# operscan.py — PM-only IRC oper scanner for Sopel
# Scans a channel for IRC operators via WHO.
# Usage (PM only): $operscan #channel
#
# IRC operators appear with a '*' flag in the WHO reply (numeric 352).

from __future__ import annotations

import logging
import threading

from sopel import plugin

LOG = logging.getLogger(__name__)

# Keyed by lowercased channel name.
# Each entry: {'requester': str, 'opers': list[str], 'timer': Timer}
_scans: dict[str, dict] = {}
_scans_lock = threading.Lock()

_SCAN_TIMEOUT = 15  # seconds before giving up waiting for WHO replies


def _cleanup(channel: str) -> dict | None:
    """Remove and return a scan state entry, cancelling its timer."""
    with _scans_lock:
        state = _scans.pop(channel, None)
    if state and state.get('timer'):
        state['timer'].cancel()
    return state


def _timeout_scan(bot, channel: str) -> None:
    """Called if the WHO responses never arrive."""
    state = _cleanup(channel)
    if not state:
        return
    requester = state['requester']
    opers = state['opers']
    if opers:
        bot.say(f'IRC operators found in {channel} (scan timed out): {", ".join(opers)}', requester)
    else:
        bot.say(f'Scan of {channel} timed out — no IRC operators found so far.', requester)


@plugin.command('operscan')
@plugin.thread(True)
def operscan(bot, trigger):
    """$operscan #channel — PM only. Scan a channel for IRC operators."""
    if not trigger.is_privmsg:
        return

    target = (trigger.group(2) or '').strip()
    if not target or not target.startswith('#'):
        bot.say('Usage: $operscan #channel', trigger.nick)
        return

    channel_key = target.lower()

    if not bot.channels.get(channel_key):
        bot.say(f"I'm not in {target}.", trigger.nick)
        return

    with _scans_lock:
        if channel_key in _scans:
            bot.say(f'A scan of {target} is already in progress.', trigger.nick)
            return

    bot.say(f'Scanning {target} for IRC operators…', trigger.nick)

    timer = threading.Timer(_SCAN_TIMEOUT, _timeout_scan, args=(bot, channel_key))

    with _scans_lock:
        _scans[channel_key] = {
            'requester': trigger.nick,
            'opers': [],
            'timer': timer,
        }

    timer.start()
    bot.write(['WHO', target])


@plugin.rule('.*')
@plugin.event('352')
@plugin.priority('low')
def who_reply(bot, trigger):
    """Collect WHO reply lines, noting users with the IRC oper flag (*)."""
    # 352 params: botnick channel user host server nick flags :hopcount realname
    args = trigger.args
    if len(args) < 7:
        return

    channel_key = args[1].lower()

    with _scans_lock:
        state = _scans.get(channel_key)

    if not state:
        return

    nick = args[5]
    flags = args[6]   # e.g. "H*@"  — '*' means IRC oper

    if '*' in flags:
        with _scans_lock:
            if channel_key in _scans:
                _scans[channel_key]['opers'].append(nick)


@plugin.rule('.*')
@plugin.event('315')
@plugin.priority('low')
def end_of_who(bot, trigger):
    """Handle end-of-WHO — report results to the requester."""
    # 315 params: botnick channel :End of /WHO list.
    args = trigger.args
    if len(args) < 2:
        return

    channel_key = args[1].lower()

    state = _cleanup(channel_key)
    if not state:
        return

    requester = state['requester']
    opers = state['opers']

    if opers:
        oper_list = ', '.join(opers)
        bot.say(f'IRC operators in {args[1]}: {oper_list}', requester)
    else:
        bot.say(f'No IRC operators found in {args[1]}.', requester)
