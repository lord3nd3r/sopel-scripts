# grok.py — v6.0: memory-safe refactor, proper shutdown, thread-safe caches
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
from zoneinfo import ZoneInfo


class _BoundedTTLCache:
    """Thread-safe bounded cache with TTL eviction.

    Used for dedup keys, per-user timestamps, and other ephemeral data
    that must not grow without bound.
    """
    __slots__ = ('_data', '_lock', '_maxsize', '_ttl')

    def __init__(self, maxsize=2000, ttl=60.0):
        self._data = {}        # key -> (value, expiry)
        self._lock = threading.Lock()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key, default=None):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            val, expiry = entry
            if time.monotonic() > expiry:
                del self._data[key]
                return default
            return val

    def set(self, key, value):
        now = time.monotonic()
        with self._lock:
            self._data[key] = (value, now + self._ttl)
            if len(self._data) > self._maxsize:
                self._evict(now)

    def check_and_set(self, key, value, window):
        """Atomically check if key was set within `window` seconds, then set it.

        Returns True if the key already exists within the window (duplicate).
        Returns False if freshly set (first occurrence).
        """
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is not None:
                val, expiry = entry
                if now <= expiry and now - val < window:
                    return True  # duplicate
            self._data[key] = (value, now + self._ttl)
            if len(self._data) > self._maxsize:
                self._evict(now)
            return False  # fresh

    def _evict(self, now):
        # Remove all expired entries
        expired = [k for k, (_, exp) in self._data.items() if now > exp]
        for k in expired:
            del self._data[k]
        # If still over capacity, remove oldest entries
        if len(self._data) > self._maxsize:
            by_age = sorted(self._data.items(), key=lambda kv: kv[1][1])
            to_remove = len(self._data) - (self._maxsize // 2)
            for k, _ in by_age[:to_remove]:
                del self._data[k]

    def __len__(self):
        return len(self._data)

# Tunables / constants
MAX_SEND_LEN = 440
SEND_DELAY = 1.0
CHANNEL_RATE_LIMIT = 4
REVIEW_COOLDOWN = 30
USER_SAFETY_SECONDS = 2
API_QUEUE_MAXSIZE = 50
API_WORKER_COUNT = 3  # Number of parallel API request threads

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
    r'\b(?:show\s+(?:me\s+)?(?:the\s+)?(?:links?|sources?|citations?|refs?|references?|urls?)'
    r'|give\s+(?:me\s+)?(?:the\s+)?(?:links?|sources?|citations?|refs?|references?|urls?)'
    r'|i\s+want\s+(?:the\s+)?(?:links?|sources?|citations?|refs?|references?|urls?)'
    r'|include\s+(?:the\s+)?(?:links?|sources?|citations?|refs?|references?|urls?)'
    r'|with\s+(?:the\s+)?(?:links?|sources?|citations?|refs?|references?|urls?)'
    r'|sources?\s*\??\s*$'
    r'|links?\s*\??\s*$)',
    re.IGNORECASE,
)

_TIME_INTENT_RE = re.compile(
    r'\b(what(?:\s+is|s|\u2019s)?\s+(the\s+)?(time|date|day)|'
    r'current\s+(time|date)|what\s+time|what\s+day|today(?:\s+is|\s+the\s+date|s\s+date)|'
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

# Match channel-wide personality: must explicitly say "in this channel" or "for everyone"
_PERSONALITY_CHANNEL_INDICATOR_RE = re.compile(
    r'\b(?:in (?:this |the )?channel|for everyone|for (?:the )?whole channel|channel[- ]?wide|to everyone)\b',
    re.IGNORECASE,
)

# Match personality command (defaults to per-user unless channel indicator present)
_PERSONALITY_COMMAND_RE = re.compile(
    r'\b(?:role\s*play|roleplay|pretend(?:\s+to\s+be)?|act\s+(?:like|as)|be|become|'
    r'speak|talk|reply|respond)\s+'
    r'(?:to\s+(?:me\s+)?)?(?:from now on\s+)?(?:as(?:\s+if)?|like|in)?\s*'
    r'(?:a\s+|an\s+)?(.+?)(?:\.|$)',
    re.IGNORECASE,
)

# Match per-user personality with explicit target: "speak to burnout like..."
_PERSONALITY_USER_TARGET_RE = re.compile(
    r'\b(?:speak|talk|reply|respond)\s+(?:to|with)\s+(\w+)\s+(?:like|as(?:\s+if)?|in)\s+(.+?)(?:\.|$)',
    re.IGNORECASE,
)

_PERSONALITY_RESET_RE = re.compile(
    r'\b(?:stop|quit|end|reset|clear|remove|cancel|revert|go back to normal|be normal|'
    r'be yourself|default|original)\s+'
    r'(?:the\s+)?(?:roleplay|personality|character|act|acting|pretending|persona|mode)\b',
    re.IGNORECASE,
)

# Persistent memory: "remember X" stores facts, "forget X" removes them
_REMEMBER_CMD_RE = re.compile(
    r'^remember\s+(?:that\s+)?(.+)',
    re.IGNORECASE | re.DOTALL,
)
# Conversational "remember" — NOT a command, let it go to the AI
_REMEMBER_SKIP_RE = re.compile(
    r'^remember\s+(?:when\b|how\b|the\s+time\b|that\s+time\b|that\s+one\s+time\b)',
    re.IGNORECASE,
)
_FORGET_CMD_RE = re.compile(
    r'^forget\s+(?:that\s+|about\s+)?(.+)',
    re.IGNORECASE | re.DOTALL,
)
_WHAT_REMEMBER_RE = re.compile(
    r'what\s+do\s+you\s+(?:remember|know)\s+about\s+(?:me\b|(\w+))',
    re.IGNORECASE,
)

# Max persistent facts per user
MAX_USER_FACTS = 50

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
    r'i(?:\'m| am)\s+in|i\s+(?:use|prefer|set|changed\s+to|want)\s+(?:my\s+)?(?:tz|timezone|time\s*zone)?|'
    r'(?:use|prefer|set|change|using)\s+(?:my\s+)?(?:tz|timezone|time\s*zone)?)\b'
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
# Semaphore to limit concurrent background tasks (learning, scheck) to 2
_BG_TASK_SEMAPHORE = threading.Semaphore(2)

def _api_worker_loop():
    """Main loop for API worker threads. Tasks are dicts with named keys."""
    while not API_WORKER_SHUTDOWN:
        try:
            task = API_TASK_QUEUE.get(timeout=0.5)
            if task is None:
                break
            try:
                _api_worker(**task)
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
    api_key = types.ValidatedAttribute('api_key')
    model = types.ChoiceAttribute(
        'model',
        choices=['grok-4-1-fast-reasoning', 'grok-4-fast-reasoning', 'grok-4-20', 'grok-4.3', 'grok-3', 'grok-beta'],
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

def _read_api_key_raw(bot):
    """Read API key directly from the config file, bypassing the sopel shim which masks SecretAttribute values."""
    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(bot.config.filename)
        return cfg.get('grok', 'api_key', fallback=None)
    except Exception:
        return None

def setup(bot):
    bot.config.define_section('grok', GrokSection)
    # Read API key directly from the underlying configparser - the ibot shim
    # wraps returned values in objects whose __str__ returns '***' for security.
    _raw_key = None
    for _getter in (
        lambda: bot.config.parser.get('grok', 'api_key'),
        lambda: bot.config.grok._parser.get('grok', 'api_key'),
        lambda: str(bot.config.grok.api_key),
    ):
        try:
            v = _getter()
            if v and v not in ('***', 'None', 'none'):
                _raw_key = v
                break
        except Exception:
            pass
    _log(bot).info('setup: api_key_present=%s key_len=%d', bool(_raw_key), len(_raw_key) if _raw_key else 0)

    # Close any previous session (handles plugin reload gracefully)
    old_session = bot.memory.get('grok_session')
    if old_session:
        try:
            old_session.close()
        except Exception:
            pass

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=2
    )
    session.mount('https://', adapter)
    session.headers.update({
        "Authorization": f"Bearer {_raw_key}",
        "Content-Type": "application/json",
    })
    bot.memory['grok_session'] = session

    # Per-conversation rolling history & last-response time
    bot.memory['grok_history'] = {}
    bot.memory['grok_last'] = {}
    bot.memory['grok_locks'] = {}
    bot.memory['grok_locks_lock'] = threading.Lock()
    bot.memory['grok_channel_log'] = {}  # per-channel chronological message log
    bot.memory['grok_say_lock'] = threading.Lock()  # thread-safe say wrapper lock
    bot.memory['grok_api_failures'] = {}  # circuit breaker: channel -> failure count
    bot.memory['grok_chimein_last'] = {}  # per-channel last chime-in timestamp
    bot.memory['grok_channel_personality'] = {}  # per-channel dynamic personality overrides
    bot.memory['grok_user_personality'] = {}  # per-user personalities: {channel: {nick: personality}}
    # Bounded TTL caches for ephemeral data (replaces unbounded bot.memory keys)
    bot.memory['grok_dedup_cache'] = _BoundedTTLCache(maxsize=2000, ttl=2.0)
    bot.memory['grok_user_last_cache'] = _BoundedTTLCache(maxsize=5000, ttl=300.0)
    bot.memory['grok_learn_counters'] = {}  # per-channel learn counter (bounded by # channels)

    # Wrap bot.say so ALL bot output (from every plugin) is captured in channel log.
    # This lets the AI see game results, mug outcomes, bet payouts, etc.
    # Guard against stacking on reload: only wrap if not already wrapped.
    if not hasattr(bot, '_grok_original_say'):
        bot._grok_original_say = bot.say
    _original_say = bot._grok_original_say

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
    global API_WORKER_SHUTDOWN
    API_WORKER_SHUTDOWN = False
    for _ in range(API_WORKER_COUNT):
        t = threading.Thread(target=_api_worker_loop, daemon=True)
        t.start()


def shutdown(bot):
    """Sopel calls this on plugin unload/reload. Clean up all resources."""
    global API_WORKER_SHUTDOWN
    API_WORKER_SHUTDOWN = True

    # Send poison pills to stop workers
    for _ in range(API_WORKER_COUNT):
        try:
            API_TASK_QUEUE.put_nowait(None)
        except queue.Full:
            pass

    # Drain any remaining tasks
    try:
        while not API_TASK_QUEUE.empty():
            API_TASK_QUEUE.get_nowait()
            API_TASK_QUEUE.task_done()
    except queue.Empty:
        pass

    # Close the HTTP session
    session = bot.memory.pop('grok_session', None)
    if session:
        try:
            session.close()
        except Exception:
            pass

    # Restore original bot.say to prevent stacking on reload
    original = getattr(bot, '_grok_original_say', None)
    if original:
        bot.say = original
        del bot._grok_original_say

    _log(bot).info('Grok plugin shut down cleanly')


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
    conn = sqlite3.connect(path, timeout=30.0)
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_user_profiles (
            nick TEXT PRIMARY KEY,
            nationality TEXT,
            location TEXT,
            weather_location TEXT,
            facts TEXT,
            last_updated TEXT,
            updated_by TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS grok_profile_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nick TEXT NOT NULL,
            fact TEXT NOT NULL,
            confidence REAL,
            source_context TEXT,
            suggested_ts TEXT,
            reviewed INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 0
        )
    ''')
    try:
        c.execute('ALTER TABLE grok_channel_settings ADD COLUMN enabled INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    conn.commit()
    # Enable WAL mode for better concurrent read/write access
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.close()

def _db_conn(bot):
    path = bot.memory.get('grok_db_path')
    if not path:
        raise RuntimeError('DB path not set')
    return sqlite3.connect(path, timeout=30.0, check_same_thread=False)

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

def _call_responses_api(bot, messages, model, temp, max_toks, search_mode=False, conv_id=None):
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

    session = bot.memory.get('grok_session')
    if not session:
        session = requests.Session()
    
    headers = {}
    if conv_id:
        headers["x-grok-conv-id"] = conv_id

    r = session.post(
        "https://api.x.ai/v1/responses",
        headers=headers,
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
            
    # URL extraction: scan the raw JSON response for all URLs.
    try:
        raw_json_str = json.dumps(data, default=str)
        raw_urls = re.findall(r'https?://[^\s()<>\[\]{}"]+', raw_json_str)
        for u in raw_urls:
            u = u.replace('\\/', '/').strip(').,;:!?\'">')
            if u and 'x.ai' not in u.lower() and 'google.com' not in u.lower():
                citations.append({"url": u, "title": ""})
    except Exception as e:
        _log(bot).error('URL extraction failed: %s', str(e))

    # Cleanup and dedupe raw extraction
    seen_raw = set()
    cleaned_citations = []
    for c in citations:
        u = c['url'].strip()
        if not u:
            continue
        u_low = u.lower().rstrip('/')
        if u_low not in seen_raw:
            existing = next((x for x in cleaned_citations if x['url'].lower().rstrip('/') == u_low), None)
            if existing:
                if not existing['title'] and c['title']:
                    existing['title'] = c['title']
                continue
            seen_raw.add(u_low)
            cleaned_citations.append(c)
    citations = cleaned_citations

    _log(bot).debug('API citations extracted: %d', len(citations))
    return reply.strip(), citations

def _url_to_title(url):
    """Generate a fallback title from a URL slug."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        slug = p.path.strip('/').split('/')[-1]
        if not slug or '.' in slug:
            return p.netloc
        return slug.replace('-', ' ').replace('_', ' ').title()
    except Exception:
        return ""

def _api_worker(*, bot, trigger, messages, review_mode, is_pm, bot_nick, chan_lock, search_mode=False, wants_sources=False, is_chimein=False, is_action=False):
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

        conv_id = None
        if is_pm:
            conv_id = f"pm-{trigger.nick.lower()}"
        else:
            conv_id = f"chan-{trigger.sender.lower()}-{trigger.nick.lower()}"

        for attempt in range(1, attempts + 1):
            try:
                reply, citations = _call_responses_api(
                    bot, messages, model, temp, max_toks,
                    search_mode=search_mode, conv_id=conv_id,
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
            except requests.exceptions.HTTPError as e:
                if attempt < attempts:
                    time.sleep(backoff + random.random() * 0.5)
                    backoff *= 2
                else:
                    _log(bot).exception('Grok API final attempt failed (HTTP error)')
                    try:
                        _log(bot).error('API 400 response body: %s', e.response.text[:500] if e.response is not None else 'no body')
                    except Exception:
                        pass
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
                reply += ' (no sources found)'

        try:
            _ulc = bot.memory.get('grok_user_last_cache')
            if _ulc:
                _ulc_key = f"{trigger.sender}:{trigger.nick}"
                _last_ts = _ulc.get(_ulc_key, 0)
                if time.time() - _last_ts < USER_SAFETY_SECONDS:
                    return
                _ulc.set(_ulc_key, time.time())
        except Exception:
            pass

        if review_mode:
            pass  # no canned prefix — let the AI speak naturally

        try:
            reply = re.sub(rf'^\s*{re.escape(bot_nick)}[,:>\s]+', '', reply, flags=re.IGNORECASE)
        except Exception:
            pass

        # Detect action-style replies: AI responded with a third-person verb
        # e.g. "farts on End3r", "hugs End3r warmly", "waves at everyone"
        # These should be sent as /me actions, not prefixed with the requester's nick.
        _reply_is_action = bool(re.match(
            r'^[a-z]+(?:e?s)?\s+(?:on|at|to|toward|with|for|from|around|into)\s',
            reply
        ))

        if is_action or _reply_is_action:
            final_reply = reply
        elif not is_chimein and trigger.nick.lower() not in reply.lower() and not _is_owner(bot, trigger):
            final_reply = f"{trigger.nick}: {reply}"
        else:
            final_reply = reply

        # Humanizing delay: pause before sending to simulate reading + typing
        _typing_delay = random.uniform(TYPING_DELAY_MIN, TYPING_DELAY_MAX)
        time.sleep(_typing_delay)

        if is_action or _reply_is_action:
            bot.action(final_reply, trigger.sender)
        else:
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
        pass

def _db_get_recent(bot, nick, channel=None, limit=MAX_HISTORY_PER_USER):
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            if channel:
                c.execute(
                    'SELECT role, text FROM grok_user_history WHERE nick = ? AND source = ? ORDER BY id DESC LIMIT ?',
                    (nick.lower(), channel, limit),
                )
            else:
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

# ==================== USER PROFILE FUNCTIONS ====================

def _db_get_user_profile(bot, nick):
    """Retrieve user profile data. Returns dict with nationality, location, weather_location, and facts (list)."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT nationality, location, weather_location, facts, last_updated, updated_by '
                'FROM grok_user_profiles WHERE nick = ?',
                (nick.lower(),)
            )
            row = c.fetchone()
            if not row:
                return None
            profile = {
                'nationality': row[0],
                'location': row[1],
                'weather_location': row[2],
                'facts': json.loads(row[3]) if row[3] else [],
                'last_updated': row[4],
                'updated_by': row[5]
            }
            return profile
    except Exception:
        _log(bot).exception('Failed to get profile for %s', nick)
        return None

def _db_update_profile_field(bot, nick, field, value, updated_by):
    """Update a specific profile field (nationality, location, weather_location)."""
    valid_fields = {'nationality', 'location', 'weather_location'}
    if field not in valid_fields:
        return False
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            # Check if profile exists
            c.execute('SELECT nick FROM grok_user_profiles WHERE nick = ?', (nick.lower(),))
            exists = c.fetchone()
            now_ts = datetime.datetime.utcnow().isoformat()
            if exists:
                c.execute(
                    f'UPDATE grok_user_profiles SET {field} = ?, last_updated = ?, updated_by = ? WHERE nick = ?',
                    (value, now_ts, updated_by.lower(), nick.lower())
                )
            else:
                # Create new profile
                c.execute(
                    'INSERT INTO grok_user_profiles (nick, nationality, location, weather_location, facts, last_updated, updated_by) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (nick.lower(), 
                     value if field == 'nationality' else None,
                     value if field == 'location' else None,
                     value if field == 'weather_location' else None,
                     json.dumps([]),
                     now_ts,
                     updated_by.lower())
                )
            return True
    except Exception:
        _log(bot).exception('Failed to update profile field for %s', nick)
        return False

def _db_add_profile_fact(bot, nick, fact, updated_by):
    """Add a fact to user's profile. Returns True if successful."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT facts FROM grok_user_profiles WHERE nick = ?', (nick.lower(),))
            row = c.fetchone()
            now_ts = datetime.datetime.utcnow().isoformat()
            
            if row:
                facts = json.loads(row[0]) if row[0] else []
                if fact not in facts:
                    facts.append(fact)
                    c.execute(
                        'UPDATE grok_user_profiles SET facts = ?, last_updated = ?, updated_by = ? WHERE nick = ?',
                        (json.dumps(facts), now_ts, updated_by.lower(), nick.lower())
                    )
            else:
                # Create new profile with this fact
                c.execute(
                    'INSERT INTO grok_user_profiles (nick, facts, last_updated, updated_by) VALUES (?, ?, ?, ?)',
                    (nick.lower(), json.dumps([fact]), now_ts, updated_by.lower())
                )
            return True
    except Exception:
        _log(bot).exception('Failed to add fact for %s', nick)
        return False

def _db_remove_profile_fact(bot, nick, fact_index):
    """Remove a fact by index. Returns True if successful."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('SELECT facts FROM grok_user_profiles WHERE nick = ?', (nick.lower(),))
            row = c.fetchone()
            if not row:
                return False
            facts = json.loads(row[0]) if row[0] else []
            if 0 <= fact_index < len(facts):
                facts.pop(fact_index)
                now_ts = datetime.datetime.utcnow().isoformat()
                c.execute(
                    'UPDATE grok_user_profiles SET facts = ?, last_updated = ? WHERE nick = ?',
                    (json.dumps(facts), now_ts, nick.lower())
                )
                return True
            return False
    except Exception:
        _log(bot).exception('Failed to remove fact for %s', nick)
        return False

def _db_delete_user_profile(bot, nick):
    """Delete entire profile for a user."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM grok_user_profiles WHERE nick = ?', (nick.lower(),))
            return True
    except Exception:
        _log(bot).exception('Failed to delete profile for %s', nick)
        return False

def _format_profile_for_context(nick, profile, include_facts=True):
    """Format user profile data for inclusion in AI context."""
    if not profile:
        return None
    parts = []
    if profile.get('nationality'):
        parts.append(f"Nationality: {profile['nationality']}")
    if profile.get('location'):
        parts.append(f"Location: {profile['location']}")
    if profile.get('weather_location'):
        parts.append(f"Weather location: {profile['weather_location']}")
    if include_facts and profile.get('facts'):
        facts_formatted = "\n- ".join(profile['facts'])
        parts.append(f"Notable facts:\n- {facts_formatted}")
    
    if not parts:
        return None
    
    return f"Profile for {nick}: {', '.join(parts)}"

# ==================== PROFILE SUGGESTION FUNCTIONS ====================

def _db_add_fact_suggestion(bot, nick, fact, confidence, context):
    """Store a suggested fact for later review. Confidence is 0.0-1.0."""
    auto_approve = False
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            # Check if similar fact already exists (pending or approved)
            c.execute(
                'SELECT id FROM grok_profile_suggestions WHERE nick = ? AND fact = ? AND reviewed = 0',
                (nick.lower(), fact)
            )
            if c.fetchone():
                return False  # Already suggested
            
            now_ts = datetime.datetime.utcnow().isoformat()
            c.execute(
                'INSERT INTO grok_profile_suggestions (nick, fact, confidence, source_context, suggested_ts) '
                'VALUES (?, ?, ?, ?, ?)',
                (nick.lower(), fact, confidence, context, now_ts)
            )
            
            # Mark as approved in suggestions table, but defer the profile write
            # until AFTER this connection closes to avoid a nested-connection deadlock.
            if confidence >= 0.9:
                suggestion_id = c.lastrowid
                c.execute(
                    'UPDATE grok_profile_suggestions SET reviewed = 1, approved = 1 WHERE id = ?',
                    (suggestion_id,)
                )
                auto_approve = True
        # Outer connection is now committed and closed — safe to open a new one.
        if auto_approve:
            _db_add_profile_fact(bot, nick, fact, 'auto-learned')
        return True
    except Exception:
        _log(bot).exception('Failed to add fact suggestion for %s', nick)
        return False

def _db_get_pending_suggestions(bot, limit=20):
    """Get pending fact suggestions that haven't been reviewed."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT id, nick, fact, confidence, source_context, suggested_ts '
                'FROM grok_profile_suggestions WHERE reviewed = 0 ORDER BY confidence DESC, id ASC LIMIT ?',
                (limit,)
            )
            rows = c.fetchall()
            return [
                {
                    'id': r[0],
                    'nick': r[1],
                    'fact': r[2],
                    'confidence': r[3],
                    'context': r[4],
                    'suggested_ts': r[5]
                }
                for r in rows
            ]
    except Exception:
        _log(bot).exception('Failed to get pending suggestions')
        return []

def _db_approve_suggestion(bot, suggestion_id, approver):
    """Approve a fact suggestion and add it to the user's profile.
    
    The profile write is deferred until after the suggestion connection closes
    to avoid a nested-connection deadlock with SQLite.
    """
    nick = fact = None
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'SELECT nick, fact FROM grok_profile_suggestions WHERE id = ? AND reviewed = 0',
                (suggestion_id,)
            )
            row = c.fetchone()
            if not row:
                return False
            
            nick, fact = row
            c.execute(
                'UPDATE grok_profile_suggestions SET reviewed = 1, approved = 1 WHERE id = ?',
                (suggestion_id,)
            )
    except Exception:
        _log(bot).exception('Failed to approve suggestion %s', suggestion_id)
        return False
    # Connection is now closed — safe to open a new one for the profile write
    if nick and fact:
        _db_add_profile_fact(bot, nick, fact, approver)
    return True

def _db_reject_suggestion(bot, suggestion_id):
    """Reject a fact suggestion."""
    try:
        with _DBContext(bot) as conn:
            c = conn.cursor()
            c.execute(
                'UPDATE grok_profile_suggestions SET reviewed = 1, approved = 0 WHERE id = ?',
                (suggestion_id,)
            )
            return True
    except Exception:
        _log(bot).exception('Failed to reject suggestion %s', suggestion_id)
        return False

def _extract_facts_from_conversation(bot, channel_log, user_nick):
    """Use AI to extract facts about a user from recent conversation. Returns list of (fact, confidence) tuples."""
    # This is called periodically to analyze conversation and extract facts
    if not channel_log or len(channel_log) < 5:
        _log(bot).debug('Not enough conversation history for fact extraction (need 5+ messages)')
        return []
    
    # Build a prompt asking the AI to extract facts
    log_text = '\n'.join([f"{nick}: {text}" for nick, text in channel_log[-30:]])
    
    extraction_prompt = f"""Analyze this IRC conversation log and extract factual information about the user '{user_nick}'.

Conversation log:
{log_text}

Extract clear, factual statements about {user_nick}. Examples of good facts:
- "is from Canada"
- "plays Counter-Strike"
- "works as a software developer"
- "speaks French"
- "hates pineapple on pizza"

Return ONLY a JSON array of facts with confidence scores (0.0-1.0), like:
[{{"fact": "is from Canada", "confidence": 0.95}}, {{"fact": "plays CS:GO", "confidence": 0.8}}]

If no clear facts can be extracted, return an empty array: []

Rules:
- Only include facts explicitly stated or strongly implied
- Use confidence 0.9+ only for direct statements
- Be concise (under 10 words per fact)
- Avoid opinions unless clearly stated as theirs
- Skip temporary states (e.g., "is tired")"""

    try:
        # Use the shared session (which has auth headers set in setup)
        session = bot.memory.get('grok_session')
        if not session:
            _log(bot).warning('No Grok session available for fact extraction')
            return []
        
        model = bot.config.grok.model
        _log(bot).info('Extracting facts for %s from %d messages using model %s', user_nick, len(channel_log), model)
            
        response = session.post(
            'https://api.x.ai/v1/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': extraction_prompt}],
                'temperature': 0.3,
                'max_tokens': 500
            },
            timeout=15
        )
        
        _log(bot).debug('Fact extraction API response status: %d', response.status_code)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            _log(bot).info('Fact extraction response for %s: %s', user_nick, content[:500])
            
            # Store for debugging
            bot.memory['_last_fact_extraction_response'] = content
            
            # Try to extract JSON from the response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                _log(bot).debug('Found JSON: %s', json_str[:300])
                try:
                    facts_data = json.loads(json_str)
                    extracted = [(f['fact'], f['confidence']) for f in facts_data if isinstance(f, dict) and 'fact' in f and 'confidence' in f]
                    _log(bot).info('Extracted %d facts for %s: %s', len(extracted), user_nick, extracted)
                    return extracted
                except json.JSONDecodeError as e:
                    _log(bot).error('Failed to parse JSON: %s', str(e))
            else:
                _log(bot).warning('No JSON array found in fact extraction response. Full response: %s', content)
        else:
            _log(bot).error('Fact extraction API error: %d - %s', response.status_code, response.text[:200])
            
    except requests.exceptions.Timeout:
        _log(bot).error('Fact extraction timed out for %s', user_nick)
    except requests.exceptions.RequestException as e:
        _log(bot).exception('Request failed during fact extraction for %s: %s', user_nick, str(e))
    except json.JSONDecodeError as e:
        _log(bot).exception('Failed to parse JSON in fact extraction for %s: %s', user_nick, str(e))
    except Exception as e:
        _log(bot).exception('Unexpected error during fact extraction for %s: %s', user_nick, str(e))
    
    return []

# ==================== END PROFILE SUGGESTION FUNCTIONS ====================

# ==================== END USER PROFILE FUNCTIONS ====================


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

def _db_set_user_pref(bot, nick, tz=None, tz_label=None, fmt=None):
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
            new_label = tz_label if tz_label is not None else (cur_label if cur_label else new_iana)
            new_fmt = fmt if fmt is not None else cur_fmt
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

@plugin.rule('.*')
@plugin.priority('high')
def handle(bot, trigger):
    # Uses bounded TTL cache instead of polluting bot.memory with unbounded keys.
    _dedup_key = f'{trigger.nick}:{trigger.sender}:{trigger.group(0)[:40]}'
    _now = time.monotonic()
    _dedup_cache = bot.memory.get('grok_dedup_cache')
    if _dedup_cache:
        if _dedup_cache.check_and_set(_dedup_key, _now, 5.0):
            return  # duplicate — already handled

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
                
                # Auto-learning: periodically extract facts about active users
                _learn_counters = bot.memory.get('grok_learn_counters', {})
                _learn_count = _learn_counters.get(_cl_key, 0) + 1
                _learn_counters[_cl_key] = _learn_count
                
                # Every 100 messages, pick a random active user and try to learn facts
                if _learn_count >= 100:
                    _learn_counters[_cl_key] = 0
                    
                    # Find active users (who have spoken at least 5 times in recent history)
                    nick_counts = {}
                    for n, _ in list(_cl_dq)[-100:]:
                        if n.lower() not in own_nicks:
                            nick_counts[n] = nick_counts.get(n, 0) + 1
                    
                    active_users = [n for n, count in nick_counts.items() if count >= 5]
                    if active_users:
                        target_user = random.choice(active_users)
                        _snapshot = list(_cl_dq)
                        _sender = trigger.sender
                        
                        # Run fact extraction with semaphore to limit concurrent background tasks
                        def _background_learn(_user=target_user, _log_snapshot=_snapshot, _chan=_sender):
                            if not _BG_TASK_SEMAPHORE.acquire(blocking=False):
                                return  # Skip if too many background tasks already running
                            try:
                                facts = _extract_facts_from_conversation(bot, _log_snapshot, _user)
                                for fact, confidence in facts:
                                    context = f"Auto-learned from {_chan}"
                                    _db_add_fact_suggestion(bot, _user, fact, confidence, context)
                            except Exception:
                                _log(bot).exception('Background fact learning failed for %s', _user)
                            finally:
                                _BG_TASK_SEMAPHORE.release()
                        
                        learn_thread = threading.Thread(target=_background_learn, daemon=True)
                        learn_thread.start()
                        
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
                        # Skip chime-in on short greetings directed at other users
                        # e.g. "hey owo o/", "yo burnout", "hi there nick"
                        _chimein_skip = False
                        if len(text_for_history.split()) <= 5:
                            _greeting_m = re.match(
                                r'^(?:hey|hi|hello|yo|sup|wb|welcome back|o/|\\o)\s+(\S+)',
                                text_for_history, re.IGNORECASE,
                            )
                            if _greeting_m:
                                _greeted = _greeting_m.group(1).strip(',:!?').lower()
                                if _greeted != bot.nick.lower():
                                    _chimein_skip = True
                        if not _chimein_skip and random.random() * 100 < _chance:
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
                                "Single line only — this is IRC. "
                                "IMPORTANT: You only know what has been said in THIS channel's recent log shown below. "
                                "Do NOT reference events, facts, or conversations from other channels."
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
                                API_TASK_QUEUE.put_nowait({
                                    'bot': bot, 'trigger': trigger, 'messages': _chimein_msgs,
                                    'review_mode': False, 'is_pm': False,
                                    'bot_nick': _bot_nick, 'chan_lock': _chimein_lock,
                                    'search_mode': False, 'wants_sources': False,
                                    'is_chimein': True, 'is_action': False,
                                })
                            except queue.Full:
                                pass
                            except Exception:
                                pass
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

    # ========== INSTANT CONFIG COMMANDS (no rate limiting, no busy check) ==========
    # These are processed immediately and return early - they don't queue API calls

    # Persistent memory: remember / forget / what do you remember
    # This MUST come before timezone/personality handlers which could intercept
    # messages containing "remember I prefer 12h..." etc.
    _um_stripped = (user_message or '').strip()

    # --- "remember X" ---
    if _um_stripped and _REMEMBER_CMD_RE.match(_um_stripped) and not _REMEMBER_SKIP_RE.match(_um_stripped):
        _rem_match = _REMEMBER_CMD_RE.match(_um_stripped)
        _fact = _rem_match.group(1).strip().rstrip('.')
        if _fact and len(_fact) >= 5:
            # Always store in the speaker's own profile — these are personal notes
            # (including notes about other people, e.g. "ComputerTech is the sheep shagger")
            try:
                if len(_fact) > 300:
                    bot.say("that's a bit much — keep it under 300 chars?", trigger.sender)
                    return
                _existing_profile = _db_get_user_profile(bot, trigger.nick)
                _existing_facts = (_existing_profile or {}).get('facts', [])
                if len(_existing_facts) >= MAX_USER_FACTS:
                    bot.say("I'm remembering too many things already — try telling me to forget something first", trigger.sender)
                    return
                # Check for duplicate
                _fact_lower = _fact.lower()
                if any(_fact_lower == f.lower() for f in _existing_facts):
                    bot.say("yeah, I've already got that", trigger.sender)
                    return
                _saved = _db_add_profile_fact(bot, trigger.nick, _fact, trigger.nick)
                _log(bot).info('Remember: nick=%s saved=%s fact=%s', trigger.nick, _saved, _fact[:80])
                # Also extract and save any embedded timezone/format preferences
                try:
                    _mtz = _TZ_SET_RE.search(user_message)
                    if _mtz:
                        _abbr = _mtz.group(1).upper()
                        _iana = _TZ_ABBR_MAP.get(_abbr)
                        if _iana:
                            _db_set_user_pref(bot, trigger.nick, tz=_iana, tz_label=_abbr)
                    _mfmt = _FMT_SET_RE.search(user_message)
                    if _mfmt:
                        _raw = _mfmt.group(1).lower().replace(' ', '').replace('-', '')
                        _pref_fmt = '12' if _raw.startswith('12') else '24'
                        _db_set_user_pref(bot, trigger.nick, fmt=_pref_fmt)
                except Exception:
                    pass
            except Exception:
                _log(bot).exception('Remember handler DB error')
            # Always try to reply and always return — even if say fails
            try:
                _responses = [
                    "got it, I'll remember that",
                    "noted",
                    "saved, won't forget",
                    "locked in",
                    "k I'll remember",
                    "remembered",
                ]
                bot.say(random.choice(_responses), trigger.sender)
            except Exception:
                _log(bot).exception('Remember handler bot.say failed')
                try:
                    bot.reply("saved")
                except Exception:
                    pass
            return

    # --- "forget X" / "forget everything" ---
    if _um_stripped:
        _forget_match = _FORGET_CMD_RE.match(_um_stripped)
    else:
        _forget_match = None
    if _forget_match:
        _forget_what = _forget_match.group(1).strip().lower()
        _reply_msg = None
        try:
            if _forget_what in ('everything', 'all', 'it all', 'all of it', 'everything about me'):
                _existing_profile = _db_get_user_profile(bot, trigger.nick)
                if _existing_profile and _existing_profile.get('facts'):
                    with _DBContext(bot) as conn:
                        c = conn.cursor()
                        c.execute(
                            'UPDATE grok_user_profiles SET facts = ? WHERE nick = ?',
                            (json.dumps([]), trigger.nick.lower())
                        )
                    _reply_msg = "done, forgot everything"
                else:
                    _reply_msg = "I don't have anything saved about you"
            else:
                # Fuzzy match against existing facts
                _existing_profile = _db_get_user_profile(bot, trigger.nick)
                if _existing_profile and _existing_profile.get('facts'):
                    _facts = _existing_profile['facts']
                    _matched_idx = None
                    for i, f in enumerate(_facts):
                        if _forget_what in f.lower():
                            _matched_idx = i
                            break
                    if _matched_idx is not None:
                        _removed_fact = _facts[_matched_idx]
                        if _db_remove_profile_fact(bot, trigger.nick, _matched_idx):
                            _reply_msg = f"ok, forgot: {_removed_fact[:100]}"
                        else:
                            _reply_msg = "something went wrong trying to forget that"
                    else:
                        _reply_msg = "I don't remember anything about that — say 'what do you remember about me' to see what I know"
                else:
                    _reply_msg = "I don't have anything saved about you"
        except Exception:
            _log(bot).exception('Forget handler error')
            _reply_msg = _reply_msg or "something went wrong"
        try:
            bot.say(_reply_msg, trigger.sender)
        except Exception:
            _log(bot).exception('Forget handler bot.say failed')
        return

    # --- "what do you remember about me" ---
    if _um_stripped:
        _what_match = _WHAT_REMEMBER_RE.search(_um_stripped)
    else:
        _what_match = None
    if _what_match:
        try:
            _target = _what_match.group(1) or trigger.nick
            _profile = _db_get_user_profile(bot, _target)
            if _profile and _profile.get('facts'):
                _facts_list = _profile['facts']
                if len(_facts_list) <= 5:
                    _facts_str = ' | '.join(_facts_list)
                    bot.say(f"I remember: {_facts_str}", trigger.sender)
                else:
                    bot.say(f"I remember {len(_facts_list)} things about {'you' if _target.lower() == trigger.nick.lower() else _target}:", trigger.sender)
                    for i in range(0, len(_facts_list), 5):
                        chunk = ' | '.join(_facts_list[i:i+5])
                        bot.say(chunk, trigger.sender)
            else:
                _who = 'you' if _target.lower() == trigger.nick.lower() else _target
                bot.say(f"I don't have anything saved about {_who}", trigger.sender)
        except Exception:
            _log(bot).exception('What-do-you-remember handler failed')
        return

    # Timezone/format preferences
    try:
        _pref_tz = None
        _pref_tz_label = None
        _pref_fmt = None
        _mtz = _TZ_SET_RE.search(user_message)
        if _mtz:
            _abbr = _mtz.group(1).upper()
            _iana = _TZ_ABBR_MAP.get(_abbr)
            if _iana:
                _pref_tz = _iana
                _pref_tz_label = _abbr
        _mfmt = _FMT_SET_RE.search(user_message)
        if _mfmt:
            _raw = _mfmt.group(1).lower().replace(' ', '').replace('-', '')
            _pref_fmt = '12' if _raw.startswith('12') else '24'
        if _pref_tz or _pref_fmt:
            _db_set_user_pref(bot, trigger.nick, tz=_pref_tz, tz_label=_pref_tz_label, fmt=_pref_fmt)
            _log(bot).info('Saved pref for %s: tz=%s label=%s fmt=%s', trigger.nick, _pref_tz, _pref_tz_label, _pref_fmt)
            
            conf_parts = []
            if _pref_tz:
                conf_parts.append(f"timezone to {_pref_tz_label}")
            if _pref_fmt:
                conf_parts.append(f"time format to {_pref_fmt}-hour")
                
            if _pref_tz and not _pref_fmt:
                bot.say(f"got it, {_pref_tz_label} for ya {trigger.nick}", trigger.sender)
            else:
                bot.say(f"Got it, saved your preference: {', '.join(conf_parts)} for {trigger.nick}.", trigger.sender)
            return
    except Exception:
        pass

    # Personality commands - instant config changes
    # Default: commands are per-user UNLESS "in this channel" or similar is specified
    _personality_key = trigger.sender.lower() if not is_pm else f"PM:{trigger.nick.lower()}"
    _personality_match = None
    _user_target_match = None
    _personality_reset_match = None
    
    try:
        # Check if it's explicitly a channel-wide command
        _is_channel_wide = bool(_PERSONALITY_CHANNEL_INDICATOR_RE.search(user_message))
        
        # Check for personality command with explicit target: "speak to burnout like..."
        _user_target_match = _PERSONALITY_USER_TARGET_RE.search(user_message)
        if _user_target_match:
            _target_nick = _user_target_match.group(1).strip().lower()
            _personality_desc = _user_target_match.group(2).strip()
            if _personality_desc and not is_pm:
                _chan_key = trigger.sender.lower()
                if _chan_key not in bot.memory['grok_user_personality']:
                    bot.memory['grok_user_personality'][_chan_key] = {}
                bot.memory['grok_user_personality'][_chan_key][_target_nick] = _personality_desc
                _log(bot).info('Set user personality for %s in %s: %s', _target_nick, _chan_key, _personality_desc[:50])
                return  # Personality set, no response needed
        
        # Check for general personality command (defaults to per-user)
        _personality_match = _PERSONALITY_COMMAND_RE.search(user_message)
        if _personality_match:
            # Guard against false positives: if the command verb (e.g. "be")
            # appears deep in a long conversational sentence or a question,
            # it's almost certainly NOT a personality command.
            # e.g. "would you be happy?" should NOT set personality to "happy?"
            _pm_pos = _personality_match.start()
            if _pm_pos > 20 and ('?' in user_message or len(user_message) > 80):
                _personality_match = None
        if _personality_match:
            _personality_desc = _personality_match.group(1).strip()
            # Remove channel indicators from the description if present
            _personality_desc = _PERSONALITY_CHANNEL_INDICATOR_RE.sub('', _personality_desc).strip()
            # Strip leading connector words left over after channel indicator removal
            _personality_desc = re.sub(r'^(?:like|as(?:\s+if)?|in|a|an)\s+', '', _personality_desc, flags=re.IGNORECASE).strip()
            
            if _personality_desc:
                if _is_channel_wide:
                    # Channel-wide: affects everyone
                    bot.memory['grok_channel_personality'][_personality_key] = _personality_desc
                    _log(bot).info('Set channel-wide personality for %s: %s', _personality_key, _personality_desc[:50])
                else:
                    # Per-user (default): only affects the person who said it
                    if not is_pm:
                        _chan_key = trigger.sender.lower()
                        if _chan_key not in bot.memory['grok_user_personality']:
                            bot.memory['grok_user_personality'][_chan_key] = {}
                        bot.memory['grok_user_personality'][_chan_key][trigger.nick.lower()] = _personality_desc
                        _log(bot).info('Set per-user personality for %s in %s: %s', trigger.nick.lower(), _chan_key, _personality_desc[:50])
                    else:
                        # In PM, just use the personality
                        bot.memory['grok_channel_personality'][_personality_key] = _personality_desc
                        _log(bot).info('Set PM personality for %s: %s', _personality_key, _personality_desc[:50])
                return  # Personality set, no response needed
        
        # Check for personality reset
        _personality_reset_match = _PERSONALITY_RESET_RE.search(user_message)
        if _personality_reset_match:
            # Clear channel personality
            if _personality_key in bot.memory['grok_channel_personality']:
                del bot.memory['grok_channel_personality'][_personality_key]
                _log(bot).info('Cleared channel personality for %s', _personality_key)
            # Clear user personalities for this channel
            if not is_pm:
                _chan_key = trigger.sender.lower()
                if _chan_key in bot.memory['grok_user_personality']:
                    del bot.memory['grok_user_personality'][_chan_key]
                    _log(bot).info('Cleared all user personalities for %s', _chan_key)
            return  # Reset complete, no response needed
    except Exception:
        pass

    # ========== END INSTANT CONFIG COMMANDS ==========

    review_mode = bool(_REVIEW_INTENT_RE.search(user_message)) or (user_message.strip() == '^^')

    if not user_message:
        return

    if re.match(r'^[.!/]', user_message):
        return

    time_mode = bool(_TIME_INTENT_RE.search(user_message))

    now = time.time()
    # Rate limit per-user-per-channel so one user's question doesn't block others
    _rl_key = (trigger.sender, trigger.nick.lower())
    if not time_mode:
        with chan_lock:
            last = bot.memory['grok_last'].get(_rl_key, 0)
            if now - last < CHANNEL_RATE_LIMIT:
                return
            bot.memory['grok_last'][_rl_key] = now
    else:
        with chan_lock:
            last = bot.memory['grok_last'].get(_rl_key, 0)
            if now - last < 1.5:  # small debounce to prevent double-dispatch for time mode
                return
            bot.memory['grok_last'][_rl_key] = now

    if review_mode:
        review_last = bot.memory.setdefault('grok_review_last', {})
        last_review = review_last.get(trigger.sender, 0)
        if now - last_review < REVIEW_COOLDOWN:
            return
        review_last[trigger.sender] = now

    # Get user's timezone and format preferences
    user_prefs = _db_get_user_pref(bot, trigger.nick)
    user_tz = user_prefs.get('tz_iana', 'UTC')
    user_fmt = user_prefs.get('time_fmt', '24')
    
    try:
        now_dt = datetime.datetime.now(ZoneInfo(user_tz))
        if user_fmt == '12':
            time_fmt = '%I:%M %p'
        else:
            time_fmt = '%H:%M'
        tz_label = user_prefs.get('tz_label', user_tz)
        now_str = now_dt.strftime(f'%A, %B %d, %Y at {time_fmt} {tz_label}')
    except Exception:
        # Fallback to UTC if timezone is invalid
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime('%A, %B %d, %Y at %H:%M UTC')

    # For pure time/date queries, answer directly without hitting the API.
    # Skip the shortcut if the question specifies a location (e.g. "what time is it in mesa arizona?")
    # so the API can resolve the correct timezone for that place.
    _time_is_location_query = time_mode and bool(
        re.search(r'\bin\s+[a-z]', user_message, re.IGNORECASE)
    )
    if time_mode and not _time_is_location_query and len(user_message.split()) <= 8:
        bot.say(now_str, trigger.sender)
        return
    
    # Use per-channel system prompt if defined, otherwise fall back to the global one.
    _active_system_prompt = bot.config.grok.system_prompt
    _channel_always_search = False
    if not is_pm:
        _ch_prompts = _load_channel_prompts()
        _ch_cfg = _ch_prompts.get(trigger.sender.lower())
        if _ch_cfg:
            _active_system_prompt = _ch_cfg["prompt"]
            _channel_always_search = _ch_cfg.get("always_search", False)
    
    # Apply dynamic personality override if set
    # Priority: user-specific > channel-wide > config default
    _personality_key = trigger.sender.lower() if not is_pm else f"PM:{trigger.nick.lower()}"
    _dynamic_personality = None
    
    # Check for user-specific personality first
    if not is_pm:
        _chan_key = trigger.sender.lower()
        _user_personalities = bot.memory.get('grok_user_personality', {}).get(_chan_key, {})
        _dynamic_personality = _user_personalities.get(trigger.nick.lower())
    
    # Fall back to channel-wide personality
    if not _dynamic_personality:
        _dynamic_personality = bot.memory.get('grok_channel_personality', {}).get(_personality_key)
    
    if _dynamic_personality:
        # Override the system prompt with the personality instruction
        _active_system_prompt = (
            f"You are {bot_nick}. {_dynamic_personality}. "
            "Speak naturally in this role. Keep responses short and conversational — this is IRC. "
            "Stay in character consistently. No ASCII art, no code blocks, no figlets — just talk."
        )
    messages = [
        {"role": "system", "content": _active_system_prompt},
        {
            "role": "system",
            "content": (
                f"Current date/time for {trigger.nick}: {now_str}. Use this ONLY if {trigger.nick} explicitly asks for the time or date in their message — do NOT volunteer it unprompted. "
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

    # Inject user profile data if available
    # In channels, suppress auto-learned facts to avoid cross-channel leakage
    user_profile = _db_get_user_profile(bot, trigger.nick)
    if user_profile:
        # Always include the asker's own facts — these are intentional user-stored notes
        # (auto-learned facts go into the *subject's* profile, so the asker's facts are safe)
        profile_text = _format_profile_for_context(trigger.nick, user_profile, include_facts=True)
        if profile_text:
            messages.append({"role": "system", "content": profile_text})
    
    # Check if other users are mentioned and include their profiles
    mentioned_nicks = set()
    words = user_message.lower().split()
    # Try to find mentioned nicks - look for words that might be nicknames
    # This is heuristic - we check against known nicks in recent channel history
    if not is_pm:
        try:
            with chan_lock:
                chan_log_dq = bot.memory.get('grok_channel_log', {}).get(trigger.sender.lower())
                if chan_log_dq:
                    # Collect nicks from recent channel activity
                    recent_nicks = set()
                    for nick, _ in list(chan_log_dq)[-100:]:  # Last 100 messages
                        recent_nicks.add(nick.lower())
                    # Check if any words in the message match recent nicks
                    for word in words:
                        clean_word = word.strip(',:;!?.')
                        if clean_word in recent_nicks and clean_word != trigger.nick.lower() and clean_word != bot_nick.lower():
                            mentioned_nicks.add(clean_word)
        except Exception:
            pass
    
    # Add profiles for mentioned users
    # In channels, suppress auto-learned facts to avoid cross-channel leakage
    for mentioned_nick in mentioned_nicks:
        mentioned_profile = _db_get_user_profile(bot, mentioned_nick)
        if mentioned_profile:
            profile_text = _format_profile_for_context(mentioned_nick, mentioned_profile, include_facts=is_pm)
            if profile_text:
                messages.append({"role": "system", "content": profile_text})


    relevant_turns = []
    if not review_mode:
        db_entries = _db_get_recent(bot, trigger.nick, channel='PM' if is_pm else str(trigger.sender), limit=20)
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
        # If responding to a /me action, tell Grok to reply in /me style
        if action_bot_mentioned:
            messages.append({"role": "system", "content":
                "The user just performed a /me IRC action directed at you. "
                "Respond as a short third-person action yourself (e.g. 'purrs contentedly' or 'wags tail'). "
                "Do NOT start with your nick. Do NOT use quotes. Just the action text, plain and brief."
            })
        API_TASK_QUEUE.put_nowait({
            'bot': bot, 'trigger': trigger, 'messages': messages,
            'review_mode': review_mode, 'is_pm': is_pm,
            'bot_nick': bot_nick, 'chan_lock': chan_lock,
            'search_mode': search_mode, 'wants_sources': wants_sources,
            'is_chimein': False, 'is_action': action_bot_mentioned,
        })
        # Reset chimein cooldown so talkback doesn't fire right after a direct response
        if not is_pm:
            _chimein_ts = bot.memory.get('grok_chimein_last', {})
            _chimein_ts[trigger.sender.lower()] = time.time()
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

# ==================== USER PROFILE COMMANDS ====================

@plugin.command('profile')
def profile_view(bot, trigger):
    """View a user's profile. Usage: .profile <nick>"""
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .profile <nick>")
        return
    
    target_nick = args.split()[0]
    profile = _db_get_user_profile(bot, target_nick)
    
    if not profile:
        bot.say(f"No profile found for {target_nick}.")
        return
    
    parts = []
    if profile.get('nationality'):
        parts.append(f"Nationality: {profile['nationality']}")
    if profile.get('location'):
        parts.append(f"Location: {profile['location']}")
    if profile.get('weather_location'):
        parts.append(f"Weather: {profile['weather_location']}")
    
    if parts:
        bot.say(f"Profile for {target_nick} — {' | '.join(parts)}")
    
    facts = profile.get('facts', [])
    if facts:
        for i, fact in enumerate(facts):
            bot.say(f"  [{i}] {fact}")
    
    if not parts and not facts:
        bot.say(f"Profile for {target_nick} exists but is empty.")

@plugin.command('setprofile')
def profile_set_field(bot, trigger):
    """Set a profile field. Usage: .setprofile <nick> <field> <value>
    Fields: nationality, location, weather_location"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can manage profiles.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .setprofile <nick> <field> <value>")
        return
    
    parts = args.split(None, 2)
    if len(parts) < 3:
        bot.reply("Usage: .setprofile <nick> <field> <value>")
        return
    
    target_nick, field, value = parts
    field = field.lower()
    
    if field not in {'nationality', 'location', 'weather_location'}:
        bot.reply("Valid fields: nationality, location, weather_location")
        return
    
    if _db_update_profile_field(bot, target_nick, field, value, trigger.nick):
        bot.say(f"Updated {field} for {target_nick} to: {value}")
    else:
        bot.say(f"Failed to update profile for {target_nick}.")

@plugin.command('addfact')
def profile_add_fact(bot, trigger):
    """Add a fact to a user's profile. Usage: .addfact <nick> <fact>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can manage profiles.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .addfact <nick> <fact>")
        return
    
    parts = args.split(None, 1)
    if len(parts) < 2:
        bot.reply("Usage: .addfact <nick> <fact>")
        return
    
    target_nick, fact = parts
    
    if _db_add_profile_fact(bot, target_nick, fact, trigger.nick):
        bot.say(f"Added fact for {target_nick}: {fact}")
    else:
        bot.say(f"Failed to add fact for {target_nick}.")

@plugin.command('delfact')
def profile_del_fact(bot, trigger):
    """Remove a fact from a user's profile. Usage: .delfact <nick> <index>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can manage profiles.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .delfact <nick> <index>")
        return
    
    parts = args.split()
    if len(parts) < 2:
        bot.reply("Usage: .delfact <nick> <index>")
        return
    
    target_nick = parts[0]
    try:
        index = int(parts[1])
    except ValueError:
        bot.reply("Index must be a number.")
        return
    
    if _db_remove_profile_fact(bot, target_nick, index):
        bot.say(f"Removed fact #{index} for {target_nick}.")
    else:
        bot.say(f"Failed to remove fact for {target_nick}. Check the index.")

@plugin.command('delprofile')
def profile_delete(bot, trigger):
    """Delete a user's entire profile. Usage: .delprofile <nick>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can manage profiles.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .delprofile <nick>")
        return
    
    target_nick = args.split()[0]
    
    if _db_delete_user_profile(bot, target_nick):
        bot.say(f"Deleted profile for {target_nick}.")
    else:
        bot.say(f"Failed to delete profile for {target_nick}.")

@plugin.command('reviewfacts')
def review_facts(bot, trigger):
    """Review pending fact suggestions. Usage: .reviewfacts [limit]"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can review facts.")
        return
    
    args = (trigger.group(2) or '').strip()
    limit = 10
    if args:
        try:
            limit = int(args)
            limit = min(limit, 50)
        except ValueError:
            pass
    
    suggestions = _db_get_pending_suggestions(bot, limit)
    if not suggestions:
        bot.say("No pending fact suggestions.")
        return
    
    bot.say(f"Found {len(suggestions)} pending fact suggestion(s):")
    for s in suggestions:
        confidence_pct = int(s['confidence'] * 100)
        bot.say(f"[{s['id']}] {s['nick']}: \"{s['fact']}\" (confidence: {confidence_pct}%)")
    bot.say("Use '.approve <id>' to approve or '.reject <id>' to reject.")

@plugin.command('approve')
def approve_fact(bot, trigger):
    """Approve a fact suggestion. Usage: .approve <id>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can approve facts.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .approve <id>")
        return
    
    try:
        suggestion_id = int(args)
    except ValueError:
        bot.reply("ID must be a number.")
        return
    
    if _db_approve_suggestion(bot, suggestion_id, trigger.nick):
        bot.say(f"Approved suggestion #{suggestion_id}.")
    else:
        bot.say(f"Failed to approve suggestion #{suggestion_id}. It may not exist or was already reviewed.")

@plugin.command('reject')
def reject_fact(bot, trigger):
    """Reject a fact suggestion. Usage: .reject <id>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can reject facts.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .reject <id>")
        return
    
    try:
        suggestion_id = int(args)
    except ValueError:
        bot.reply("ID must be a number.")
        return
    
    if _db_reject_suggestion(bot, suggestion_id):
        bot.say(f"Rejected suggestion #{suggestion_id}.")
    else:
        bot.say(f"Failed to reject suggestion #{suggestion_id}.")

@plugin.command('learnfacts')
def learn_facts_now(bot, trigger):
    """Manually trigger fact learning for a specific user. Usage: .learnfacts <nick>"""
    if not _is_admin(bot, trigger):
        bot.reply("Only bot admins can trigger fact learning.")
        return
    
    args = (trigger.group(2) or '').strip()
    if not args:
        bot.reply("Usage: .learnfacts <nick>")
        return
    
    target_nick = args.split()[0]
    
    # Get recent channel log
    if _is_pm(trigger):
        bot.reply("Fact learning only works in channels.")
        return
    
    chan_lock = _get_channel_lock(bot, trigger.sender)
    
    with chan_lock:
        chan_log_dq = bot.memory.get('grok_channel_log', {}).get(trigger.sender.lower())
        if not chan_log_dq:
            bot.say("No conversation history available.")
            return
        channel_log = list(chan_log_dq)
    
    if len(channel_log) < 5:
        bot.say(f"Not enough conversation history (only {len(channel_log)} messages). Need at least 5.")
        return
    
    # Count how many messages mention the target user
    mentions = sum(1 for nick, text in channel_log if target_nick.lower() in text.lower() or nick.lower() == target_nick.lower())
    
    bot.say(f"Analyzing {len(channel_log)} messages ({mentions} mentioning {target_nick})...")
    
    # Store response for debugging
    bot.memory['_last_fact_extraction_response'] = None
    
    try:
        facts = _extract_facts_from_conversation(bot, channel_log, target_nick)
    except Exception as e:
        bot.say(f"Error during extraction: {type(e).__name__}: {str(e)[:100]}")
        # Show the last API response if available
        if bot.memory.get('_last_fact_extraction_response'):
            bot.say(f"Last API response: {bot.memory['_last_fact_extraction_response'][:200]}")
        return
    
    if not facts:
        bot.say(f"No facts could be extracted about {target_nick}. Check error logs for details (might be API issue).")
        return
    
    added = 0
    auto_approved = 0
    for fact, confidence in facts:
        context_snippet = f"Learned from channel conversation in {trigger.sender}"
        if _db_add_fact_suggestion(bot, target_nick, fact, confidence, context_snippet):
            added += 1
            if confidence >= 0.9:
                auto_approved += 1
    
    if auto_approved > 0:
        bot.say(f"Added {added} fact suggestion(s) for {target_nick}. {auto_approved} auto-approved (high confidence). Use .reviewfacts to review others.")
    else:
        bot.say(f"Added {added} fact suggestion(s) for {target_nick}. Use .reviewfacts to review.")

@plugin.command('testapi')
def test_api(bot, trigger):
    """Test the Grok API directly. Admin only."""
    if not _is_admin(bot, trigger):
        return
    
    try:
        session = bot.memory.get('grok_session')
        if not session:
            bot.say("No Grok session configured")
            return
        
        model = bot.config.grok.model
        bot.say(f"Testing API with simple request using model {model}...")
        response = session.post(
            'https://api.x.ai/v1/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': 'Say only the word "test" and nothing else.'}],
                'temperature': 0.3,
                'max_tokens': 10
            },
            timeout=15
        )
        
        bot.say(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            bot.say(f"Response: {content}")
        else:
            bot.say(f"Error: {response.text[:200]}")
    except Exception as e:
        bot.say(f"Exception: {type(e).__name__}: {str(e)[:150]}")

@plugin.command('showextract')
def show_last_extraction(bot, trigger):
    """Show the last fact extraction API response. Admin only."""
    if not _is_admin(bot, trigger):
        return
    
    response = bot.memory.get('_last_fact_extraction_response')
    if not response:
        bot.say("No extraction has been run yet.")
        return
    
    # Split into chunks if needed
    if len(response) <= 400:
        bot.say(f"Last extraction: {response}")
    else:
        bot.say(f"Last extraction (first 400 chars): {response[:400]}")
        bot.say(f"... (total {len(response)} chars)")


# ==================== END USER PROFILE COMMANDS ====================


# ==================== SCHECK — SCHIZO DETECTION TOOL ====================

def _scheck_worker(bot, requester, channel, target_nick, messages_text):
    """Background worker: sends chat lines to Grok for analysis, PMs results."""
    if not _BG_TASK_SEMAPHORE.acquire(blocking=False):
        try:
            bot.say("Too many background tasks running — try again in a moment.", requester)
        except Exception:
            pass
        return
    try:
        model = bot.config.grok.model
        session = bot.memory.get('grok_session')
        if not session:
            bot.say("No Grok session configured.", requester)
            return

        if target_nick:
            scope = f"from user '{target_nick}'"
        else:
            scope = "from all users"

        system_prompt = (
            "You are a channel moderation assistant. You are analyzing IRC chat messages "
            f"{scope} in {channel}. Your job is to identify messages that are incoherent, "
            "delusional, paranoid, conspiratorial (flat earth, QAnon, etc.), schizophrenic-sounding, "
            "or otherwise disconnected from reality. Look for:\n"
            "- Incoherent word salad or nonsensical ramblings\n"
            "- Paranoid delusions (government watching me, mind control, etc.)\n"
            "- Extreme conspiratorial thinking presented as fact\n"
            "- Threatening or disturbing content\n"
            "- Rapid topic switching with no coherence\n\n"
            "Respond with a brief assessment. If you find concerning messages, quote the worst "
            "examples (max 3) with the username. If nothing stands out, say so clearly. "
            "Keep your response under 300 characters total — this is IRC. "
            "Do NOT diagnose anyone. This is for moderation purposes only. "
            "Be direct and concise."
        )
            
        response = session.post(
            'https://api.x.ai/v1/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Analyze these messages:\n\n{messages_text}"},
                ],
                'temperature': 0.3,
                'max_tokens': 250,
            },
            timeout=20,
        )

        if response.status_code != 200:
            bot.say(f"API error: HTTP {response.status_code}", requester)
            return

        result = response.json()
        content = result['choices'][0]['message']['content'].strip()

        # Clean for IRC (single line)
        content = re.sub(r'\s*\n\s*', ' | ', content)

        # PM results to the requester
        bot.say(f"\x02[scheck {channel}]\x02 {content}", requester)

        # If a specific user was targeted, offer kick/ban options
        if target_nick:
            bot.say(
                f"\x0314Actions: \x02$skick {target_nick} {channel}\x02 or "
                f"\x02$skban {target_nick} {channel}\x02\x0f",
                requester,
            )

    except Exception as e:
        _log(bot).exception('scheck worker error')
        try:
            bot.say(f"scheck error: {type(e).__name__}: {str(e)[:100]}", requester)
        except Exception:
            pass
    finally:
        _BG_TASK_SEMAPHORE.release()


@plugin.command('scheck')
def scheck(bot, trigger):
    """Scan channel chat for schizo/incoherent posts. Admin/Op only.

    Usage:
        $scheck           — scan last 100 messages from all users
        $scheck <nick>    — scan last 100 messages, filter to <nick> only
    """
    if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
        return

    is_pm = _is_pm(trigger)

    if is_pm:
        # PM mode: $scheck #channel [nick]  — admin only
        if not _is_admin(bot, trigger):
            bot.say("Admin only from PM.")
            return
        args = (trigger.group(2) or '').strip().split()
        if not args or not args[0].startswith('#'):
            bot.say("Usage from PM: $scheck #channel [nick]")
            return
        channel = args[0]
        target_nick = args[1] if len(args) > 1 else None
    else:
        # Channel mode: $scheck [nick]
        channel = trigger.sender
        args = (trigger.group(2) or '').strip()
        target_nick = args.split()[0] if args else None

    # Get channel log
    chan_key = channel.lower()
    chan_log = bot.memory.get('grok_channel_log', {}).get(chan_key)
    if not chan_log or len(chan_log) < 5:
        bot.say("Not enough channel history to analyze.")
        return

    # Pull last 100 messages
    recent = list(chan_log)[-100:]

    # Filter to target nick if specified
    if target_nick:
        filtered = [(n, t) for n, t in recent if n.lower() == target_nick.lower()]
        if not filtered:
            bot.say(f"No recent messages from {target_nick} in the log.")
            return
        recent = filtered

    # Format for AI
    lines = [f"<{n}> {t}" for n, t in recent]
    messages_text = "\n".join(lines)

    # Truncate if too long
    if len(messages_text) > 6000:
        messages_text = messages_text[-6000:]

    # Confirmation — in channel or PM depending on where it was invoked
    scan_msg = f"🔍 Scanning {len(recent)} messages{' from ' + target_nick if target_nick else ''} in {channel}... results via PM."
    if is_pm:
        bot.say(scan_msg, trigger.nick)
    else:
        bot.say(scan_msg)

    # Run in background thread
    t = threading.Thread(
        target=_scheck_worker,
        args=(bot, trigger.nick, channel, target_nick, messages_text),
        daemon=True,
        name=f"scheck_{trigger.nick}_{chan_key}",
    )
    t.start()


@plugin.command('skick')
def scheck_kick(bot, trigger):
    """Kick a user from a channel. Admin/Op only.

    Usage: $skick <nick> <#channel>
    """
    if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
        return

    args = (trigger.group(2) or '').strip().split()
    if len(args) < 2:
        bot.say("Usage: $skick <nick> <#channel>")
        return

    target = args[0]
    channel = args[1]

    if not channel.startswith('#'):
        bot.say("Invalid channel. Must start with #.")
        return

    try:
        bot.write(['KICK', channel, target, ':Removed by moderator'])
        bot.say(f"✅ Kicked {target} from {channel}", trigger.nick)
    except Exception as e:
        bot.say(f"❌ Failed to kick: {e}", trigger.nick)


@plugin.command('skban')
def scheck_kickban(bot, trigger):
    """Kick-ban a user from a channel. Admin/Op only.

    Usage: $skban <nick> <#channel>
    """
    if not (_is_admin(bot, trigger) or _is_channel_op(bot, trigger)):
        return

    args = (trigger.group(2) or '').strip().split()
    if len(args) < 2:
        bot.say("Usage: $skban <nick> <#channel>")
        return

    target = args[0]
    channel = args[1]

    if not channel.startswith('#'):
        bot.say("Invalid channel. Must start with #.")
        return

    try:
        # Set ban first, then kick
        # Try to get the user's host for a proper ban mask
        ban_mask = f"{target}!*@*"
        try:
            chan_obj = getattr(bot, 'channels', {}).get(channel)
            if chan_obj:
                users = getattr(chan_obj, 'users', {})
                user_obj = users.get(target) or users.get(target.lower())
                if user_obj and hasattr(user_obj, 'host') and user_obj.host:
                    ban_mask = f"*!*@{user_obj.host}"
        except Exception:
            pass

        bot.write(['MODE', channel, '+b', ban_mask])
        bot.write(['KICK', channel, target, ':Banned by moderator'])
        bot.say(f"✅ Kick-banned {target} from {channel} ({ban_mask})", trigger.nick)
    except Exception as e:
        bot.say(f"❌ Failed to kick-ban: {e}", trigger.nick)


# ==================== END SCHECK ====================

# Force reload
