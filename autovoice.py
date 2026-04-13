"""
autovoice.py - Sopel auto-voice plugin based on chat activity.

Off by default. Enable per-channel with $autovoice on.
Requires the bot to have halfop+ in the channel.

Tracks message counts per user per channel. Once a user hits the
configured threshold they get +v. If they stop talking for a
configurable idle period (default: 7 days) the voice is removed.

Users who already have +v, +h, +o, +a, or +q are ignored entirely.
"""

import json
import logging
import os
import threading
import time

from sopel import module, plugin

LOG = logging.getLogger(__name__)

# ─── tunables ────────────────────────────────────────────────────────
MSG_THRESHOLD = 50           # messages needed to earn +v
IDLE_SECONDS = 7 * 86400     # 7 days without talking → devoice
SWEEP_INTERVAL = 15 * 60     # background sweep every 15 minutes
DATA_FILE = os.path.expanduser('~/.sopel/autovoice_data.json')
# ─────────────────────────────────────────────────────────────────────

# privilege bits used by Sopel internally
_PRIV_VOICE  = 1
_PRIV_HALFOP = 2
_PRIV_OP     = 4
_PRIV_ADMIN  = 8
_PRIV_OWNER  = 16

# runtime state
_data_lock = threading.RLock()
_data = None          # {"channels": {"#chan": {"nick": {"count": N, "last": epoch}}}}
_enabled = None       # {"#chan": bool}
_sweep_stop = threading.Event()
_sweep_thread = None


# ═══════════════════════════════ persistence ═════════════════════════

def _load():
    global _data, _enabled
    with _data_lock:
        if _data is not None:
            return
        if os.path.isfile(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    raw = json.load(f)
                _data = raw.get('channels', {})
                _enabled = raw.get('enabled', {})
            except Exception:
                LOG.exception('autovoice: failed to load %s', DATA_FILE)
                _data = {}
                _enabled = {}
        else:
            _data = {}
            _enabled = {}


def _save():
    with _data_lock:
        if _data is None:
            return
        payload = {'channels': _data, 'enabled': _enabled or {}}
    tmp = DATA_FILE + '.tmp'
    try:
        with open(tmp, 'w') as f:
            json.dump(payload, f)
        os.replace(tmp, DATA_FILE)
    except Exception:
        LOG.exception('autovoice: failed to save %s', DATA_FILE)


# ═══════════════════════════════ helpers ═════════════════════════════

def _bot_has_halfop(bot, channel):
    """Return True if the bot has halfop or higher in the channel."""
    try:
        chan = bot.channels.get(channel)
        if not chan:
            return False
        privs = getattr(chan, 'privileges', None) or {}
        for k, v in privs.items():
            if k.lower() == bot.nick.lower():
                return isinstance(v, int) and v >= _PRIV_HALFOP
        return False
    except Exception:
        return False


def _user_has_mode(bot, channel, nick):
    """Return True if the user already has +v, +h, +o, +a, or +q."""
    try:
        chan = bot.channels.get(channel)
        if not chan:
            return False
        privs = getattr(chan, 'privileges', None) or {}
        for k, v in privs.items():
            if k.lower() == nick.lower():
                return isinstance(v, int) and v >= _PRIV_VOICE
        return False
    except Exception:
        return False


def _user_privs(bot, channel, nick):
    """Return the privilege bitmask for a nick, 0 if unknown."""
    try:
        chan = bot.channels.get(channel)
        if not chan:
            return 0
        privs = getattr(chan, 'privileges', None) or {}
        for k, v in privs.items():
            if k.lower() == nick.lower():
                return v if isinstance(v, int) else 0
        return 0
    except Exception:
        return 0


def _nick_in_channel(bot, channel, nick_lower):
    """Check whether a nick is currently in the channel."""
    try:
        chan = bot.channels.get(channel)
        if not chan:
            return False
        privs = getattr(chan, 'privileges', None) or {}
        return any(k.lower() == nick_lower for k in privs)
    except Exception:
        return False


def _is_enabled(channel):
    """Check if autovoice is enabled for a channel."""
    _load()
    return (_enabled or {}).get(channel.lower(), False)


# ═══════════════════════════════ sweep ═══════════════════════════════

def _sweep(bot):
    """Voice users who hit the threshold; devoice users idle > IDLE_SECONDS."""
    _load()
    now = time.time()
    with _data_lock:
        channels = dict(_data) if _data else {}

    for channel, users in channels.items():
        if not _is_enabled(channel):
            continue
        if not _bot_has_halfop(bot, channel):
            continue

        to_voice = []
        to_devoice = []

        for nick_lower, info in list(users.items()):
            if not isinstance(info, dict):
                continue
            count = info.get('count', 0)
            last = info.get('last', 0)

            if not _nick_in_channel(bot, channel, nick_lower):
                continue

            privs = _user_privs(bot, channel, nick_lower)
            has_voice = (privs & _PRIV_VOICE) != 0
            has_higher = privs >= _PRIV_HALFOP  # +h, +o, +a, +q

            # Never touch users with halfop+
            if has_higher:
                continue

            idle = (now - last) > IDLE_SECONDS

            if count >= MSG_THRESHOLD and not has_voice and not idle:
                to_voice.append(nick_lower)
            elif has_voice and idle:
                to_devoice.append(nick_lower)

        # batch MODE changes (up to 4 per command to stay safe)
        _batch_mode(bot, channel, '+v', to_voice)
        _batch_mode(bot, channel, '-v', to_devoice)

        # reset count for devoiced users so they must re-earn +v
        with _data_lock:
            chan_data = _data.get(channel, {})
            for nick_lower in to_devoice:
                if nick_lower in chan_data and isinstance(chan_data[nick_lower], dict):
                    chan_data[nick_lower]['count'] = 0

        # clean out idle entries from data so file doesn't grow forever
        with _data_lock:
            chan_data = _data.get(channel, {})
            for nick_lower in list(chan_data):
                info = chan_data[nick_lower]
                if isinstance(info, dict) and (now - info.get('last', 0)) > (IDLE_SECONDS * 2):
                    del chan_data[nick_lower]

    _save()


def _batch_mode(bot, channel, mode_str, nicks):
    """Apply a mode to a list of nicks in batches of 4."""
    if not nicks:
        return
    sign = mode_str[0]   # + or -
    char = mode_str[1]   # v
    for i in range(0, len(nicks), 4):
        batch = nicks[i:i+4]
        flags = sign + (char * len(batch))
        params = ' '.join(batch)
        bot.write(['MODE', channel, flags, params])
        LOG.info('autovoice: %s %s in %s', flags, params, channel)


def _start_sweep(bot):
    global _sweep_thread
    _sweep_stop.clear()

    def _loop():
        _sweep_stop.wait(60)  # let bot join channels first
        while not _sweep_stop.is_set():
            try:
                _sweep(bot)
            except Exception:
                LOG.exception('autovoice: sweep error')
            _sweep_stop.wait(SWEEP_INTERVAL)

    _sweep_thread = threading.Thread(target=_loop, daemon=True)
    _sweep_thread.start()


# ═══════════════════════════════ lifecycle ═══════════════════════════

def setup(bot):
    _load()
    _start_sweep(bot)
    LOG.info('autovoice: plugin loaded')


def shutdown(bot):
    _sweep_stop.set()
    _save()
    LOG.info('autovoice: plugin shutdown')


# ═══════════════════════════════ message tracking ════════════════════

@module.rule('.*')
@module.priority('low')
@plugin.thread(True)
def track_message(bot, trigger):
    """Track every channel message for activity counting."""
    if not trigger.sender or not str(trigger.sender).startswith('#'):
        return
    channel = str(trigger.sender).lower()
    if not _is_enabled(channel):
        return
    nick = str(trigger.nick)
    nick_lower = nick.lower()
    if nick_lower == bot.nick.lower():
        return

    _load()
    now = time.time()
    with _data_lock:
        chan_data = _data.setdefault(channel, {})
        rec = chan_data.setdefault(nick_lower, {'count': 0, 'last': 0, 'nick': nick})
        rec['count'] = rec.get('count', 0) + 1
        rec['last'] = now
        rec['nick'] = nick  # keep display nick fresh
        count = rec['count']

    # Check if this message just pushed them over the threshold
    if count == MSG_THRESHOLD:
        if _bot_has_halfop(bot, channel) and not _user_has_mode(bot, channel, nick):
            bot.write(['MODE', channel, '+v', nick])
            LOG.info('autovoice: +v %s in %s (hit %d msgs)', nick, channel, MSG_THRESHOLD)

    # Periodic save (every 50 messages across all channels)
    if int(now) % 50 == 0:
        _save()


# ═══════════════════════════════ admin commands ══════════════════════

@module.commands('autovoice')
@module.example('$autovoice on')
@module.example('$autovoice off')
@module.example('$autovoice status')
@module.example('$autovoice reset <nick>')
def autovoice_cmd(bot, trigger):
    """Toggle autovoice for the current channel, check status, or reset a user."""
    if not trigger.sender or not str(trigger.sender).startswith('#'):
        bot.reply('This command only works in a channel.')
        return

    channel = str(trigger.sender).lower()
    nick = trigger.nick

    # require halfop+ to manage
    privs = _user_privs(bot, channel, nick)
    if privs < _PRIV_HALFOP and not trigger.admin:
        bot.reply('You need halfop or higher to manage autovoice.')
        return

    args = (trigger.group(2) or '').strip().lower().split()
    subcmd = args[0] if args else 'status'

    _load()

    if subcmd in ('on', 'enable'):
        with _data_lock:
            _enabled[channel] = True
        _save()
        bot.say('Autovoice \x02enabled\x02 for this channel.')

    elif subcmd in ('off', 'disable'):
        with _data_lock:
            _enabled[channel] = False
        _save()
        bot.say('Autovoice \x02disabled\x02 for this channel.')

    elif subcmd == 'status':
        on = _is_enabled(channel)
        with _data_lock:
            tracked = len((_data or {}).get(channel, {}))
        state = '\x0303ON\x03' if on else '\x0304OFF\x03'
        bot.say(f'Autovoice is {state} | Tracking \x02{tracked}\x02 users | '
                f'Threshold: {MSG_THRESHOLD} msgs | Idle timeout: {IDLE_SECONDS // 86400}d')

    elif subcmd == 'reset':
        target = args[1] if len(args) > 1 else None
        if not target:
            bot.reply('Usage: $autovoice reset <nick>')
            return
        target_lower = target.lower()
        with _data_lock:
            chan_data = (_data or {}).get(channel, {})
            if target_lower in chan_data:
                del chan_data[target_lower]
                _save()
                bot.say(f'Reset activity data for \x02{target}\x02.')
            else:
                bot.reply(f'No data found for {target}.')

    elif subcmd == 'threshold':
        bot.say(f'Current threshold: \x02{MSG_THRESHOLD}\x02 messages to earn +v, '
                f'\x02{IDLE_SECONDS // 86400}\x02 days idle to lose it.')

    else:
        bot.reply('Usage: $autovoice <on|off|status|reset <nick>|threshold>')
