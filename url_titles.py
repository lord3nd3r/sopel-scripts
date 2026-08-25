# -*- coding: utf-8 -*-
"""
url_titles.py — Fetch and display the <title> of URLs posted in chat.

Ignores YouTube links (handled by youtube_titles.py).

Commands:
  $urltitle on   — enable URL title fetching in this channel (op / admin)
  $urltitle off  — disable URL title fetching in this channel (op / admin)
  $urltitle      — check whether URL title fetching is enabled
"""

import logging
import re
import threading

import requests
from bs4 import BeautifulSoup
from sopel import plugin

LOG = logging.getLogger(__name__)

PLUGIN_NAME = 'url_titles'
URL_RE = r'https?://[^\s>)"\']+'

# Domains handled by other plugins — skip them
SKIP_DOMAINS = re.compile(
    r'(?:youtube\.com|youtu\.be)',
    re.IGNORECASE
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}
MAX_BYTES  = 65_536   # read at most 64 KB to find the title
TIMEOUT    = 8
MAX_TITLE  = 200

# Channel toggle state: {channel_lower: bool}
_channel_toggles: dict[str, bool] | None = None
_toggles_lock = threading.Lock()


def _load_toggles(bot) -> dict[str, bool]:
    global _channel_toggles
    with _toggles_lock:
        if _channel_toggles is None:
            val = bot.db.get_plugin_value(PLUGIN_NAME, 'channel_toggles')
            _channel_toggles = val if isinstance(val, dict) else {}
        return _channel_toggles


def _save_toggles(bot, toggles: dict[str, bool]) -> None:
    bot.db.set_plugin_value(PLUGIN_NAME, 'channel_toggles', toggles)


def _is_enabled(bot, channel: str) -> bool:
    """Return True if URL title fetching is enabled in *channel* (defaults to True)."""
    toggles = _load_toggles(bot)
    return toggles.get(channel.lower(), True)


def _set_enabled(bot, channel: str, enabled: bool) -> None:
    toggles = _load_toggles(bot)
    toggles[channel.lower()] = enabled
    _save_toggles(bot, toggles)


def _is_op_or_admin(bot, trigger) -> bool:
    """Return True if *trigger* belongs to a channel op (+h or higher), admin, or owner."""
    if getattr(trigger, 'owner', False) or getattr(trigger, 'admin', False):
        return True
    try:
        cfg_admins = getattr(bot.config.core, 'admins', None)
        if isinstance(cfg_admins, (list, tuple, set)):
            if trigger.nick.lower() in {a.lower() for a in cfg_admins}:
                return True
    except Exception:
        pass
    channel_name = str(trigger.sender)
    try:
        chan = bot.channels.get(channel_name)
        if chan:
            priv = chan.privileges.get(trigger.nick, 0)
            if priv >= plugin.HALFOP:
                return True
    except Exception:
        pass
    return False


@plugin.command('urltitle', 'urltitles')
def urltitle_toggle(bot, trigger):
    """Enable or disable URL title fetching in this channel.

    Usage: $urltitle on | $urltitle off
    Requires channel op (halfop+) or bot admin/owner.
    """
    if not trigger.sender or not str(trigger.sender).startswith('#'):
        bot.reply('This command only works in a channel.')
        return

    arg = (trigger.group(2) or '').strip().lower()

    if arg not in ('on', 'off'):
        status = 'enabled 🟢' if _is_enabled(bot, str(trigger.sender)) else 'disabled 🔴'
        bot.reply(
            f'URL title fetching is currently {status} in {trigger.sender}. '
            "Use '$urltitle on' or '$urltitle off' to change it."
        )
        return

    if not _is_op_or_admin(bot, trigger):
        bot.reply('⛔ You need to be a channel op or bot admin to change this setting.')
        return

    enable = (arg == 'on')
    _set_enabled(bot, str(trigger.sender), enable)

    if enable:
        bot.say(f'🔗 URL title fetching is now \x02enabled\x02 in {trigger.sender}.')
    else:
        bot.say(f'🔕 URL title fetching is now \x02disabled\x02 in {trigger.sender}.')


@plugin.rule('.*')
@plugin.priority('low')
@plugin.thread(True)
def url_title(bot, trigger):
    if not trigger.sender or not str(trigger.sender).startswith('#'):
        return

    if not _is_enabled(bot, str(trigger.sender)):
        return

    raw = str(trigger.group(0) or '')
    m = re.search(URL_RE, raw)
    if not m:
        return
    url = re.sub(r'[>)\]\'\".,!?]+$', '', m.group(0))

    if SKIP_DOMAINS.search(url):
        return

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return

        raw_html = b''
        for chunk in resp.iter_content(chunk_size=4096):
            raw_html += chunk
            if len(raw_html) >= MAX_BYTES:
                break

        encoding = resp.apparent_encoding or 'utf-8'
        html = raw_html.decode(encoding, errors='replace')

    except Exception:
        return

    try:
        soup = BeautifulSoup(html, 'html.parser')
        tag = soup.find('title')
        if not tag or not tag.string:
            return
        title = ' '.join(tag.string.strip().split())
    except Exception:
        return

    if not title:
        return

    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip() + '…'

    bot.say(f'\x02[\x02 {title} \x02]\x02')
