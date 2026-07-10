# fix.py — Full-featured IRC sed correction plugin for Sopel
#
# Syntax:  [nick[,: ]] s<delim>pattern<delim>replacement[<delim>[flags]]
#          [nick[,: ]] s<delim>pattern<delim>replacement[<delim>[flags]]
#
# Delimiters: any non-alphanumeric, non-space character (/, |, #, !, @, ...)
# Flags: g (global), i (case-insensitive), 1-9 (replace Nth occurrence only)
# Pattern: full Python regex; \1 \2 backreferences and & (whole match) work in replacement
#
# Examples:
#   s/hatr/hate                → corrects your own last message with "hatr"
#   s/hatr/hate/g              → replace every occurrence
#   s/hatr/hate/i              → case-insensitive
#   s/hatr/hate/2              → replace only the 2nd occurrence
#   s|(foo)|([\1])|g           → pipe delimiter, backreference
#   End3r: s/hatr/hate         → corrects End3r's last matching message
#   s/hatr/hate                → also searches all recent channel history if
#                                your own history has no match

import re
import time
import threading
from collections import deque
from sopel import plugin

HISTORY_LEN = 20          # messages remembered per (channel, nick)
MAX_PATTERN_LEN = 200     # guard against absurd patterns
REGEX_TIMEOUT = 0.5       # seconds before a regex match is considered runaway
MAX_OUTPUT_LEN = 420      # truncate corrected output to stay within IRC limits
RATE_LIMIT = 4.0          # minimum seconds between corrections per (channel, nick)
IRC_CHAN_PREFIXES = '#&!+' # all valid IRC channel sigils

# Matches optional "nick: " or "nick, " prefix then the sed expression.
# Delimiter is captured so it can be reused for the second split.
_SED_RE = re.compile(
    r'^(?:(\S+)[,:\s]+)?'           # optional target nick
    r's([^a-zA-Z0-9\s])'            # 's' + delimiter (any punct)
    r'((?:[^\\]|\\.)*?)'            # pattern (allows escaped delimiters)
    r'\2'                           # same delimiter
    r'((?:[^\\]|\\.)*?)'            # replacement
    r'(?:\2([gi1-9]*))?$',          # optional closing delim + flags
    re.IGNORECASE,
)


def setup(bot):
    if 'fix_history' not in bot.memory:
        # {(channel, nick): deque([text, ...])}
        bot.memory['fix_history'] = {}
    if 'fix_rate' not in bot.memory:
        # {(channel, nick): last_correction_timestamp}
        bot.memory['fix_rate'] = {}

    # Patch the send layer so the bot's own output is recorded and correctable.
    #
    # ibot:  bot is a SopelWrapper recreated per handler call — patching it
    #        would be lost immediately.  Instead patch the shared core client
    #        (bot._bot) at send_privmsg, which persists for the bot's lifetime.
    #
    # Sopel: bot IS the long-lived bot object, so patching bot.say directly
    #        works fine.
    _core = getattr(bot, '_bot', bot)   # ibot exposes ._bot; Sopel doesn't
    if not getattr(_core, '_fix_patched', False):
        if hasattr(_core, 'send_privmsg'):
            # ── ibot path ──────────────────────────────────────────────────
            _orig_sp = _core.send_privmsg
            _memory  = bot.memory      # SopelWrapper.memory → _bot.memory (shared)
            _get_nick = lambda: _core.nick
            def _patched_sp(target, text):
                _orig_sp(target, text)
                if str(target)[:1] in IRC_CHAN_PREFIXES:
                    _record_mem(_memory, str(target), _get_nick(), str(text))
            _core.send_privmsg = _patched_sp
        else:
            # ── Sopel path ─────────────────────────────────────────────────
            _orig_say = _core.say
            def _patched_say(*args, **kwargs):
                _orig_say(*args, **kwargs)
                text_out    = args[0] if args else kwargs.get('text', '')
                destination = args[1] if len(args) > 1 else kwargs.get('destination')
                if destination and str(destination)[:1] in IRC_CHAN_PREFIXES:
                    _record(bot, str(destination), bot.nick, str(text_out))
            _core.say = _patched_say
        _core._fix_patched = True


def _record_mem(memory, channel, nick, text):
    """Write directly to a memory dict (used by the send_privmsg patch closure)."""
    key = (channel.lower(), nick.lower())
    history = memory['fix_history'].setdefault(key, deque(maxlen=HISTORY_LEN))
    history.append(text)


def _record(bot, channel, nick, text):
    _record_mem(bot.memory, channel, nick, text)


def _get_history(bot, channel, nick):
    key = (channel.lower(), nick.lower())
    return list(bot.memory['fix_history'].get(key, []))


def _regex_match(pattern, flags_str, text):
    """Compile and search with a timeout guard. Returns (compiled, match) or raises."""
    re_flags = 0
    if 'i' in flags_str:
        re_flags |= re.IGNORECASE
    compiled = re.compile(pattern, re_flags)
    result = [None]
    exc = [None]

    def _run():
        try:
            result[0] = compiled.search(text)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(REGEX_TIMEOUT)
    if t.is_alive():
        raise TimeoutError('pattern took too long')
    if exc[0]:
        raise exc[0]
    return compiled, result[0]


def _apply_sub(compiled, replacement, text, flags_str):
    """Apply substitution respecting g / nth-occurrence flags."""
    # Replace & with the whole-match backreference \g<0> in replacement
    replacement = re.sub(r'(?<!\\)&', r'\\g<0>', replacement)

    nth = None
    for ch in flags_str:
        if ch.isdigit() and ch != '0':
            nth = int(ch)
            break

    if 'g' in flags_str:
        return compiled.sub(replacement, text)
    elif nth is not None:
        # Replace only the nth occurrence
        occurrences = [0]
        def _replacer(m):
            occurrences[0] += 1
            if occurrences[0] == nth:
                return m.expand(replacement)
            return m.group(0)
        return compiled.sub(_replacer, text)
    else:
        return compiled.sub(replacement, text, count=1)


@plugin.rule(r'.*')
@plugin.priority('low')
def record_message(bot, trigger):
    """Record every non-sed message for later correction."""
    if trigger.is_privmsg:
        return
    line = trigger.group(0).strip()
    if _SED_RE.match(line):
        return
    _record(bot, str(trigger.sender), trigger.nick, line)


@plugin.rule(r'^(?:\S+[,:\s]+)?s[^a-zA-Z0-9\s].+')
@plugin.require_chanmsg('Corrections only work in channels.')
def fix_typo(bot, trigger):
    """Apply a sed-style correction to a recent message."""
    line = trigger.group(0).strip()
    m = _SED_RE.match(line)
    if not m:
        return

    raw_nick    = m.group(1)   # may be None; may have trailing ',:'
    target_nick = raw_nick.rstrip(',:') if raw_nick else None
    pattern_str = m.group(3)
    replacement = m.group(4)
    flags_str   = (m.group(5) or '').lower()
    channel     = str(trigger.sender)

    # Rate limit: ignore if this user corrected too recently
    rate_key = (channel.lower(), trigger.nick.lower())
    now = time.monotonic()
    last = bot.memory['fix_rate'].get(rate_key, 0.0)
    if now - last < RATE_LIMIT:
        return
    bot.memory['fix_rate'][rate_key] = now

    if not pattern_str or len(pattern_str) > MAX_PATTERN_LEN:
        return

    # Decide whose history to search
    if target_nick:
        # Explicit target: only search that nick's history
        candidates = [(target_nick, msg) for msg in reversed(_get_history(bot, channel, target_nick))]
        if not candidates:
            return
    else:
        # No target: search own history first, then fall back to whole channel
        own = [(trigger.nick, msg) for msg in reversed(_get_history(bot, channel, trigger.nick))]
        # Build recent channel-wide history (all nicks, newest first)
        channel_wide = []
        chan_store = bot.memory.get('fix_history', {})
        for (ch, nk), dq in chan_store.items():
            if ch == channel.lower() and nk != trigger.nick.lower():
                for msg in reversed(list(dq)):
                    channel_wide.append((nk, msg))
        candidates = own + channel_wide

    # Find first message that matches the pattern
    found_nick = None
    found_msg  = None
    compiled   = None
    try:
        for nk, msg in candidates:
            compiled, match = _regex_match(pattern_str, flags_str, msg)
            if match:
                found_nick = nk
                found_msg  = msg
                break
    except (re.error, TimeoutError):
        return

    if found_msg is None or compiled is None:
        return

    try:
        corrected = _apply_sub(compiled, replacement, found_msg, flags_str)
    except (re.error, IndexError):
        return

    if corrected == found_msg:
        return

    # Truncate to avoid exceeding IRC line length limits
    if len(corrected) > MAX_OUTPUT_LEN:
        corrected = corrected[:MAX_OUTPUT_LEN - 3] + '...'

    if found_nick.lower() == trigger.nick.lower():
        bot.say(f'{trigger.nick} meant to say: {corrected}')
    else:
        bot.say(f'{trigger.nick} thinks {found_nick} meant to say: {corrected}')
