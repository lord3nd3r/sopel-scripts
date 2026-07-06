"""
antispam.py - Anti-Spam Kick Protection

Detects users who paste rapid-fire multi-line spam (URL dumps, quoted text walls)
and kicks them. No bans — just kicks.

Four detection modes:
    1. Rate-based:      If a user sends >= `threshold` messages within `window`
                        seconds, they get kicked.
    2. Content-based:   If a message matches any configured trigger phrase,
                        instant kick — regardless of rate or timing.
    3. Unicode art:     Detects braille/block character floods.
    4. Copypasta:       Fingerprints long messages. When a spammer is kicked,
                        their messages are learned. Future messages matching
                        the learned spam get instant-kicked — even with minor
                        word changes.

Author: Kristopher Craig
Commands:
    $spam                               - Show status for the current channel
    $spam on / off                      - Enable/disable in the current channel
    $spam set <param> <val>             - Adjust window or threshold
    $spam trigger add <phrase>          - Add a trigger phrase (instant kick)
    $spam trigger del <phrase>          - Remove a trigger phrase
    $spam trigger list                  - List all trigger phrases
    $spam copypasta status              - Show copypasta DB stats
    $spam copypasta clear               - Wipe the copypasta DB for this channel
    $spam help                          - Show help via NOTICE
"""

from sopel import plugin
import json
import logging
import logging.handlers
import os
import re
import requests
import threading
import time

LOGGER = logging.getLogger('antispam')
LOGGER.setLevel(logging.DEBUG)
# File handler — dedicated log file for antispam
_log_path = os.path.join(os.path.expanduser('~/.sopel'), 'antispam.log')
_fh = logging.handlers.RotatingFileHandler(_log_path, maxBytes=5*1024*1024, backupCount=3)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-7s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
if not LOGGER.handlers:
    LOGGER.addHandler(_fh)

B = "\x02"
COLOR_RESET = "\x03"
SEP = "\x0314 · \x03"

# Default settings
DEFAULT_WINDOW = 8        # seconds — how fast messages must come
DEFAULT_THRESHOLD = 5     # messages within window to trigger kick
DEFAULT_UNICODE_THRESHOLD = 3   # unicode art lines within window to trigger kick
DEFAULT_UNICODE_WINDOW = 30     # seconds — window for unicode art flood detection

# Copypasta detection settings
COPYPASTA_MIN_LENGTH = 60       # minimum normalized chars to fingerprint
COPYPASTA_SHINGLE_SIZE = 3      # words per shingle
COPYPASTA_MATCH_RATIO = 0.4     # 40% shingle overlap = copypasta match
COPYPASTA_MAX_SHINGLES = 2000   # max shingles stored per channel
COPYPASTA_TEXT_WINDOW = 300     # seconds to keep recent texts for learning

# Grok AI spam classification settings
GROK_SPAM_ENABLED = True        # toggle AI classification
GROK_SPAM_MIN_LENGTH = 80       # minimum message length to classify
GROK_SPAM_COOLDOWN = 10         # seconds between AI checks per user
GROK_SPAM_TIMEOUT = 5           # API timeout in seconds
GROK_SPAM_MODEL = 'grok-3-mini-fast'  # cheap/fast model for classification


# ========================= SETUP / SHUTDOWN =========================

def setup(bot):
    """Initialize the antispam plugin."""
    bot.memory['spam_messages'] = {}        # (channel, hostmask) -> [timestamps]
    bot.memory['spam_unicode'] = {}         # (channel, hostmask) -> [timestamps] for unicode art
    bot.memory['spam_kicked'] = {}          # (channel, nick_lower) -> timestamp of last kick
    bot.memory['spam_texts'] = {}           # (channel, hostmask) -> [(timestamp, text)] recent msgs
    bot.memory['spam_grok_last'] = {}       # (channel, hostmask) -> timestamp of last Grok check
    bot.memory['spam_lock'] = threading.Lock()
    LOGGER.info("Antispam protection initialized (with Grok AI classification)")


def shutdown(bot):
    """Clean up on shutdown."""
    LOGGER.info("Antispam protection shutdown")


# ========================= SETTINGS HELPERS =========================

def _get_settings(bot, channel):
    """Get antispam settings for a channel from the DB, with defaults."""
    overrides = bot.db.get_plugin_value('antispam', f'settings_{channel.lower()}') or {}
    return {
        'window': overrides.get('window', DEFAULT_WINDOW),
        'threshold': overrides.get('threshold', DEFAULT_THRESHOLD),
        'unicode_threshold': overrides.get('unicode_threshold', DEFAULT_UNICODE_THRESHOLD),
        'unicode_window': overrides.get('unicode_window', DEFAULT_UNICODE_WINDOW),
    }


def _save_setting(bot, channel, key, value):
    """Persist a setting override to the DB."""
    db_key = f'settings_{channel.lower()}'
    overrides = bot.db.get_plugin_value('antispam', db_key) or {}
    overrides[key] = value
    bot.db.set_plugin_value('antispam', db_key, overrides)


def _is_channel_enabled(bot, channel):
    """Check if antispam is enabled for a specific channel."""
    enabled = bot.db.get_plugin_value('antispam', 'enabled_channels') or []
    return channel.lower() in [c.lower() for c in enabled]


def _is_exempt(bot, nick, channel):
    """Check if a user holds halfop (+h) or higher — exempt from spam kicks.
    Voiced (+v) users are explicitly NOT exempt."""
    chan = str(channel)
    if chan not in bot.channels:
        return False
    privs = bot.channels[chan].privileges.get(nick, 0)
    # Only halfop (+h) and above are exempt — voice (+v) is NOT exempt
    exempt = bool(privs & (plugin.HALFOP | plugin.OP | plugin.ADMIN | plugin.OWNER | plugin.OPER))
    if privs and not exempt:
        LOGGER.debug("Antispam: %s has privs=%d in %s but is NOT exempt", nick, privs, chan)
    return exempt


def _bot_has_op(bot, channel):
    """Check if the bot has operator (or halfop) status in a channel."""
    chan = str(channel)
    if chan in bot.channels:
        privs = bot.channels[chan].privileges.get(bot.nick, 0)
        return bool(privs & (plugin.HALFOP | plugin.OP))
    return False


def _get_triggers(bot, channel):
    """Get the list of trigger phrases for a channel."""
    return bot.db.get_plugin_value('antispam', f'triggers_{channel.lower()}') or []


def _save_triggers(bot, channel, triggers):
    """Save the list of trigger phrases for a channel."""
    bot.db.set_plugin_value('antispam', f'triggers_{channel.lower()}', triggers)


def _check_triggers(bot, channel, text):
    """Check if a message matches any trigger phrase. Returns the matched phrase or None."""
    triggers = _get_triggers(bot, channel)
    if not triggers:
        return None
    text_lower = text.lower()
    for phrase in triggers:
        if phrase.lower() in text_lower:
            return phrase
    return None


# Unicode art character ranges used in braille/block art floods
_UNICODE_ART_RANGES = [
    (0x2500, 0x257F),  # Box Drawing
    (0x2580, 0x259F),  # Block Elements
    (0x25A0, 0x25FF),  # Geometric Shapes
    (0x2800, 0x28FF),  # Braille Patterns
]


def _is_unicode_art(text, min_length=20, ratio=0.3):
    """Detect messages that are predominantly unicode art (braille, box drawing, etc.).

    Returns True if at least ``ratio`` of non-whitespace characters fall in
    known art-character ranges and the message meets ``min_length``.
    """
    stripped = text.replace(' ', '')
    if len(stripped) < min_length:
        return False
    art_count = sum(
        1 for c in stripped
        if any(lo <= ord(c) <= hi for lo, hi in _UNICODE_ART_RANGES)
    )
    return (art_count / len(stripped)) >= ratio


# ========================= COPYPASTA DETECTION =========================

def _normalize_for_fingerprint(text):
    """Normalize text for copypasta fingerprinting.

    Strips URLs, IRC formatting, punctuation — keeps only lowercase words.
    """
    text = text.lower()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'[\x02\x03\x0f\x16\x1d\x1f]', '', text)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_shingles(text, size=COPYPASTA_SHINGLE_SIZE):
    """Extract word-level shingles (n-grams) from normalized text."""
    words = text.split()
    if len(words) < size:
        return set()
    return {' '.join(words[i:i + size]) for i in range(len(words) - size + 1)}


def _get_spam_shingles(bot, channel):
    """Load stored spam shingles for a channel from the DB."""
    stored = bot.db.get_plugin_value('antispam', f'copypasta_{channel}') or []
    return set(stored)


def _save_spam_shingles(bot, channel, shingles):
    """Save spam shingles for a channel to the DB, capped at max."""
    shingle_list = list(shingles)
    if len(shingle_list) > COPYPASTA_MAX_SHINGLES:
        shingle_list = shingle_list[-COPYPASTA_MAX_SHINGLES:]
    bot.db.set_plugin_value('antispam', f'copypasta_{channel}', shingle_list)


def _check_copypasta(bot, channel, text):
    """Check if a message matches known copypasta.

    Returns (ratio, matched_count, total_shingles) or (0, 0, 0) if no match.
    """
    normalized = _normalize_for_fingerprint(text)
    if len(normalized) < COPYPASTA_MIN_LENGTH:
        return 0, 0, 0
    msg_shingles = _get_shingles(normalized)
    if not msg_shingles:
        return 0, 0, 0
    known = _get_spam_shingles(bot, channel)
    if not known:
        return 0, 0, 0
    overlap = msg_shingles & known
    ratio = len(overlap) / len(msg_shingles)
    return ratio, len(overlap), len(msg_shingles)


def _learn_spam_content(bot, channel, texts):
    """Record message texts as known spam for copypasta detection."""
    known = _get_spam_shingles(bot, channel)
    added = 0
    for text in texts:
        normalized = _normalize_for_fingerprint(text)
        if len(normalized) >= COPYPASTA_MIN_LENGTH:
            shingles = _get_shingles(normalized)
            new = shingles - known
            known.update(new)
            added += len(new)
    if added:
        _save_spam_shingles(bot, channel, known)
        LOGGER.info("Antispam: Learned %d new copypasta shingles for %s (total: %d)",
                    added, channel, len(known))


def _track_text(bot, channel, hostmask, text):
    """Track a message's text for copypasta learning when the user gets kicked."""
    now = time.time()
    key = (channel, hostmask)
    with bot.memory['spam_lock']:
        texts = bot.memory['spam_texts']
        if key not in texts:
            texts[key] = []
        texts[key].append((now, text))
        # Prune old entries
        cutoff = now - COPYPASTA_TEXT_WINDOW
        texts[key] = [(t, txt) for t, txt in texts[key] if t > cutoff]


def _get_tracked_texts(bot, channel, hostmask):
    """Get recently tracked texts for a user."""
    key = (channel, hostmask)
    with bot.memory['spam_lock']:
        entries = bot.memory['spam_texts'].get(key, [])
        return [txt for _, txt in entries]


# ========================= GROK AI CLASSIFICATION =========================

_GROK_SPAM_PROMPT = """You are a spam classifier for the IRC channel #8chan. This channel allows ALL offensive language, racial slurs, trolling, and crude humor — that is NORMAL and must NOT be flagged.

You are looking for ONE specific behavior: a user FLOODING the channel with repetitive copypasta — walls of quoted news articles, URLs, and manifesto-style text about the same topic, posted over and over across multiple messages in rapid succession.

Here are the user's last {count} messages sent in the last {seconds} seconds:
---
{messages}
---

Is this user flooding the channel with repetitive copypasta/spam? Consider:
- Are they posting multiple quoted articles/URLs about the same topic rapidly?
- Is this a wall-of-text flood rather than normal conversation?
- One or two links in conversation is NORMAL. 5+ quoted articles in rapid succession is SPAM.

Reply with ONLY the word SPAM or SAFE. Nothing else."""

GROK_SPAM_MIN_MESSAGES = 5    # need at least this many recent messages to bother checking


def _grok_classify_spam(bot, channel, hostmask, message_text):
    """Ask Grok AI whether a user's recent messages constitute copypasta spam.

    Sends the user's full recent message history so Grok can see the
    flooding pattern, not just one message in isolation.

    Returns True if Grok says it's spam, False otherwise.
    Fails safe (returns False) on any error or timeout.
    Rate-limited per user to avoid API abuse.
    """
    if not GROK_SPAM_ENABLED:
        return False

    # Get the user's recent messages
    recent = _get_tracked_texts(bot, channel, hostmask)
    if len(recent) < GROK_SPAM_MIN_MESSAGES:
        return False

    # Rate limit: one AI check per user per cooldown period
    now = time.time()
    key = (channel, hostmask)
    with bot.memory['spam_lock']:
        last_check = bot.memory['spam_grok_last'].get(key, 0)
        if now - last_check < GROK_SPAM_COOLDOWN:
            return False
        bot.memory['spam_grok_last'][key] = now

    # Use the Grok session from the ai-grok plugin
    session = bot.memory.get('grok_session')
    if not session:
        LOGGER.debug("Antispam: No grok_session available for AI classification")
        return False

    try:
        # Build context: last N messages, truncated to fit
        msg_lines = []
        for i, txt in enumerate(recent[-15:], 1):
            msg_lines.append(f"{i}. {txt[:200]}")
        messages_block = '\n'.join(msg_lines)

        prompt = _GROK_SPAM_PROMPT.format(
            count=len(recent),
            seconds=int(COPYPASTA_TEXT_WINDOW),
            messages=messages_block,
        )
        payload = {
            "model": GROK_SPAM_MODEL,
            "input": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_output_tokens": 10,
        }
        LOGGER.debug("Antispam: Sending %d messages to Grok AI for %s in %s",
                     len(recent), hostmask, channel)
        r = session.post(
            "https://api.x.ai/v1/responses",
            json=payload,
            timeout=(3, GROK_SPAM_TIMEOUT),
        )
        r.raise_for_status()
        data = r.json()

        # Parse response — same format as ai-grok.py
        reply = ''
        output_items = data.get('output', [])
        for item in output_items:
            if isinstance(item, dict) and item.get('type') == 'message':
                for part in (item.get('content') or []):
                    if isinstance(part, dict) and part.get('type') in ('text', 'output_text'):
                        reply += part.get('text', '')

        verdict = reply.strip().upper()
        LOGGER.info("Antispam: Grok AI verdict for %s in %s: %s (%d msgs analyzed)",
                    hostmask, channel, verdict, len(recent))
        return verdict == 'SPAM'

    except requests.Timeout:
        LOGGER.debug("Antispam: Grok AI classification timed out")
        return False
    except Exception:
        LOGGER.debug("Antispam: Grok AI classification failed", exc_info=True)
        return False


# ========================= CORE LOGIC =========================

@plugin.thread(True)
@plugin.rule('.*')
def on_message(bot, trigger):
    """Track every PRIVMSG in enabled channels for spam detection."""
    if trigger.is_privmsg:
        return
    if not str(trigger.sender).startswith('#'):
        return

    channel = str(trigger.sender).lower()
    nick = trigger.nick

    if not _is_channel_enabled(bot, channel):
        return
    if nick.lower() == bot.nick.lower():
        return
    if _is_exempt(bot, nick, channel):
        return

    hostmask = f"{trigger.user or '*'}@{trigger.host or '*'}"
    message_text = str(trigger)

    # --- Content-based detection (instant kick) ---
    matched = _check_triggers(bot, channel, message_text)
    LOGGER.debug(
        "Antispam: [%s] <%s> %s | triggers=%s | matched=%s",
        channel, nick, message_text[:80], bool(_get_triggers(bot, channel)), matched,
    )
    if matched:
        if _bot_has_op(bot, channel):
            reason = f"Matched spam trigger — kick on sight"
            bot.write(['KICK', channel, nick, f':{reason}'])
            LOGGER.info(
                "Antispam: Kicked %s (%s) from %s — trigger match: %s",
                nick, hostmask, channel, matched,
            )
        else:
            LOGGER.warning(
                "Antispam: Trigger match from %s in %s — bot not opped",
                nick, channel,
            )
        return

    settings = _get_settings(bot, channel)
    now = time.time()
    key = (channel, hostmask)

    # --- Track message text for copypasta learning ---
    _track_text(bot, channel, hostmask, message_text)

    # --- Copypasta detection (learned spam fingerprints) ---
    ratio, matched, total = _check_copypasta(bot, channel, message_text)
    if ratio >= COPYPASTA_MATCH_RATIO:
        LOGGER.info(
            "Antispam: Copypasta match from %s in %s — %.0f%% (%d/%d shingles)",
            nick, channel, ratio * 100, matched, total,
        )
        _kick_spammer(bot, nick, channel, hostmask, settings, 0,
                     reason=f"Copypasta detected ({matched}/{total} fingerprints matched)")
        # Learn any new shingles from this message too
        _learn_spam_content(bot, channel, [message_text])
        return

    # --- Grok AI classification (catches new copypasta not yet fingerprinted) ---
    if _grok_classify_spam(bot, channel, hostmask, message_text):
        LOGGER.info("Antispam: Grok AI flagged spam from %s in %s", nick, channel)
        _kick_spammer(bot, nick, channel, hostmask, settings, 0,
                     reason="AI detected copypasta spam")
        _learn_spam_content(bot, channel, [message_text])
        return

    # --- Unicode art flood detection (stricter threshold) ---
    if _is_unicode_art(message_text):
        unicode_triggered = False
        with bot.memory['spam_lock']:
            umsgs = bot.memory['spam_unicode']
            if key not in umsgs:
                umsgs[key] = []
            umsgs[key].append(now)
            cutoff = now - settings['unicode_window']
            umsgs[key] = [t for t in umsgs[key] if t > cutoff]
            ucount = len(umsgs[key])
            if ucount >= settings['unicode_threshold']:
                del umsgs[key]
                unicode_triggered = True

        if unicode_triggered:
            _kick_spammer(bot, nick, channel, hostmask, settings, ucount,
                         reason="Unicode art flood detected — knock it off")
            return

    # --- Rate-based detection ---
    triggered = False

    with bot.memory['spam_lock']:
        msgs = bot.memory['spam_messages']

        if key not in msgs:
            msgs[key] = []
        msgs[key].append(now)

        # Prune outside window
        cutoff = now - settings['window']
        msgs[key] = [t for t in msgs[key] if t > cutoff]
        count = len(msgs[key])

        if count >= settings['threshold']:
            # Reset their counter
            del msgs[key]
            triggered = True

    if triggered:
        _kick_spammer(bot, nick, channel, hostmask, settings, count)


def _revoke_autovoice(bot, channel, nick):
    """Reset a user's autovoice data so they don't get re-voiced on rejoin.

    Directly modifies the autovoice module's in-memory data and saves to disk.
    This is the nuclear option — the user has to re-earn voice from zero.
    """
    try:
        import autovoice
        nick_lower = nick.lower()
        autovoice._load()
        with autovoice._data_lock:
            chan_data = (autovoice._data or {}).get(channel, {})
            if nick_lower in chan_data:
                chan_data[nick_lower]['count'] = 0
                chan_data[nick_lower]['autovoiced'] = False
                LOGGER.info("Antispam: Reset autovoice data for %s in %s", nick, channel)
        autovoice._save()
    except Exception:
        LOGGER.debug("Antispam: Could not reset autovoice data (module not loaded?)")


def _kick_spammer(bot, nick, channel, hostmask, settings, count, reason=None):
    """Kick the spammer and revoke their autovoice so they don't get re-voiced on rejoin."""
    if not _bot_has_op(bot, channel):
        LOGGER.warning(
            "Antispam: Spam from %s in %s — bot not opped, cannot kick",
            nick, channel,
        )
        return

    if reason is None:
        reason = f"Spam detected ({count} msgs in {settings['window']}s) — slow down"
    bot.write(['KICK', channel, nick, f':{reason}'])

    # Record the kick so autovoice won't re-voice them on rejoin
    with bot.memory['spam_lock']:
        bot.memory['spam_kicked'][(channel, nick.lower())] = time.time()

    # Learn their recent messages as copypasta for future detection
    recent_texts = _get_tracked_texts(bot, channel, hostmask)
    if recent_texts:
        _learn_spam_content(bot, channel, recent_texts)

    # Nuke their autovoice data so they have to re-earn voice from zero
    _revoke_autovoice(bot, channel, nick)

    LOGGER.info(
        "Antispam: Kicked %s (%s) from %s — %s (autovoice revoked, copypasta learned)",
        nick, hostmask, channel, reason,
    )


# ========================= PERIODIC CLEANUP =========================

@plugin.thread(True)
@plugin.interval(30)
def cleanup(bot):
    """Prune stale message tracking entries."""
    now = time.time()

    with bot.memory['spam_lock']:
        msgs = bot.memory['spam_messages']
        stale = []
        for key, timestamps in msgs.items():
            channel = key[0]
            settings = _get_settings(bot, channel)
            cutoff = now - settings['window']
            msgs[key] = [t for t in timestamps if t > cutoff]
            if not msgs[key]:
                stale.append(key)
        for key in stale:
            del msgs[key]

        # Prune unicode art tracking
        umsgs = bot.memory.get('spam_unicode', {})
        ustale = []
        for key, timestamps in umsgs.items():
            channel = key[0]
            settings = _get_settings(bot, channel)
            cutoff = now - settings['unicode_window']
            umsgs[key] = [t for t in timestamps if t > cutoff]
            if not umsgs[key]:
                ustale.append(key)
        for key in ustale:
            del umsgs[key]


# ========================= ADMIN COMMANDS =========================

@plugin.command('spam')
@plugin.require_admin('You need to be a bot admin to manage antispam.')
def cmd_spam(bot, trigger):
    """$spam <status|on|off|set|trigger|help> — Manage antispam protection.

    In a channel:  $spam trigger add <phrase>
    In PM:         $spam #channel trigger add <phrase>
    """
    args = (trigger.group(2) or '').strip().split()

    # Determine channel: from PM require #channel as first arg, in-channel use sender
    if trigger.is_privmsg:
        if not args or not args[0].startswith('#'):
            return bot.reply(
                f"From PM, specify the channel first: "
                f"{B}$spam #channel <subcommand>{B}"
            )
        channel = args.pop(0).lower()
    else:
        channel = str(trigger.sender).lower()

    subcmd = args[0].lower() if args else 'status'

    dispatch = {
        'status':    lambda: _cmd_status(bot, trigger, channel),
        'on':        lambda: _cmd_toggle(bot, trigger, channel, enable=True),
        'off':       lambda: _cmd_toggle(bot, trigger, channel, enable=False),
        'set':       lambda: _cmd_set(bot, trigger, channel, args[1:]),
        'trigger':   lambda: _cmd_trigger(bot, trigger, channel, args[1:]),
        'copypasta': lambda: _cmd_copypasta(bot, trigger, channel, args[1:]),
        'help':      lambda: _cmd_help(bot, trigger),
    }

    handler = dispatch.get(subcmd)
    if handler:
        handler()
    else:
        bot.reply(
            f"⚠️ Unknown subcommand {B}{subcmd}{B}. "
            f"Try: {B}$spam help{B}"
        )


def _cmd_status(bot, trigger, channel):
    """Show antispam status for the given channel."""
    settings = _get_settings(bot, channel)
    enabled = _is_channel_enabled(bot, channel)
    icon = "✅" if enabled else "❌"
    triggers = _get_triggers(bot, channel)

    with bot.memory['spam_lock']:
        active = sum(1 for (ch, _) in bot.memory['spam_messages'] if ch == channel)

    bot.say(
        f"🛡️ {B}Antispam Status{B} for {B}{channel}{B}{SEP}"
        f"{icon} {'Enabled' if enabled else 'Disabled'}{SEP}"
        f"⏱️ Window: {B}{settings['window']}s{B}{SEP}"
        f"🎯 Threshold: {B}{settings['threshold']}{B} msgs{SEP}"
        f"🎨 Unicode: {B}{settings['unicode_threshold']}{B} msgs / {B}{settings['unicode_window']}s{B}{SEP}"
        f"🔑 Triggers: {B}{len(triggers)}{B}{SEP}"
        f"📊 Tracking: {B}{active}{B} user(s)"
    )


def _cmd_toggle(bot, trigger, channel, enable):
    """Enable or disable antispam for a channel."""
    enabled_channels = bot.db.get_plugin_value('antispam', 'enabled_channels') or []

    if enable:
        if channel not in [c.lower() for c in enabled_channels]:
            enabled_channels.append(channel)
        bot.db.set_plugin_value('antispam', 'enabled_channels', enabled_channels)
        bot.say(f"✅ Antispam protection {B}enabled{B} for {B}{channel}{B}")
    else:
        enabled_channels = [c for c in enabled_channels if c.lower() != channel]
        bot.db.set_plugin_value('antispam', 'enabled_channels', enabled_channels)
        bot.say(f"❌ Antispam protection {B}disabled{B} for {B}{channel}{B}")

    LOGGER.info("Antispam: %s in %s by %s", 'Enabled' if enable else 'Disabled', channel, trigger.nick)


def _cmd_set(bot, trigger, channel, args):
    """Adjust a setting. Usage: $spam [#chan] set <window|threshold|...> <value>"""
    valid = {
        'window': (3, 120),
        'threshold': (3, 30),
        'unicode_threshold': (2, 10),
        'unicode_window': (10, 120),
    }

    if len(args) < 2:
        bot.reply(
            f"Usage: {B}$spam set{B} <{'|'.join(valid)}> <value>"
        )
        return

    param = args[0].lower()
    if param not in valid:
        bot.reply(
            f"⚠️ Unknown parameter. Valid: "
            + ", ".join(f"{B}{p}{B}" for p in valid)
        )
        return

    try:
        value = int(args[1])
    except ValueError:
        return bot.reply("⚠️ Value must be a number.")

    lo, hi = valid[param]
    if value < lo or value > hi:
        return bot.reply(f"⚠️ {B}{param}{B} must be between {lo} and {hi}.")

    _save_setting(bot, channel, param, value)
    bot.say(f"✅ Antispam {B}{param}{B} set to {B}{value}{B} for {B}{channel}{B}")
    LOGGER.info("Antispam: %s → %d in %s by %s", param, value, channel, trigger.nick)


def _cmd_trigger(bot, trigger, channel, args):
    """Manage trigger phrases. Usage: $spam [#chan] trigger <add|del|list> [phrase]"""
    subcmd = args[0].lower() if args else 'list'

    if subcmd == 'list':
        triggers = _get_triggers(bot, channel)
        if not triggers:
            bot.say(f"📋 No trigger phrases set for {B}{channel}{B}.")
        else:
            bot.say(f"📋 {B}Trigger Phrases{B} for {B}{channel}{B} ({len(triggers)}):")
            for i, phrase in enumerate(triggers, 1):
                bot.say(f"  {i}. {phrase}")
        return

    if subcmd == 'add':
        if len(args) < 2:
            return bot.reply(f"Usage: {B}$spam trigger add{B} <phrase>")
        phrase = ' '.join(args[1:])
        triggers = _get_triggers(bot, channel)
        # Check for duplicates (case-insensitive)
        if phrase.lower() in [t.lower() for t in triggers]:
            return bot.reply(f"⚠️ Trigger already exists: {B}{phrase}{B}")
        triggers.append(phrase)
        _save_triggers(bot, channel, triggers)
        bot.say(f"✅ Added trigger for {B}{channel}{B}: {B}{phrase}{B}")
        LOGGER.info("Antispam: Added trigger '%s' in %s by %s", phrase, channel, trigger.nick)
        return

    if subcmd in ('del', 'rm', 'remove'):
        if len(args) < 2:
            return bot.reply(f"Usage: {B}$spam trigger del{B} <phrase or number>")
        raw = ' '.join(args[1:])
        triggers = _get_triggers(bot, channel)

        # Allow deletion by number
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(triggers):
                removed = triggers.pop(idx)
                _save_triggers(bot, channel, triggers)
                bot.say(f"✅ Removed trigger from {B}{channel}{B}: {B}{removed}{B}")
                LOGGER.info("Antispam: Removed trigger '%s' in %s by %s", removed, channel, trigger.nick)
                return
        except ValueError:
            pass

        # Delete by phrase match (case-insensitive)
        new_triggers = [t for t in triggers if t.lower() != raw.lower()]
        if len(new_triggers) == len(triggers):
            return bot.reply(f"⚠️ Trigger not found: {B}{raw}{B}")
        _save_triggers(bot, channel, new_triggers)
        bot.say(f"✅ Removed trigger from {B}{channel}{B}: {B}{raw}{B}")
        LOGGER.info("Antispam: Removed trigger '%s' in %s by %s", raw, channel, trigger.nick)
        return

    bot.reply(f"⚠️ Usage: {B}$spam trigger{B} <add|del|list> [phrase]")


def _cmd_copypasta(bot, trigger, channel, args):
    """Manage copypasta fingerprint DB. Usage: $spam [#chan] copypasta <status|clear>"""
    subcmd = args[0].lower() if args else 'status'

    if subcmd == 'status':
        shingles = _get_spam_shingles(bot, channel)
        ai_status = "✅ ON" if GROK_SPAM_ENABLED else "❌ OFF"
        bot.say(
            f"🧬 {B}Copypasta DB{B} for {B}{channel}{B}{SEP}"
            f"📊 Fingerprints: {B}{len(shingles)}{B} shingles{SEP}"
            f"🤖 AI Classification: {ai_status}{SEP}"
            f"📏 Min length: {B}{COPYPASTA_MIN_LENGTH}{B} chars{SEP}"
            f"🎯 Match ratio: {B}{int(COPYPASTA_MATCH_RATIO * 100)}%{B}"
        )
        return

    if subcmd == 'clear':
        _save_spam_shingles(bot, channel, set())
        bot.say(f"🗑️ Cleared copypasta fingerprint DB for {B}{channel}{B}")
        LOGGER.info("Antispam: Copypasta DB cleared for %s by %s", channel, trigger.nick)
        return

    bot.reply(f"⚠️ Usage: {B}$spam copypasta{B} <status|clear>")


def _cmd_help(bot, trigger):
    """Send the command reference via NOTICE."""
    nick = trigger.nick
    bot.notice(f"🛡️ {B}Antispam Protection — Spam Detection & Auto-Kick{B}", nick)
    bot.notice(" ", nick)
    bot.notice(f"  In a channel, the channel is implicit.", nick)
    bot.notice(f"  In PM, prefix with #channel:  {B}$spam #chan trigger add ...\n{B}", nick)
    bot.notice(" ", nick)
    bot.notice(f"  {B}$spam{B}                                  — Status for current channel", nick)
    bot.notice(f"  {B}$spam on{B} / {B}off{B}                          — Enable / disable in this channel", nick)
    bot.notice(f"  {B}$spam set window <sec>{B}                  — Rate detection window (3–120s, default {DEFAULT_WINDOW})", nick)
    bot.notice(f"  {B}$spam set threshold <n>{B}                  — Message count to trigger (3–30, default {DEFAULT_THRESHOLD})", nick)
    bot.notice(f"  {B}$spam set unicode_threshold <n>{B}          — Unicode art lines to trigger (2–10, default {DEFAULT_UNICODE_THRESHOLD})", nick)
    bot.notice(f"  {B}$spam set unicode_window <sec>{B}           — Unicode art window (10–120s, default {DEFAULT_UNICODE_WINDOW})", nick)
    bot.notice(f"  {B}$spam trigger list{B}                       — List trigger phrases", nick)
    bot.notice(f"  {B}$spam trigger add <phrase>{B}               — Add a trigger phrase (instant kick on match)", nick)
    bot.notice(f"  {B}$spam trigger del <phrase|#>{B}             — Remove by phrase or number", nick)
    bot.notice(f"  {B}$spam copypasta status{B}                   — Show copypasta fingerprint DB stats", nick)
    bot.notice(f"  {B}$spam copypasta clear{B}                    — Wipe the copypasta DB", nick)
    bot.notice(f"  {B}$spam help{B}                               — This help message", nick)
    bot.notice(" ", nick)
    bot.notice(
        f"📝 Four detection modes: (1) Rate — kicks if a user sends >= threshold "
        f"msgs within the window. (2) Content — instant kick if a message "
        f"contains any trigger phrase. (3) Copypasta — fingerprints long messages; "
        f"when a spammer is kicked, their text is learned and future matches are "
        f"auto-kicked. (4) Grok AI — classifies long messages as copypasta spam "
        f"vs normal trolling. Users with +h or higher are exempt. "
        f"No bans, just kicks. Off by default — use $spam on to enable.",
        nick,
    )
    bot.say(f"📬 {B}{nick}{B}, check your notices for antispam command help!")

