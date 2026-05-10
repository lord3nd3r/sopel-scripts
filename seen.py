# -*- coding: utf-8 -*-
"""
seen.py — Track the last time a user was seen speaking in a channel.

$seen <nick>  — reports when and where they were last seen and what they said.
"""

import logging
import os
import sqlite3
import threading
import time

from sopel import plugin

LOG = logging.getLogger(__name__)

DB_PATH = os.path.expanduser('~/.sopel/seen.db')
_db_lock = threading.Lock()


# ─────────────────────────── database ───────────────────────────────

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def _init_db():
    with _db_lock, _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen (
                nick_lower  TEXT    NOT NULL,
                channel     TEXT    NOT NULL COLLATE NOCASE,
                nick        TEXT    NOT NULL,
                message     TEXT    NOT NULL,
                seen_at     INTEGER NOT NULL,
                PRIMARY KEY (nick_lower, channel)
            )
        """)


# ─────────────────────────── helpers ────────────────────────────────

def _update_seen(nick, channel, message):
    nick_lower = nick.lower()
    with _db_lock, _get_conn() as conn:
        conn.execute("""
            INSERT INTO seen (nick_lower, channel, nick, message, seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nick_lower, channel) DO UPDATE SET
                nick    = excluded.nick,
                message = excluded.message,
                seen_at = excluded.seen_at
        """, (nick_lower, channel.lower(), nick, message, int(time.time())))


def _get_seen(nick, channel=None):
    """
    Look up a nick. If channel is given, search that channel first then fall
    back to the most recent record across all channels.
    """
    nick_lower = nick.lower()
    with _db_lock, _get_conn() as conn:
        if channel:
            row = conn.execute(
                'SELECT * FROM seen WHERE nick_lower = ? AND channel = ?',
                (nick_lower, channel.lower())
            ).fetchone()
            if row:
                return row
        # global fallback: most recent record
        return conn.execute(
            'SELECT * FROM seen WHERE nick_lower = ? ORDER BY seen_at DESC LIMIT 1',
            (nick_lower,)
        ).fetchone()


def _fmt_ago(epoch):
    """Return a human-friendly 'X ago' string."""
    delta = int(time.time()) - epoch
    if delta < 60:
        return f'{delta}s ago'
    if delta < 3600:
        m = delta // 60
        return f'{m}m ago'
    if delta < 86400:
        h = delta // 3600
        m = (delta % 3600) // 60
        return f'{h}h {m}m ago'
    d = delta // 86400
    h = (delta % 86400) // 3600
    return f'{d}d {h}h ago'


# ─────────────────────────── lifecycle ──────────────────────────────

def setup(bot):
    _init_db()
    LOG.info('seen: plugin loaded')


# ─────────────────────────── tracking ───────────────────────────────

@plugin.rule('.*')
@plugin.priority('low')
@plugin.thread(True)
def track_message(bot, trigger):
    """Record every channel message."""
    if not trigger.sender or trigger.is_privmsg:
        return
    nick = str(trigger.nick)
    if nick.lower() == bot.nick.lower():
        return
    channel = str(trigger.sender)
    _update_seen(nick, channel, trigger.group(0) or '')


@plugin.action_command('.*')
@plugin.priority('low')
@plugin.thread(True)
def track_action(bot, trigger):
    """Record /me actions."""
    if not trigger.sender or trigger.is_privmsg:
        return
    nick = str(trigger.nick)
    if nick.lower() == bot.nick.lower():
        return
    channel = str(trigger.sender)
    _update_seen(nick, channel, f'* {nick} {trigger.group(0)}')


# ─────────────────────────── command ────────────────────────────────

@plugin.commands('seen')
@plugin.example('$seen SomeUser')
def cmd_seen(bot, trigger):
    """<nick> — Report when a user was last seen in this channel."""
    target = (trigger.group(2) or '').strip()
    if not target:
        bot.reply('Usage: $seen <nick>')
        return

    if target.lower() == bot.nick.lower():
        bot.say("I'm right here!")
        return

    if target.lower() == trigger.nick.lower():
        bot.reply("You're right here!")
        return

    channel = str(trigger.sender) if not trigger.is_privmsg else None
    row = _get_seen(target, channel)

    if not row:
        bot.say(f"I haven't seen \x02{target}\x02.")
        return

    ago = _fmt_ago(row['seen_at'])
    chan = row['channel']
    msg  = row['message']

    # truncate long messages
    if len(msg) > 200:
        msg = msg[:197] + '...'

    bot.say(f"\x02{row['nick']}\x02 was last seen in \x02{chan}\x02 {ago}: {msg}")
