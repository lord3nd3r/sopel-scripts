# -*- coding: utf-8 -*-
"""
tell.py — Leave messages for offline users.

Usage:
  .tell <nick> <message>   — leave a message for <nick>
  .showtells               — privately list your pending tells (clears them)

When <nick> next speaks in any channel the bot is in, they receive a PM
per pending message: who sent it, when, and the text.
"""

import logging
import os
import sqlite3
import threading
import time

from sopel import plugin

LOG = logging.getLogger(__name__)

DB_PATH = os.path.expanduser('~/.sopel/tell.db')
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
            CREATE TABLE IF NOT EXISTS tells (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient   TEXT    NOT NULL COLLATE NOCASE,
                sender      TEXT    NOT NULL,
                channel     TEXT    NOT NULL,
                message     TEXT    NOT NULL,
                sent_at     INTEGER NOT NULL,
                delivered   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tells_recipient '
            'ON tells(recipient COLLATE NOCASE) WHERE delivered = 0'
        )


# ─────────────────────────── helpers ────────────────────────────────

def _store_tell(recipient, sender, channel, message):
    with _db_lock, _get_conn() as conn:
        conn.execute(
            'INSERT INTO tells (recipient, sender, channel, message, sent_at) '
            'VALUES (?, ?, ?, ?, ?)',
            (recipient.lower(), sender, channel, message, int(time.time()))
        )


def _fetch_tells(nick):
    """Return all undelivered tells for nick, mark them delivered."""
    nick_lower = nick.lower()
    with _db_lock, _get_conn() as conn:
        rows = conn.execute(
            'SELECT id, sender, channel, message, sent_at '
            'FROM tells WHERE recipient = ? AND delivered = 0 '
            'ORDER BY sent_at ASC',
            (nick_lower,)
        ).fetchall()
        if rows:
            ids = [r['id'] for r in rows]
            conn.execute(
                'UPDATE tells SET delivered = 1 WHERE id IN ({})'.format(
                    ','.join('?' * len(ids))
                ),
                ids
            )
    return rows


def _pending_count(nick):
    nick_lower = nick.lower()
    with _db_lock, _get_conn() as conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM tells WHERE recipient = ? AND delivered = 0',
            (nick_lower,)
        ).fetchone()
    return row[0] if row else 0


def _fmt_time(epoch):
    """Format epoch as a human-readable UTC string."""
    return time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(epoch))


def _deliver_tells(bot, nick):
    """Fetch and deliver all pending tells for nick via PM."""
    tells = _fetch_tells(nick)
    for row in tells:
        msg = (
            f'[Tell from \x02{row["sender"]}\x02 in {row["channel"]} '
            f'on {_fmt_time(row["sent_at"])}]: {row["message"]}'
        )
        bot.say(msg, nick)
    return len(tells)


# ─────────────────────────── lifecycle ──────────────────────────────

def setup(bot):
    _init_db()
    LOG.info('tell: plugin loaded')


# ─────────────────────────── commands ───────────────────────────────

@plugin.commands('tell')
@plugin.example('$tell SomeUser Hey, call me back!')
def cmd_tell(bot, trigger):
    """Leave a message for a user. Delivered via NOTICE when they next speak."""
    args = (trigger.group(2) or '').strip()
    if not args or ' ' not in args:
        bot.reply('Usage: $tell <nick> <message>')
        return

    recipient, _, message = args.partition(' ')
    message = message.strip()

    if not message:
        bot.reply('Usage: $tell <nick> <message>')
        return

    if recipient.lower() == bot.nick.lower():
        bot.reply("I can't take messages for myself.")
        return

    if recipient.lower() == trigger.nick.lower():
        bot.reply("You can't leave a message for yourself.")
        return

    channel = str(trigger.sender) if trigger.is_privmsg else str(trigger.sender)
    _store_tell(recipient, str(trigger.nick), channel, message)
    bot.reply(f'I will tell \x02{recipient}\x02 that when they next speak.')


@plugin.commands('showtells')
def cmd_showtells(bot, trigger):
    """Show your pending tells privately without waiting to speak."""
    count = _pending_count(str(trigger.nick))
    if count == 0:
        bot.say('You have no pending messages.', trigger.nick)
        return
    delivered = _deliver_tells(bot, str(trigger.nick))
    bot.say(f'{delivered} message(s) delivered above.', trigger.nick)


# ─────────────────────────── delivery trigger ───────────────────────

@plugin.rule('.*')
@plugin.priority('high')
@plugin.thread(True)
def check_tells(bot, trigger):
    """Deliver pending tells when a user speaks in a channel."""
    if not trigger.sender or trigger.is_privmsg:
        return
    nick = str(trigger.nick)
    if nick.lower() == bot.nick.lower():
        return
    if _pending_count(nick) == 0:
        return
    _deliver_tells(bot, nick)
