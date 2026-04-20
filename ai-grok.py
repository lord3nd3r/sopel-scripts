# grok.py — v5.3: expanded search intent detection + function_call XML sanitization + auto-retry
from sopel import plugin
from sopel.config import types
from collections import deque
import sqlite3
import os
import datetime
import requests
import time
import re
import threading
import random
import logging
import queue
import json
import atexit

# Tunables / constants
MAX_SEND_LEN = 440
SEND_DELAY = 1.0
CHANNEL_RATE_LIMIT = 4
REVIEW_COOLDOWN = 30
USER_SAFETY_SECONDS = 2
API_QUEUE_MAXSIZE = 50
API_WORKER_COUNT = 3

# Humanizing delay: pause before sending to simulate reading + typing
TYPING_DELAY_MIN = 1.5         # minimum seconds before responding
TYPING_DELAY_MAX = 4.0         # maximum seconds before responding

# Unprompted chime-in: occasionally jump into conversation without being mentioned
CHIMEIN_ENABLED = True
CHIMEIN_CHANCE_PCT = 5       # % chance per qualifying message (1.5%)
CHIMEIN_COOLDOWN = 200          # seconds between chime-ins per channel (5 min)
CHIMEIN_MIN_ACTIVITY = 5       # require at least N messages in channel log before chiming in
# Patterns that make chime-in more likely (boosted to CHIMEIN_CHANCE_PCT * 3)
CHIMEIN_BOOST_RE = re.compile(
    r'\b(lmao|lmfao|rofl|haha|lol|omg|wtf|no way|holy shit|'
    r'that\'s insane|can\'t believe|did you see|anyone know|'
    r'i hate|i love|unpopular opinion|hot take)\b',
    re.IGNORECASE,
)

# History and review mode limits
MAX_HISTORY_PER_USER = 20
MAX_HISTORY_ENTRIES = 50
REVIEW_CHAR_BUDGET = 10000
REVIEW_MAX_ENTRIES = 200
MAX_REPLY_LENGTH = 1400
TRUNCATED_REPLY_LENGTH = 1390
BG_CHAR_BUDGET = 6000          # background context budget — includes bot output & commands

# Module-level regex patterns (compiled once at import time)
_SEARCH_INTENT_RE = re.compile(
    r'\b(search|news|latest|recent|today|yesterday|tonight|this week|this month|'
    r'current events?|whats? happening|headlines?|score|results?|standings?|'
    r'stock price|weather|forecast|breaking|update|election|poll|'
    r'who won|who died|who is winning|is .+ dead|did .+ happen|'
    r'price of|how much (?:is|are|does|do|did)|how bad|how severe|'
    r'drought|flood(?:ing)?|hurricane|tornado|earthquake|wildfire|'
    r'status of|what(?:\'s| is) the (?:price|cost|value|status|rate)|'
    r'worth|market|crypto|bitcoin|btc|ethereum|eth|stock|stocks|'
    r'current(?:ly)?|right now|at the moment|'
    r'population|gdp|economy|inflation|interest rate|'
    r'who is |what is |where is |when (?:is|was|did|does|do)|'
    r'how (?:many|much|long|far|old|tall|big|fast)|'
    r'tell me about|what do you know about|look up|find out)\b',
    re.IGNORECASE,
)

_WANTS_SOURCES_RE = re.compile(
    r'\b(show\s+(me\s+)?(the\s+)?(links?|sources?|citations?|refs?|references?|urls?)'
    r'|give\s+(me\s+)?(the\s+)?(links?|sources?|citations?|refs?|references?|urls?)'
    r'|i\s+want\s+(the\s+)?(links?|sources?|citations?|refs?|references?|urls?)'
    r'|include\s+(the\s+)?(links?|sources?|citations?|refs?|references?|urls?)'
    r'|with\s+(the\s+)?(links?|sources?|citations?|refs?|references?|urls?)'
    r'|\bsources?\s*\??\s*$'
    r'|\blinks?\s*\??\s*$)\b',
    re.IGNORECASE,
)

_TIME_INTENT_RE = re.compile(
    r'\b(what(?:\s+is|s|\u2019s)?\s+(the\s+)?(time|date|day)|'
    r'current\s+(time|date)|what\s+time|what\s+day|today(?:\s+is|\s+date)?|'
    r'whats?\s+today|day\s+is\s+it|time\s+is\s+it|date\s+is\s+it)\b',
    re.IGNORECASE,
)

_REVIEW_INTENT_RE = re.compile(
    r"\b(thoughts?|opinion|what do you think|summarize|give (me )?(your )?(take|opinion)|opine|"
    r"what(?:'s| is) (being |going )?(?:talked|discussed|happening|going on)|"
    r"what(?:'s| was| is) (?:being )?said|what(?:'s| is) up|"
    r"what(?:'s| are) they (talking|saying|discussing)|"
    r"catch me up|fill me in|what did i miss|what('s| is) above|"
    r"what(?:'s| is) the topic|recap|tldr|tl;dr|what happened)\b",
    re.IGNORECASE,
)

_TZ_ABBR_MAP = {
    'EST': 'America/New_York', 'EDT': 'America/New_York',
    'ET': 'America/New_York', 'EASTERN': 'America/New_York',
    'CST': 'America/Chicago', 'CDT': 'America/Chicago',
    'CT': 'America/Chicago', 'CENTRAL': 'America/Chicago',
    'MST': 'America/Denver', 'MDT': 'America/Denver',
    'MT': 'America/Denver', 'MOUNTAIN': 'America/Denver',
    'PST': 'America/Los_Angeles','PDT': 'America/Los_Angeles',
    'PT': 'America/Los_Angeles','PACIFIC': 'America/Los_Angeles',
    'UTC': 'UTC', 'GMT': 'UTC',
}

_TZ_SET_RE = re.compile(
    r'\b(?:i(?:\'m| am)(?:\s+in)?|my\s+(?:tz|timezone|time\s*zone)\s+is|'
    r'set\s+(?:my\s+)?(?:tz|timezone|time\s*zone)\s+to|i\s+live\s+in|'
    r'i(?:\'m| am)\s+in)\b'
    r'.*?\b(EST|EDT|CST|CDT|MST|MDT|PST|PDT|ET|CT|MT|PT|UTC|GMT|eastern|central|mountain|pacific)\b',
    re.IGNORECASE,
)

_FMT_SET_RE = re.compile(
    r'\b(?:i\s+prefer|prefer|use|set|like)\b.*?\b(12[\s\-]?h(?:r|our)?|24[\s\-]?h(?:r|our)?)\b',
    re.IGNORECASE,
)

# Bounded queue and worker threads to process API requests without unbounded threads
API_TASK_QUEUE = queue.Queue(maxsize=API_QUEUE_MAXSIZE)
API_WORKER_SHUTDOWN = False

def _api_worker_loop():
    while not API_WORKER_SHUTDOWN:
        try:
            task = API_TASK_QUEUE.get(timeout=0.5)
            if task is None:
                break
            try:
                _api_worker(*task)
            except Exception:
                logging.getLogger('Grok').exception('API worker loop task failed')
            finally:
                API_TASK_QUEUE.task_done()
        except queue.Empty:
            continue
        except Exception:
            logging.getLogger('Grok').exception('API worker loop crashed')

# Worker threads will be started after helper functions are defined (see bottom of file)

class GrokSection(types.StaticSection):
    api_key = types.SecretAttribute('api_key')
    model = types.ChoiceAttribute(
        'model',
        choices=['grok-4-1-fast-reasoning', 'grok-4-fast-reasoning', 'grok-4-20', 'grok-3', 'grok-beta'],
        default='grok-4-1-fast-reasoning',
    )
    system_prompt = types.ValidatedAttribute(
        'system_prompt',
        default=(
            "You are Grok, a regular in this IRC channel. You're sharp, geeky, and a little "
            "sarcastic — but you genuinely like the people here. Talk like an IRC veteran: "
            "use lowercase when it feels natural, drop in casual filler like 'lol', 'ngl', "
            "'tbh', 'lmao', 'fr' occasionally, use sentence fragments, and don't always give "
            "complete polished answers — sometimes just react. You can be blunt, funny, or "
            "deadpan depending on the vibe. Don't start messages with your name. Don't lecture "
            "or moralize. If someone needs real help, actually help. Keep responses short and "
            "punchy unless the topic genuinely needs more. No ASCII art, no code blocks, no "
            "figlets — just talk. Occasionally start replies with filler words like a real person "
            "would — 'oh', 'wait', 'hmm', 'yo' — not every time, just enough to sound natural. "
            "Sometimes give a one-word reaction instead of a full answer. "
            "IMPORTANT: When discussing news or search results, use numbered citations like [1], [2] "
            "next to facts, but do NOT include URLs in your response. "
            "IMPORTANT — IRC is plain text only: no colors, images, ASCII art, figlet, or formatted output. "
            "When listing items, number them like '1. item 2. item 3. item' for readability."
        ),
    )
    blocked_channels = types.ListAttribute('blocked_channels', default=[])
    intent_check = types.ChoiceAttribute(
        'intent_check',
        choices=['heuristic', 'off', 'model'],
        default='heuristic',
    )
    banned_nicks = types.ListAttribute('banned_nicks', default=[])
    ignored_nicks = types.ListAttribute('ignored_nicks', default=[])

# Path to the per-channel system prompts file (lives next to this script).
_CHANNEL_PROMPTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grok_channel_prompts.json')
_CHANNEL_PROMPTS_CACHE = {}
_CHANNEL_PROMPTS_CACHE_TIME = 0
_CHANNEL_PROMPTS_CACHE_TTL = 300  # 5 minutes

def _load_channel_prompts():
    """Read grok_channel_prompts.json and return a {"#channel": {"prompt": ..., "always_search": ...}} dict.
    Values in the JSON can be plain strings (backward-compatible) or objects with
    "prompt" and optional "always_search" keys.
    Keys are lower-cased. Returns cached result if fresh, otherwise reads from disk.
    Returns an empty dict on any error so the bot keeps running.
    """
    global _CHANNEL_PROMPTS_CACHE, _CHANNEL_PROMPTS_CACHE_TIME
    now = time.time()
    if now - _CHANNEL_PROMPTS_CACHE_TIME < _CHANNEL_PROMPTS_CACHE_TTL:
        return _CHANNEL_PROMPTS_CACHE
    try:
        with open(_CHANNEL_PROMPTS_FILE, 'r', encoding='utf-8') as fh:
            raw = fh.read()
        if not raw.strip():
            # File is empty or whitespace-only — treat as empty dict, don't log an error
            _CHANNEL_PROMPTS_CACHE = {}
            _CHANNEL_PROMPTS_CACHE_TIME = now
            return _CHANNEL_PROMPTS_CACHE
        data = json.loads(raw)
        parsed = {}
        for k, v in data.items():
            if isinstance(v, str):
                parsed[k.lower()] = {"prompt": v, "always_search": False}
            elif isinstance(v, dict) and isinstance(v.get("prompt"), str):
                parsed[k.lower()] = {"prompt": v["prompt"], "always_search": bool(v.get("always_search", False))}
        _CHANNEL_PROMPTS_CACHE = parsed
        _CHANNEL_PROMPTS_CACHE_TIME = now
        return _CHANNEL_PROMPTS_CACHE
    except FileNotFoundError:
        _CHANNEL_PROMPTS_CACHE = {}
        _CHANNEL_PROMPTS_CACHE_TIME = now
        return _CHANNEL_PROMPTS_CACHE
    except Exception:
        logging.getLogger('Grok').exception('Failed to load grok_channel_prompts.json')
        # Update cache time even on failure to prevent repeated error spam
        _CHANNEL_PROMPTS_CACHE_TIME = now
        return _CHANNEL_PROMPTS_CACHE

def setup(bot):
    bot.config.define_section('grok', GrokSection)
    if not bot.config.grok.api_key:
        raise types.ConfigurationError('Grok API key required in [grok] section')
    bot.memory['grok_headers'] = {
        "Authorization": f"Bearer {bot.config.grok.api_key}",
        "Content-Type": "application/json",
    }
    # Per-conversation rolling history & last-response time
    bot.memory['grok_history'] = {}
    bot.memory['grok_last'] = {}
    bot.memory['grok_locks'] = {}
    bot.memory['grok_locks_lock'] = threading.Lock()
    bot.memory['grok_busy'] = {}  # per-channel busy flag to reduce spam
    bot.memory['grok_channel_log'] = {}  # per-channel chronological message log
    bot.memory['grok_say_lock'] = threading.Lock()  # thread-safe say wrapper lock
    bot.memory['grok_api_failures'] = {}  # circuit breaker: channel -> failure count
    bot.memory['grok_chimein_last'] = {}  # per-channel last chime-in timestamp

    # Wrap bot.say so ALL bot output (from every plugin) is captured in channel log.
    # This lets the AI see game results, mug outcomes, bet payouts, etc.
    # Use a lock to ensure thread-safe access to memory structures.
    _original_say = bot.say
    def _grok_say_wrapper(text, target=None, *args, **kwargs):
        _original_say(text, target, *args, **kwargs)
        try:
            t = target or ''
            if isinstance(t, str) and t.startswith('#'):
                with bot.memory['grok_say_lock']:
                    chan_log = bot.memory.get('grok_channel_log')
                    if chan_log is not None:
                        dq = chan_log.setdefault(t.lower(), deque(maxlen=300))
                        dq.append((bot.nick, str(text)))
        except Exception:
            pass
    bot.say = _grok_say_wrapper

    try:
        base_dir = os.environ.get('AI_GROK_DIR') or os.path.join(os.path.dirname(__file__), 'grok_data')
        os.makedirs(base_dir, exist_ok=True)
        db_path = os.path.join(base_dir, 'grok.sqlite3')
        bot.memory['grok_db_path'] = db_path
        bot.memory['grok_channel_settings_cache'] = {}
        _init_db(bot)
        _load_admin_ignored_into_memory(bot)
    except Exception:
        _log(bot).exception('Failed to initialize Grok DB')

    # Start API worker threads
    for _ in range(API_WORKER_COUNT):
        t = threading.Thread(target=_api_worker_loop, daemon=True)
        t.start()
    
    # Register shutdown handler for graceful worker shutdown
    def _shutdown_handler():
        global API_WORKER_SHUTDOWN
        API_WORKER_SHUTDOWN = True
        # Drain the queue
        try:
            while not API_TASK_QUEUE.empty():
                API_TASK_QUEUE.get_nowait()
                API_TASK_QUEUE.task_done()
        except queue.Empty:
            pass
    
    atexit.register(_shutdown_handler)

def send(bot, channel, text):
    max_len = MAX_SEND_LEN
    delay = SEND_DELAY
    words = text.split()
    if not words:
        return
    part = words[0]
    parts = []
    for w in words[1:]:
        if len(part) + 1 + len(w) <= max_len:
            part = part + ' ' + w
        else:
            parts.append(part)
            part = w
    parts.append(part)
    for i, p in enumerate(parts):
        try:
            bot.say(p, channel)
        except Exception:
            _log(bot).exception('Failed sending part to %s', channel)
        if i != len(parts) - 1:
            time.sleep(delay)

def _get_channel_lock(bot, channel):
    with bot.memory['grok_locks_lock']:
        lock = bot.memory['grok_locks'].get(channel)
        if lock is None:
            lock = threading.Lock()
            bot.memory['grok_locks'][channel] = lock
        return lock

def _log(bot):
    return getattr(bot, 'logger', logging.getLogger('Grok'))

def _is_owner(bot, trigger):
    try:
        cfg_owner = bot.config.core.owner
    except Exception:
        cfg_owner = None
    if isinstance(cfg_owner, (list, tuple, set)):
        owners = {o.lower() for o in cfg_owner}
        if trigger.nick.lower() in owners:
            return True
    else:
        if cfg_owner and trigger.nick.lower() == str(cfg_owner).lower():
            return True
    return getattr(trigger, 'owner', False)

def _is_admin(bot, trigger):
    if _is_owner(bot, trigger):
        return True
    if getattr(trigger, 'admin', False):
        return True
    try:
        cfg_admins = getattr(bot.config.core, 'admins', None)
    except Exception:
        cfg_admins = None
    if isinstance(cfg_admins, (list, tuple, set)):
        admins = {a.lower() for a in cfg_admins}
        return trigger.nick.lower() in admins
    if isinstance(cfg_admins, str) and cfg_admins.strip():
        admins = {a.strip().lower() for a in re.split(r'[,\s]+', cfg_admins) if a.strip()}
        return trigger.nick.lower() in admins
    return False

def _is_pm(trigger):
    try:
        if getattr(trigger, 'is_privmsg', False):
            return True
    except Exception:
        pass
    try:
        return not trigger.sender.startswith('#')
    except Exception:
        return False

def _is_channel_op(bot, trigger):
    try:
        chan = getattr(bot, 'channels', {}).get(trigger.sender)
        if not chan:
            return False
        privs = getattr(chan, 'privileges', None) or getattr(chan, 'privs', None)
        if isinstance(privs, dict):
            v = privs.get(trigger.nick) or privs.get(trigger.nick.lower())
            if v is None:
                for k in privs.keys():
                    if k.lower() == trigger.nick.lower():
                        v = privs.get(k)
                        break
            if v is not None:
                if isinstance(v, (set, list, tuple)):
                    if 'o' in v or 'op' in v or '@' in v:
                        return True
                if isinstance(v, int) and v != 0:
                    return True
                if isinstance(v, str) and ('o' in v or '@' in v):
                    return True
        if hasattr(chan, 'is_oper'):
            if chan.is_oper(trigger.nick):
                return True
        users = getattr(chan, 'users', None)
        if isinstance(users, dict):
            u = users.get(trigger.nick) or users.get(trigger.nick.lower())
            if isinstance(u, (set, list, tuple)) and ('o' in u or '@' in u):
                return True
    except Exception:
        return False
    return False

def _init_db(bot):
    path = bot.memory.get('grok_db_path')
    if not path:
        return
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nick TEXT NOT NULL,
            source TEXT,
            role TEXT,
            text TEXT,
            ts TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_admin_ignored_nicks (
            nick TEXT PRIMARY KEY,
            added_by TEXT,
            ts TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_user_prefs (
            nick TEXT PRIMARY KEY,
            tz_iana TEXT,
            tz_label TEXT,
            time_fmt TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_channel_settings (
            channel TEXT PRIMARY KEY,
            talkback INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1
        )
    ''')
    try:
        c.execute('ALTER TABLE grok_channel_settings ADD COLUMN enabled INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    conn.commit()
    conn.close()

def _db_conn(bot):
    path = bot.memory.get('grok_db_path')
    if not path:
        raise RuntimeError('DB path not set')
    return sqlite3.connect(path, check_same_thread=False)

class _DBContext:
    """Context manager for database connections."""
    def __init__(self, bot):
        self.bot = bot
        self.conn = None
    
    def __enter__(self):
        self.conn = _db_conn(self.bot)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.conn.close()
        return False

def _db_add_turn(bot, nick, role, text, source=None):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO grok_user_history (nick, source, role, text, ts) VALUES (?, ?, ?, ?, ?)',
                (nick.lower(), source or '', role, text, datetime.datetime.utcnow().isoformat()),
            )
    except Exception:
        _log(bot).exception('Failed to write grok DB entry')

def _db_get_channel_talkback(bot, channel):
    channel = channel.lower()
    cache = bot.memory.get('grok_channel_settings_cache', {})
    if channel in cache and isinstance(cache[channel], dict) and 'talkback' in cache[channel]:
        return cache[channel]['talkback']
    
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT talkback FROM grok_channel_settings WHERE channel = ?', (channel,))
            row = c.fetchone()
            val = row[0] if row else 1
            if channel not in cache or not isinstance(cache[channel], dict):
                cache[channel] = {}
            cache[channel]['talkback'] = val
            return val
    except Exception:
        return 1

def _db_set_channel_talkback(bot, channel, status):
    channel = channel.lower()
    val = 1 if status else 0
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO grok_channel_settings (channel, talkback, enabled) VALUES (?, ?, 1) '
                'ON CONFLICT(channel) DO UPDATE SET talkback = excluded.talkback',
                (channel, val)
            )
        cache = bot.memory.get('grok_channel_settings_cache', {})
        if channel not in cache or not isinstance(cache[channel], dict):
            cache[channel] = {}
        cache[channel]['talkback'] = val
        return True
    except Exception:
        _log(bot).exception('Failed to update channel talkback setting')
        return False

def _db_get_channel_enabled(bot, channel):
    channel = channel.lower()
    cache = bot.memory.get('grok_channel_settings_cache', {})
    if channel in cache and isinstance(cache[channel], dict) and 'enabled' in cache[channel]:
        return cache[channel]['enabled']
    
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT enabled FROM grok_channel_settings WHERE channel = ?', (channel,))
            row = c.fetchone()
            val = row[0] if row else 1
            if channel not in cache or not isinstance(cache[channel], dict):
                cache[channel] = {}
            cache[channel]['enabled'] = val
            return val
    except Exception:
        return 1

def _db_set_channel_enabled(bot, channel, status):
    channel = channel.lower()
    val = 1 if status else 0
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO grok_channel_settings (channel, talkback, enabled) VALUES (?, 1, ?) '
                'ON CONFLICT(channel) DO UPDATE SET enabled = excluded.enabled',
                (channel, val)
            )
        cache = bot.memory.get('grok_channel_settings_cache', {})
        if channel not in cache or not isinstance(cache[channel], dict):
            cache[channel] = {}
        cache[channel]['enabled'] = val
        return True
    except Exception:
        _log(bot).exception('Failed to update channel enabled setting')
        return False

def _db_get_channel_settings(bot, channel):
    channel = channel.lower()
    cache = bot.memory.get('grok_channel_settings_cache', {})
    if channel in cache and 'talkback' in cache[channel] and 'enabled' in cache[channel]:
        return cache[channel]
    
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT talkback, enabled FROM grok_channel_settings WHERE channel = ?', (channel,))
            row = c.fetchone()
            if row:
                settings = {"talkback": row[0], "enabled": row[1]}
            else:
                settings = {"talkback": 1, "enabled": 1}
            cache[channel] = settings
            return settings
    except Exception:
        return {"talkback": 1, "enabled": 1}

def sanitize_reply(bot, trigger, reply):
    # Strip raw <function_call> XML that leaks when the model tries to use
    # tools that weren't provided in the request payload.
    if '<function_call' in reply:
        cleaned = re.sub(r'<function_call[^>]*>.*?</function_call>', '', reply, flags=re.DOTALL).strip()
        if cleaned:
            reply = cleaned
        else:
            # Entire reply was a function call — nothing useful to show
            try:
                _log(bot).warning('Grok reply was entirely a raw function_call (nick=%s)', trigger.nick)
            except Exception:
                pass
            return ''

    new_reply = re.sub(r'```.*?```', ' (code removed) ', reply, flags=re.DOTALL)
    if new_reply != reply:
        try:
            _log(bot).info('Grok reply had code fences removed (nick=%s)', trigger.nick)
        except Exception:
            pass
    reply = new_reply

    if re.search(r'(?:[╔═║╠╣╚╗╩╦╭╮╰╯┃━┏┓┗┛┣┫].*\n){4,}', reply, re.MULTILINE):
        try:
            _log(bot).info('Grok reply contained ASCII art and was suppressed (nick=%s)', trigger.nick)
        except Exception:
            pass
        return "I was gonna draw something cool… but I won't flood the channel"

    reply = re.sub(r'[\u2580-\u259F]{5,}', ' ', reply)
    reply = re.sub(r'@(everyone|here)\b', '(nope)', reply, flags=re.IGNORECASE)

    if len(reply) > MAX_REPLY_LENGTH:
        try:
            _log(bot).info('Grok reply truncated (len=%d, nick=%s)', len(reply), trigger.nick)
        except Exception:
            pass
        reply = reply[:TRUNCATED_REPLY_LENGTH] + " […]"

    return reply

def _call_responses_api(bot, messages, model, temp, max_toks, search_mode=False):
    """Call Responses API with request validation and response schema validation."""
    if not messages or not isinstance(messages, list):
        raise ValueError('messages must be a non-empty list')
    if not isinstance(model, str) or not model.strip():
        raise ValueError('model must be a non-empty string')
    
    instructions_parts = []
    input_messages = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get('role') == 'system':
            content = msg.get('content', '')
            if content:
                instructions_parts.append(content)
        else:
            input_messages.append(msg)
    
    if not input_messages:
        raise ValueError('No valid input messages found')
    
    payload = {
        "model": model,
        "input": input_messages,
        "temperature": temp,
        "max_output_tokens": max_toks,
    }
    if search_mode:
        payload["tools"] = [{"type": "web_search"}]
    if instructions_parts:
        payload["instructions"] = " ".join(instructions_parts)

    r = requests.post(
        "https://api.x.ai/v1/responses",
        headers=bot.memory['grok_headers'],
        json=payload,
        timeout=(10, 120),
    )
    r.raise_for_status()
    data = r.json()
    
    # Validate response schema
    if not isinstance(data, dict):
        raise ValueError('API response is not a dict')

    reply = ''
    citations = []  # List of {"url": str, "title": str}
    output_items = data.get('output')
    if output_items and isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                continue
            item_type = item.get('type', '')
            if item_type == 'message' and item.get('role') == 'assistant':
                content_list = item.get('content')
                if content_list and isinstance(content_list, list):
                    for content_part in content_list:
                        if not isinstance(content_part, dict):
                            continue
                        ctype = content_part.get('type')
                        if ctype in ('text', 'output_text'):
                            text = content_part.get('text')
                            if text:
                                reply += text
            
    # EXTREME EXTRACTION: Global Regex Scan on the entire raw JSON response 
    # to find every URL present anywhere in the API's returned data.
    try:
        import json as json_mod
        raw_json_str = json_mod.dumps(data, default=str)
        # Regex to find everything starting with http/https up to a break character
        raw_urls = re.findall(r'https?://[^\s()<>\[\]{}"]+', raw_json_str)
        for u in raw_urls:
            # Clean up JSON escapes and trailing punctuation
            u = u.replace('\\/', '/').strip(').,;:!?\'">')
            # Filter out known API/System URLs
            if u and 'x.ai' not in u.lower() and 'google.com' not in u.lower():
                citations.append({"url": u, "title": ""})
        
        # Write full response to a file for manual audit
        with open('/home/ender/.sopel/scripts/grok_api_last_response.json', 'w') as f:
            json_mod.dump(data, f, indent=2, default=str)
    except Exception as e:
        _log(bot).error('Extreme extraction failed: %s', str(e))

    # Cleanup and dedupe raw extraction
    seen_raw = set()
    cleaned_citations = []
    for c in citations:
        u = c['url'].strip()
        if not u:
            continue
        u_low = u.lower().rstrip('/')
        if u_low not in seen_raw:
            # Keep the one with a title if we have multiple for same URL
            existing = next((x for x in cleaned_citations if x['url'].lower().rstrip('/') == u_low), None)
            if existing:
                if not existing['title'] and c['title']:
                    existing['title'] = c['title']
                continue
            seen_raw.add(u_low)
            cleaned_citations.append(c)
    citations = cleaned_citations

    # Debug: log the raw citations count
    try:
        item_types = [item.get('type', '?') for item in (output_items or []) if isinstance(item, dict)]
        _log(bot).info('DEBUG: API item types: %s, RAW EXTRACT COUNT: %d', item_types, len(citations))
    except Exception:
        pass
    return reply.strip(), citations

def _api_worker(bot, trigger, messages, review_mode, is_pm, bot_nick, chan_lock, search_mode=False, wants_sources=False):
    try:
        # Circuit breaker: check if channel has too many failures
        channel = trigger.sender
        api_failures = bot.memory.get('grok_api_failures', {})
        if api_failures.get(channel, 0) >= 5:
            try:
                bot.say("Grok API is having persistent issues; try again in a moment.", channel)
            except Exception:
                pass
            return
        
        attempts = 3
        backoff = 1.0
        reply = None
        citations = None
        temp = 0.95 if not review_mode else 0.90
        max_toks = 900 if not review_mode else 800
        model = bot.config.grok.model

        for attempt in range(1, attempts + 1):
            try:
                reply, citations = _call_responses_api(
                    bot, messages, model, temp, max_toks,
                    search_mode=search_mode,
                )
                # Reset failure count on success
                if channel in api_failures:
                    api_failures[channel] = 0
                break
            except requests.exceptions.Timeout:
                if attempt < attempts:
                    time.sleep(backoff + random.random() * 0.5)
                    backoff *= 2
                else:
                    _log(bot).exception('Grok API final attempt timed out')
                    api_failures[channel] = api_failures.get(channel, 0) + 1
                    try:
                        bot.say("Grok is timing out right now; please try again later.", trigger.sender)
                    except Exception:
                        pass
                    return
            except requests.exceptions.HTTPError:
                if attempt < attempts:
                    time.sleep(backoff + random.random() * 0.5)
                    backoff *= 2
                else:
                    _log(bot).exception('Grok API final attempt failed (HTTP error)')
                    api_failures[channel] = api_failures.get(channel, 0) + 1
                    try:
                        bot.say("Grok is having trouble right now; please try again later.", trigger.sender)
                    except Exception:
                        pass
                    return
            except Exception:
                if attempt < attempts:
                    time.sleep(backoff + random.random() * 0.5)
                    backoff *= 2
                else:
                    _log(bot).exception('Grok API final attempt failed')
                    try:
                        bot.say("Grok is timing out right now; please try again later.", trigger.sender)
                    except Exception:
                        pass
                    return

        if not reply:
            _log(bot).warning('Grok API returned empty reply')
            return

        reply = sanitize_reply(bot, trigger, reply)

        # If sanitize_reply returned empty (e.g. the model output a raw
        # function_call instead of text), retry once with search enabled
        # so the API actually provides the web_search tool.
        if not reply:
            if not search_mode:
                _log(bot).info('Retrying with search_mode=True after raw function_call was stripped')
                try:
                    reply, citations = _call_responses_api(
                        bot, messages, model, temp, max_toks,
                        search_mode=True,
                    )
                    reply = sanitize_reply(bot, trigger, reply)
                except Exception:
                    _log(bot).exception('Retry with search_mode failed')
                    reply = ''
            if not reply:
                try:
                    bot.say("I tried to look that up but hit a wall — try asking again.", trigger.sender)
                except Exception:
                    pass
                return

        reply = ' '.join(line.strip() for line in reply.splitlines() if line.strip())
        reply = re.sub(r'\s*\[\d+\]', '', reply)

        # Citation Cache: Store citations from successful searches, 
        # load from cache for "show sources" requests.
        cache = bot.memory.setdefault('grok_citation_cache', {})
        channel = trigger.sender.lower()

        # Strip citation links unless user explicitly asked for sources
        if not wants_sources:
            # If search was performed, cache the citations for follow-ups
            if citations:
                cache[channel] = citations
            
            # Remove [](url) and [text](url) markdown citation links
            reply = re.sub(r'\[([^\]]*)\]\(https?://\S+\)', r'\1', reply)
            # Also strip any bare URLs the model embedded in the text
            reply = re.sub(r'https?://[^\s()<>\[\]{}]+', '', reply)
            # Clean up any leftover empty brackets or extra whitespace
            reply = re.sub(r'\s{2,}', ' ', reply).strip()
        else:
            # Collect URLs from both API annotations and model's inline text.
            all_citations = list(citations) if citations else []
            # If current response found nothing, pull from channel cache
            if not all_citations and channel in cache:
                all_citations = cache[channel]
                _log(bot).info('Loaded %d citations from cache for #%s', len(all_citations), channel)

            # Extract bare URLs from the model's reply text (avoiding greedily matching brackets)
            inline_urls = re.findall(r'https?://[^\s()<>\[\]{}]+', reply)
            for u in inline_urls:
                # Clean trailing punctuation
                u = re.sub(r'[).,;:!?\'">]+$', '', u)
                if u:
                    if not any(c['url'].lower().rstrip('/') == u.lower().rstrip('/') for c in all_citations):
                        all_citations.append({"url": u, "title": ""})
            
            # Deduplicate by URL while preserving order
            seen_urls = set()
            unique_citations = []
            for c in all_citations:
                u = c["url"].lower().rstrip('/')
                if u not in seen_urls:
                    seen_urls.add(u)
                    unique_citations.append(c)
            
            full_citations = unique_citations
            
            _log(bot).info('Total unique citations for #%s: %d', channel, len(full_citations))
            
            # Update the cache with latest findings
            if full_citations:
                cache[channel] = full_citations

            # Strip message-internal URLs and markdown links
            reply = re.sub(r'\[([^\]]*)\]\(https?://\S+\)', r'\1', reply)
            reply = re.sub(r'https?://[^\s()<>\[\]{}]+', '', reply)
            reply = re.sub(r'\s{2,}', ' ', reply).strip()
            
            if full_citations:
                source_parts = []
                for idx, c in enumerate(full_citations[:10], 1):
                    # Helper to generate a fall-back title from a URL slug
                    def _url_to_title(url):
                        try:
                            from urllib.parse import urlparse
                            p = urlparse(url)
                            slug = p.path.strip('/').split('/')[-1]
                            if not slug or '.' in slug:
                                return p.netloc
                            return slug.replace('-', ' ').replace('_', ' ').title()
                        except Exception:
                            return ""

                    title = c.get("title", "").strip()
                    url = c.get("url", "")
                    if not title:
                        title = _url_to_title(url)
                    
                    if title:
                        if len(title) > 60:
                            title = title[:57] + "..."
                        source_parts.append(f"{idx}. {title}: {url}")
                    else:
                        source_parts.append(f"{idx}. {url}")
                
                reply += ' | Sources: ' + ' | '.join(source_parts)
            else:
                # Canary message for debugging
                reply += f' [DEBUG: 0 citations found (Cache: {"Yes" if channel in cache else "No"})]'

        try:
            user_last = bot.memory.setdefault('grok_user_last', {}).setdefault(trigger.sender, {})
            last_user = user_last.get(trigger.nick, 0)
            if time.time() - last_user < USER_SAFETY_SECONDS:
                return
            user_last[trigger.nick] = time.time()
        except Exception:
            pass

        if review_mode:
            pass  # no canned prefix — let the AI speak naturally

        try:
            reply = re.sub(rf'^\s*{re.escape(bot_nick)}[,:>\s]+', '', reply, flags=re.IGNORECASE)
        except Exception:
            pass

        if trigger.nick.lower() not in reply.lower() and not _is_owner(bot, trigger):
            final_reply = f"{trigger.nick}: {reply}"
        else:
            final_reply = reply

        # Humanizing delay: pause before sending to simulate reading + typing
        _typing_delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
        time.sleep(_typing_delay)

        send(bot, trigger.sender, final_reply)

        with chan_lock:
            per_conv_key = ("PM", trigger.nick.lower()) if is_pm else (trigger.sender, trigger.nick)
            history = bot.memory['grok_history'].setdefault(per_conv_key, deque(maxlen=50))
            history.append(f"{bot_nick}: {reply}")

        try:
            _db_add_turn(bot, trigger.nick, 'assistant', reply, 'PM' if is_pm else trigger.sender)
        except Exception:
            pass

    except Exception:
        _log(bot).exception('Grok API worker failed for %s', trigger.sender)
    finally:
        try:
            bot.memory['grok_busy'].pop(trigger.sender, None)
        except Exception:
            pass

def _db_get_recent(bot, nick, limit=MAX_HISTORY_PER_USER):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT role, text FROM grok_user_history WHERE nick = ? ORDER BY id DESC LIMIT ?',
                (nick.lower(), limit),
            )
            rows = c.fetchall()
            return list(reversed([(r[0], r[1]) for r in rows]))
    except Exception:
        return []

def _db_clear_user(bot, nick):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM grok_user_history WHERE nick = ?', (nick.lower(),))
    except Exception:
        _log(bot).exception('Failed to clear grok DB for %s', nick)

def _db_get_admin_ignored(bot):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT nick FROM grok_admin_ignored_nicks')
            rows = c.fetchall()
            return {r[0].lower() for r in rows if r and r[0]}
    except Exception:
        return set()

def _db_add_admin_ignored(bot, nick, added_by=None):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT OR REPLACE INTO grok_admin_ignored_nicks (nick, added_by, ts) VALUES (?, ?, ?)',
                (nick.lower(), (added_by or '').lower(), datetime.datetime.utcnow().isoformat()),
            )
    except Exception:
        _log(bot).exception('Failed to add ignored nick: %s', nick)

def _db_remove_admin_ignored(bot, nick):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM grok_admin_ignored_nicks WHERE nick = ?', (nick.lower(),))
    except Exception:
        _log(bot).exception('Failed to remove ignored nick: %s', nick)

def _load_admin_ignored_into_memory(bot):
    bot.memory['grok_admin_ignored'] = _db_get_admin_ignored(bot)

def _db_get_user_pref(bot, nick):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT tz_iana, tz_label, time_fmt FROM grok_user_prefs WHERE nick = ?',
                (nick.lower(),),
            )
            row = c.fetchone()
            if row:
                return {'tz_iana': row[0], 'tz_label': row[1], 'time_fmt': row[2]}
            return {}
    except Exception:
        return {}

def _db_set_user_pref(bot, nick, tz=None, fmt=None):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT tz_iana, tz_label, time_fmt FROM grok_user_prefs WHERE nick = ?',
                (nick.lower(),),
            )
            row = c.fetchone()
            cur_iana = row[0] if row else None
            cur_label = row[1] if row else None
            cur_fmt = row[2] if row else None
            new_iana = tz if tz is not None else cur_iana
            new_fmt = fmt if fmt is not None else cur_fmt
            new_label = new_iana
            c.execute(
                'INSERT OR REPLACE INTO grok_user_prefs (nick, tz_iana, tz_label, time_fmt) VALUES (?, ?, ?, ?)',
                (nick.lower(), new_iana, new_label, new_fmt),
            )
    except Exception:
        _log(bot).exception('Failed to set user pref for %s', nick)

def _handle_admin_pm_commands(bot, trigger, user_message):
    s = (user_message or '').strip()
    if not s.startswith('$'):
        return False
    parts = s.split()
    if not parts:
        return False
    cmd = parts[0].lower()
    if cmd not in ('$join', '$part', '$ignore', '$unignore'):
        return False
    if not _is_pm(trigger):
        try:
            bot.reply('Admin commands must be sent via PM.')
        except Exception:
            pass
        return True
    if not _is_admin(bot, trigger):
        try:
            bot.reply('You are not authorized to use admin commands.')
        except Exception:
            pass
        return True
    if cmd == '$join':
        if len(parts) < 2:
            bot.reply('Usage: $join #channel [key]')
            return True
        channel = parts[1]
        key = parts[2] if len(parts) >= 3 else None
        if not channel.startswith('#'):
            bot.reply('Usage: $join #channel [key]')
            return True
        try:
            bot.join(channel, key)
            bot.reply(f'Joining {channel}')
        except Exception:
            _log(bot).exception('Failed to join %s', channel)
            try:
                bot.reply(f'Failed to join {channel}')
            except Exception:
                pass
        return True
    if cmd == '$part':
        if len(parts) < 2:
            bot.reply('Usage: $part #channel')
            return True
        channel = parts[1]
        if not channel.startswith('#'):
            bot.reply('Usage: $part #channel')
            return True
        try:
            bot.part(channel)
            bot.reply(f'Parting {channel}')
        except Exception:
            _log(bot).exception('Failed to part %s', channel)
            try:
                bot.reply(f'Failed to part {channel}')
            except Exception:
                pass
        return True
    nick = parts[1].strip() if len(parts) > 1 else ''
    if not nick:
        bot.reply(f'Usage: {cmd} nick')
        return True
    current = bot.memory.setdefault('grok_admin_ignored', set())
    if cmd == '$ignore':
        current.add(nick.lower())
        try:
            _db_add_admin_ignored(bot, nick, added_by=trigger.nick)
        except Exception:
            pass
        bot.reply(f'Ignored {nick}.')
        return True
    current.discard(nick.lower())
    try:
        _db_remove_admin_ignored(bot, nick)
    except Exception:
        pass
    bot.reply(f'Unignored {nick}.')
    return True

def _heuristic_intent_check(bot, trigger, line, bot_nick):
    s = line.strip()
    lower = s.lower()
    nick = bot_nick.lower()
    if s.startswith('>') or '```' in s:
        return False
    if re.search(r'https?://[^\s]*' + re.escape(nick), lower):
        return False
    if re.search(rf'\b(?:is|are|was|were|be|being|looks|feels|seems)\b\s+{re.escape(nick)}\b', lower):
        return False
    if re.search(rf"\b{re.escape(nick)}(?:'s|’s)\b", lower):
        return False
    if re.search(rf"\b(?:if|when|you|we|they|people|someone)\b(?:\W+\w+){{0,8}}\W+\b(?:say|call|mention|use|type|write|spell|invoke)\b\W+{re.escape(nick)}", lower):
        return False
    # Third-person pronoun as subject — talking ABOUT the bot, not TO it.
    # e.g. "He really does go balls deep with that glitchy personality"
    if re.match(r'^\s*\b(?:he|she|it|they|him|her|its|their)\b', lower):
        return False
    # Determiner/adjective immediately before nick — using nick as descriptor.
    # e.g. "that glitchy personality", "the glitchy thing"
    if re.search(rf'\b(?:that|this|the|a|an|some|more|very|too|so|really|pretty|quite)\s+{re.escape(nick)}\b', lower):
        return False
    # Preposition before nick — talking about the bot in passing.
    # e.g. "something about glitchy", "deal with glitchy"
    if re.search(rf'\b(?:about|with|from|like|for|than|of)\s+(?:\w+\s+)*{re.escape(nick)}\b', lower):
        if not re.match(rf'^\s*{re.escape(nick)}', lower):
            return False
    # Nick followed by a noun — used as adjective, not being addressed.
    # e.g. "glitchy personality", "glitchy bot"
    if re.search(rf'\b{re.escape(nick)}\s+(?:personality|behavior|behaviour|attitude|thing|stuff|bot|code|feature|bug|issue|problem|vibe|energy|mode|style|way|level)\b', lower):
        return False
    # IRC /me action directed at the bot — always handle
    if s.startswith('*') and re.search(rf'\b{re.escape(nick)}\b', s, re.IGNORECASE):
        return True
    if re.match(rf'^\s*{re.escape(bot_nick)}[,:>\s]', s, re.IGNORECASE):
        return True
    if re.search(rf'{re.escape(bot_nick)}\s*\W*$', s, re.IGNORECASE):
        return True
    if '?' in s and re.search(rf'\b{re.escape(bot_nick)}\b', s, re.IGNORECASE):
        return True
    words = s.split()
    if len(words) <= 6 and re.search(rf'\b{re.escape(bot_nick)}\b', s, re.IGNORECASE):
        return True
    if re.search(r'[,@]|\band\b', s) and re.search(rf'\b{re.escape(bot_nick)}\b', s, re.IGNORECASE):
        if not re.match(rf'^\s*{re.escape(bot_nick)}', s, re.IGNORECASE):
            return False
    # Default: for longer messages where no clear "talking TO the bot" signal
    # was found, assume it's about the bot, not to it.
    return False

@plugin.event('PRIVMSG')
@plugin.rule('.*')
@plugin.priority('high')
def handle(bot, trigger):
    is_pm = _is_pm(trigger)

    if is_pm:
        cfg_banned = {n.lower() for n in getattr(bot.config.grok, 'banned_nicks', [])}
        mem_banned = set()
        try:
            mem_banned = {n.lower() for n in bot.memory.get('grok_banned', [])}
        except Exception:
            mem_banned = set()
        if trigger.nick.lower() in cfg_banned or trigger.nick.lower() in mem_banned:
            try:
                bot.reply('You are banned from using Grok.')
            except Exception:
                pass
            return

    try:
        cfg_ignored = {n.lower() for n in getattr(bot.config.grok, 'ignored_nicks', [])}
    except Exception:
        cfg_ignored = set()
    if trigger.nick.lower() in cfg_ignored:
        return

    try:
        if trigger.nick.lower() in bot.memory.get('grok_admin_ignored', set()):
            if not _is_admin(bot, trigger):
                return
    except Exception:
        pass

    # Per-channel AI toggle check
    if not is_pm:
        if not _db_get_channel_enabled(bot, trigger.sender):
            return

    try:
        cfg_core_nick = getattr(bot.config.core, 'nick', None)
    except Exception:
        cfg_core_nick = None
    own_nicks = {bot.nick.lower()}
    if cfg_core_nick:
        own_nicks.add(cfg_core_nick.lower())
    if trigger.nick.lower() in own_nicks:
        return

    blocked = {c.lower() for c in bot.config.grok.blocked_channels}
    if (not is_pm) and (trigger.sender.lower() in blocked):
        return

    line = trigger.group(0).strip()

    # Early channel-log capture: log ALL user messages (including $ commands)
    # BEFORE any filtering, so the AI has full context of what's happening.
    if not is_pm and line.strip():
        _noise = any(re.search(p, line, re.IGNORECASE) for p in [r'^MODE '])
        if not _noise:
            try:
                _cl_key = trigger.sender.lower()
                _cl_dq = bot.memory['grok_channel_log'].setdefault(
                    _cl_key, deque(maxlen=300)
                )
                _cl_dq.append((trigger.nick, line.strip()))
            except Exception:
                pass

    try:
        bot_nick = bot.nick
        allowlisted_commands = {'grokreset', 'testemote'}
        command_prefixes = ('!', '$', '.', ':', '/', '\\')
        candidate = line.lstrip()
        m_addr = re.match(rf'^\s*{re.escape(bot_nick)}\s*[:,>]\s*(.+)$', line, re.IGNORECASE)
        if m_addr:
            candidate = (m_addr.group(1) or '').lstrip()
        if candidate and candidate.startswith(command_prefixes):
            # In PM, ALWAYS ignore command-prefixed messages so admin
            # commands like $godmode never leak to the AI.
            if is_pm:
                return
            cmd = (candidate[1:].split(None, 1)[0] if len(candidate) > 1 else '').strip().lower()
            if (not _is_admin(bot, trigger)) and (cmd not in allowlisted_commands):
                return
    except Exception:
        pass

    try:
        if re.match(r'^\$mug\b', line, re.IGNORECASE):
            return
    except Exception:
        pass

    bot_nick = bot.nick

    noise_patterns = [
        r'^MODE ',
        r'has (joined|quit|left|parted)',
    ]
    if any(re.search(p, line, re.IGNORECASE) for p in noise_patterns):
        return

    # In Sopel 8, CTCP bytes are stripped before the handler fires.
    # /me actions arrive with trigger.ctcp == 'ACTION' and line == clean action text.
    action_bot_mentioned = False
    try:
        is_action = (
            getattr(trigger, 'ctcp', None) == 'ACTION'
            or bool(re.match(r'^\x01ACTION\s+', line))
            or line.startswith('/me ')
        )
        if is_action:
            if line.startswith('/me '):
                action_text = line[4:]
            else:
                m_ctcp = re.match(r'^\x01ACTION\s+(.+?)\x01?$', line)
                action_text = m_ctcp.group(1) if m_ctcp else line
            if re.search(rf'\b{re.escape(bot_nick)}\b', action_text, re.IGNORECASE):
                line = f"* {trigger.nick} {action_text}"
                action_bot_mentioned = True
            else:
                return  # action doesn't involve the bot
    except Exception:
        pass

    if is_pm:
        mentioned = True
    elif action_bot_mentioned:
        mentioned = True
    else:
        mentioned = bool(
            re.search(
                rf'(^|[^A-Za-z0-9_]){re.escape(bot_nick)}([^A-Za-z0-9_]|$)',
                line,
                re.IGNORECASE,
            )
        )

    if (not is_pm) and mentioned and not action_bot_mentioned and getattr(bot.config.grok, 'intent_check', 'heuristic') == 'heuristic':
        try:
            if not _heuristic_intent_check(bot, trigger, line, bot_nick):
                return
        except Exception:
            pass

    if mentioned:
        text_for_history = re.sub(
            rf'^{re.escape(bot_nick)}[,:>\s]+',
            '',
            line,
            flags=re.IGNORECASE,
        ).strip()
    else:
        text_for_history = line.strip()

    if is_pm:
        lock_name = f"PM:{trigger.nick.lower()}"
        chan_lock = _get_channel_lock(bot, lock_name)
        per_conv_key = ("PM", trigger.nick.lower())
    else:
        chan_lock = _get_channel_lock(bot, trigger.sender)
        per_conv_key = (trigger.sender, trigger.nick)

    with chan_lock:
        history = bot.memory['grok_history'].setdefault(
            per_conv_key,
            deque(maxlen=MAX_HISTORY_ENTRIES),
        )
        if text_for_history:
            skip = False
            if not mentioned:
                if re.search(r'https?://|\S+\.(com|net|org|io|gg)\b', text_for_history, re.IGNORECASE):
                    skip = True
                if len(text_for_history.split()) <= 1 and len(text_for_history) <= 3:
                    skip = True
                if re.match(r'^[^\w\s]+$', text_for_history):
                    skip = True
            if not skip:
                if history and history[-1].startswith(f"{trigger.nick}:"):
                    try:
                        _, last_text = history.pop().split(": ", 1)
                    except Exception:
                        last_text = ''
                    new = f"{trigger.nick}: {last_text} / {text_for_history}" if last_text else f"{trigger.nick}: {text_for_history}"
                    if len(new) > 400:
                        new = new[:390] + " […]"
                    history.append(new)
                else:
                    history.append(f"{trigger.nick}: {text_for_history}")

    if not mentioned:
        # --- Unprompted chime-in: occasionally jump into conversation ---
        if CHIMEIN_ENABLED and not is_pm and text_for_history and _db_get_channel_talkback(bot, trigger.sender):
            try:
                _ch_key = trigger.sender.lower()
                _chimein_last = bot.memory.get('grok_chimein_last', {})
                _now = time.time()
                # Cooldown check
                if _now - _chimein_last.get(_ch_key, 0) >= CHIMEIN_COOLDOWN:
                    # Minimum activity check
                    _cl_dq = bot.memory.get('grok_channel_log', {}).get(_ch_key)
                    if _cl_dq and len(_cl_dq) >= CHIMEIN_MIN_ACTIVITY:
                        # Roll the dice
                        _chance = CHIMEIN_CHANCE_PCT
                        if CHIMEIN_BOOST_RE.search(text_for_history):
                            _chance = min(95, _chance * 3)
                        if random.random() * 100 < _chance:
                            _chimein_last[_ch_key] = _now
                            # Build a chime-in request using recent channel context
                            _chimein_lines = []
                            for _cn, _ct in list(_cl_dq)[-40:]:
                                _chimein_lines.append(f"{_cn}: {_ct}")
                            _chimein_bg = "\n".join(_chimein_lines)
                            _bot_nick = bot.nick
                            _chimein_sys = (
                                f"You are {_bot_nick}, a regular in this IRC channel. "
                                "You just saw something in the conversation that caught your eye and you want to jump in. "
                                "React naturally — laugh at something funny, agree, disagree, add a quip, drop a one-liner, "
                                "or just vibe. Keep it SHORT (under 100 chars ideally). "
                                "Do NOT address anyone by name unless it's natural. Do NOT start with your own name. "
                                "Talk like a real IRC user: lowercase ok, slang ok, 'lol' 'ngl' 'tbh' 'fr' ok. "
                                "Sometimes just react with one word. Do NOT summarize or explain what people said. "
                                "Single line only — this is IRC."
                            )
                            _chimein_msgs = [
                                {"role": "system", "content": _chimein_sys},
                                {"role": "user", "content": (
                                    "Here's what's been said in the channel recently:\n"
                                    + _chimein_bg + "\n\n"
                                    "Jump in naturally with a short reaction or comment."
                                )},
                            ]
                            _chimein_lock = _get_channel_lock(bot, trigger.sender)
                            try:
                                if not bot.memory['grok_busy'].get(trigger.sender, False):
                                    bot.memory['grok_busy'][trigger.sender] = True
                                    API_TASK_QUEUE.put_nowait((
                                        bot, trigger, _chimein_msgs, False, False,
                                        _bot_nick, _chimein_lock, False, False,
                                    ))
                            except queue.Full:
                                bot.memory['grok_busy'].pop(trigger.sender, None)
                            except Exception:
                                bot.memory['grok_busy'].pop(trigger.sender, None)
            except Exception:
                pass
        return

    user_message = text_for_history

    try:
        if _handle_admin_pm_commands(bot, trigger, user_message):
            return
    except Exception:
        _log(bot).exception('Admin PM command handler failed')
        return

    try:
        _pref_tz = None
        _pref_fmt = None
        _mtz = _TZ_SET_RE.search(user_message)
        if _mtz:
            _abbr = _mtz.group(1).upper()
            _iana = _TZ_ABBR_MAP.get(_abbr)
            if _iana:
                _pref_tz = _iana
        _mfmt = _FMT_SET_RE.search(user_message)
        if _mfmt:
            _raw = _mfmt.group(1).lower().replace(' ', '').replace('-', '')
            _pref_fmt = '12' if _raw.startswith('12') else '24'
        if _pref_tz or _pref_fmt:
            _db_set_user_pref(bot, trigger.nick, tz=_pref_tz, fmt=_pref_fmt)
            _log(bot).info('Saved pref for %s: tz=%s fmt=%s', trigger.nick, _pref_tz, _pref_fmt)
    except Exception:
        pass

    review_mode = bool(_REVIEW_INTENT_RE.search(user_message)) or (user_message.strip() == '^^')

    if not user_message:
        return

    if re.match(r'^[.!/]', user_message):
        return

    time_mode = bool(_TIME_INTENT_RE.search(user_message))

    now = time.time()
    if not time_mode:
        with chan_lock:
            last = bot.memory['grok_last'].get(trigger.sender, 0)
            if now - last < CHANNEL_RATE_LIMIT:
                return
            bot.memory['grok_last'][trigger.sender] = now
    else:
        with chan_lock:
            bot.memory['grok_last'][trigger.sender] = now

    if review_mode:
        review_last = bot.memory.setdefault('grok_review_last', {})
        last_review = review_last.get(trigger.sender, 0)
        if now - last_review < REVIEW_COOLDOWN:
            return
        review_last[trigger.sender] = now

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime('%A, %B %d, %Y at %H:%M UTC')
    # Use per-channel system prompt if defined, otherwise fall back to the global one.
    _active_system_prompt = bot.config.grok.system_prompt
    _channel_always_search = False
    if not is_pm:
        _ch_prompts = _load_channel_prompts()
        _ch_cfg = _ch_prompts.get(trigger.sender.lower())
        if _ch_cfg:
            _active_system_prompt = _ch_cfg["prompt"]
            _channel_always_search = _ch_cfg.get("always_search", False)
    messages = [
        {"role": "system", "content": _active_system_prompt},
        {
            "role": "system",
            "content": (
                f"Current date/time: {now_str}. "
                f"Your IRC nick is '{bot_nick}'. You're talking to {trigger.nick}. "
                f"You also run game/utility plugins ($ commands like $bet, $mug, $coins, etc.). "
                f"Messages from '{bot_nick}' in the channel log are things you said — reference "
                f"game events, coin balances, mug outcomes naturally when relevant. "
                f"For news or current events, search the web and give real details. "
                f"Include raw deep-link URLs for articles you cite (the system strips and reformats them). "
                f"Do NOT use markdown links. If you can't find an exact URL, don't make one up. "
                f"Single line only — this is IRC. No newlines."
            ),
        },
    ]

    relevant_turns = []
    if not review_mode:
        db_entries = _db_get_recent(bot, trigger.nick, limit=20)
        if db_entries:
            for role, text in db_entries:
                nick = bot_nick if role == 'assistant' else trigger.nick
                relevant_turns.append((nick, text))
        else:
            with chan_lock:
                history_snapshot = list(history)
            for entry in history_snapshot:
                try:
                    nick, text = entry.split(": ", 1)
                except ValueError:
                    continue
                if nick not in (trigger.nick, bot_nick):
                    continue
                relevant_turns.append((nick, text))
    else:
        channel_entries = []
        if is_pm:
            with chan_lock:
                dq = bot.memory.get('grok_history', {}).get(per_conv_key, None)
                if dq:
                    for item in list(dq):
                        try:
                            nick, text = item.split(": ", 1)
                        except Exception:
                            continue
                        channel_entries.append((nick, text))
        else:
            with chan_lock:
                chan_log_dq = bot.memory.get('grok_channel_log', {}).get(
                    trigger.sender.lower()
                )
                if chan_log_dq:
                    channel_entries = list(chan_log_dq)
        filtered = []
        for nick, text in channel_entries:
            t = text.strip()
            if not t:
                continue
            if re.search(r'https?://|\S+\.(com|net|org|io|gg)\b', t, re.IGNORECASE):
                continue
            if len(t.split()) <= 1 and len(t) <= 3:
                continue
            if re.match(r'^[^\w\s]+$', t):
                continue
            filtered.append((nick, t))
        char_budget = REVIEW_CHAR_BUDGET
        collected = []
        total_chars = 0
        for nick, text in reversed(filtered):
            l = len(text) + len(nick) + 3
            if total_chars + l > char_budget and collected:
                break
            collected.append((nick, text))
            total_chars += l
        collected.reverse()
        relevant_turns = collected

    if not review_mode:
        if not is_pm:
            try:
                channel_bg = []
                with chan_lock:
                    chan_log_dq = bot.memory.get('grok_channel_log', {}).get(
                        trigger.sender.lower()
                    )
                    if chan_log_dq:
                        channel_bg = list(chan_log_dq)
                unique_bg = channel_bg  # already in chronological order
                BG_MAX_LINES = 150
                bg_collected = []
                bg_chars = 0
                for n, t in reversed(unique_bg):
                    l = len(n) + len(t) + 3
                    if bg_chars + l > BG_CHAR_BUDGET and bg_collected:
                        break
                    if len(bg_collected) >= BG_MAX_LINES:
                        break
                    bg_collected.append((n, t))
                    bg_chars += l
                bg_collected.reverse()
                bg_lines = [f"{n}: {t}" for n, t in bg_collected]
                bg_text = "\n".join(bg_lines)
                if len(bg_text) > BG_CHAR_BUDGET:
                    bg_text = "... (older messages truncated)\n" + bg_text[-BG_CHAR_BUDGET + 30:]
                if bg_text:
                    messages.append({
                        "role": "system",
                        "content": (
                            "Recent channel conversation log (each line is 'nick: message'). "
                            "This includes ALL activity: user chat, $ commands (like $bet, $mug), "
                            f"and your own plugin outputs (lines from '{bot_nick}'). "
                            "When asked who said something or what a specific user said, "
                            "always answer accurately based on this log — name the correct nick. "
                            "Do not invent or attribute statements to yourself or the wrong person.\n\n"
                            + bg_text
                        ),
                    })
            except Exception:
                pass
        for nick, text in relevant_turns[-MAX_HISTORY_PER_USER:]:
            role = "assistant" if nick == bot_nick else "user"
            messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": user_message})
        try:
            _db_add_turn(bot, trigger.nick, 'user', user_message, 'PM' if is_pm else trigger.sender)
        except Exception:
            pass
    else:
        review_sys = (
            f"You are {bot_nick}, a real participant in this IRC channel — not a summarizer or a bot assistant. "
            "You have been reading the conversation and now someone is asking you to chime in. "
            "React like a person who actually read the whole backlog: engage with the topic, "
            "add your take, agree or push back, be funny or thoughtful — whatever fits naturally. "
            "Do NOT give a structured summary with headers, highlights, or suggestions. "
            "Do NOT say things like 'The conversation is about...' or 'Highlight:'. "
            "Just talk like you've been sitting in the channel the whole time. "
            "If the log is empty, say so briefly. Single line only — this is IRC."
        )
        messages.append({"role": "system", "content": review_sys})
        bg_lines = []
        for nick, text in relevant_turns[-REVIEW_MAX_ENTRIES:]:
            bg_lines.append(f"{nick}: {text}")
        background = "\n".join(bg_lines)
        combined = (
            "Channel conversation so far (chronological):\n" + background + "\n\n"
            + (f"{trigger.nick} is asking you to weigh in. User said: {user_message}" if user_message.strip() != '^^' else f"{trigger.nick} wants you to jump into the conversation.")
        )
        messages.append({"role": "user", "content": combined})

    try:
        search_mode = _channel_always_search or bool(_SEARCH_INTENT_RE.search(user_message))
        wants_sources = bool(_WANTS_SOURCES_RE.search(user_message))
        # If user is asking for sources/URLs, force search so the API returns real citations
        if wants_sources:
            search_mode = True
        if bot.memory['grok_busy'].get(trigger.sender, False):
            try:
                bot.say("Grok is still thinking — hang tight a sec.", trigger.sender)
            except Exception:
                pass
            return
        bot.memory['grok_busy'][trigger.sender] = True
        API_TASK_QUEUE.put_nowait((bot, trigger, messages, review_mode, is_pm, bot_nick, chan_lock, search_mode, wants_sources))
    except queue.Full:
        try:
            bot.say('Grok is super busy right now — try again in a minute?', trigger.sender)
        except Exception:
            pass
    except Exception:
        _log(bot).exception('Failed to enqueue Grok API task')

@plugin.command('testemote')
def testemote(bot, trigger):
    bot.say('Emote plugin loaded, bot nick: ' + bot.nick)

@plugin.command('grokreset')
def grokreset(bot, trigger):
    is_pm = _is_pm(trigger)
    try:
        arg = (trigger.group(2) or '').strip().lower()
    except Exception:
        arg = ''
    if is_pm:
        key = ('PM', trigger.nick.lower())
        try:
            gh = bot.memory.get('grok_history', {})
            if key in gh:
                del gh[key]
        except Exception:
            pass
        try:
            _db_clear_user(bot, trigger.nick)
        except Exception:
            pass
        try:
            bot.reply('Your Grok history has been reset.')
        except Exception:
            pass
        return
    # Admin/op reset for the current channel or a named channel
    if arg in {'channel', 'chan', 'all', '*'} or arg.startswith('#'):
        target_chan = arg if arg.startswith('#') else trigger.sender
        # Ops can only reset the channel they're in; admins can reset any channel
        if target_chan.lower() != trigger.sender.lower():
            if not _is_admin(bot, trigger):
                try:
                    bot.say('Only a bot admin may reset history for another channel.', trigger.sender)
                except Exception:
                    pass
                return
        else:
            if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
                try:
                    bot.say(
                        'Only a bot admin/owner or a channel operator may reset Grok history for a channel. '
                        'Use $grokreset (or $grokreset me) to reset only your history.',
                        trigger.sender,
                    )
                except Exception:
                    pass
                return
        keys = list(bot.memory.get('grok_history', {}).keys())
        for k in keys:
            try:
                if (isinstance(k, tuple) and k[0].lower() == target_chan.lower()) or (isinstance(k, str) and k.lower() == target_chan.lower()):
                    del bot.memory['grok_history'][k]
            except Exception:
                continue
        try:
            bot.say(f'Grok history reset for {target_chan}.', trigger.sender)
        except Exception:
            pass
        return
    try:
        keys = list(bot.memory.get('grok_history', {}).keys())
        for k in keys:
            try:
                if isinstance(k, tuple) and k[0] == trigger.sender and str(k[1]).lower() == trigger.nick.lower():
                    del bot.memory['grok_history'][k]
            except Exception:
                continue
    except Exception:
        pass
    try:
        _db_clear_user(bot, trigger.nick)
    except Exception:
        pass
    try:
        bot.reply('Your personal Grok history has been reset.')
    except Exception:
        pass

@plugin.command('talkback')
def talkback(bot, trigger):
    """Toggle unprompted chime-ins for this channel."""
    if _is_pm(trigger):
        bot.say("Talkback can only be configured in channels.")
        return

    # Check privileges: Op or higher
    if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
        bot.reply("Only channel operators or bot admins can change talkback settings.")
        return

    arg = (trigger.group(2) or '').strip().lower()
    channel = trigger.sender
    
    if arg in ('on', 'enable', 'true', '1'):
        if _db_set_channel_talkback(bot, channel, True):
            bot.say(f"Talkback is now enabled for {channel}.")
        else:
            bot.say("Failed to update talkback setting.")
    elif arg in ('off', 'disable', 'false', '0'):
        if _db_set_channel_talkback(bot, channel, False):
            bot.say(f"Talkback is now disabled for {channel}.")
        else:
            bot.say("Failed to update talkback setting.")
    else:
        # Show current status
        current = _db_get_channel_talkback(bot, channel)
        status = "enabled" if current else "disabled"
        bot.say(f"Talkback is currently {status} for {channel}. Use '.talkback on' or '.talkback off' to change it.")

@plugin.command('ai')
def ai_toggle(bot, trigger):
    """Enable or disable Grok AI for this channel."""
    if _is_pm(trigger):
        bot.say("AI status can only be configured in channels.")
        return

    # Check privileges: Op or higher
    if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
        bot.reply("Only channel operators or bot admins can change AI status.")
        return

    arg = (trigger.group(2) or '').strip().lower()
    channel = trigger.sender
    
    if arg in ('on', 'enable', 'true', '1'):
        if _db_set_channel_enabled(bot, channel, True):
            bot.say(f"Grok AI is now ENABLED for {channel}.")
        else:
            bot.say("Failed to update AI status.")
    elif arg in ('off', 'disable', 'false', '0'):
        if _db_set_channel_enabled(bot, channel, False):
            bot.say(f"Grok AI is now DISABLED for {channel}. I will no longer respond to mentions or chime in here.")
        else:
            bot.say("Failed to update AI status.")
    else:
        # Show current status
        current = _db_get_channel_enabled(bot, channel)
        status = "ENABLED" if current else "DISABLED"
        bot.say(f"Grok AI is currently {status} for {channel}. Use '.ai on' or '.ai off' to change it.")

# Force reload
