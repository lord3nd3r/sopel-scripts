# -*- coding: utf-8 -*-
"""
seen.py — Track the last time a user was seen speaking in a channel.

$seen <nick>  — reports when and where they were last seen and what they said.

On first load, backfills from all Sopel raw logs in ~/.sopel/logs/ so history
goes back as far as the logs do.
"""

import calendar
import glob
import logging
import os
import re
import sqlite3
import threading
import time

from sopel import plugin

LOG = logging.getLogger(__name__)

DB_PATH  = os.path.expanduser('~/.sopel/seen.db')
LOG_DIR  = os.path.expanduser('~/.sopel/logs')
_db_lock = threading.Lock()

# Matches the timestamp + inbound direction on a raw log line
_TS_RE     = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+<<')
# Matches an IRC PRIVMSG prefix
_IRC_RE    = re.compile(r':([^!@\s]+)[^\s]*\s+PRIVMSG\s+(#\S+)\s+:(.*)')
# Matches a CTCP ACTION (escaped form as written by Sopel's raw logger)
_ACTION_RE = re.compile(r'\\x01ACTION\s+(.*?)\\x01')


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


# ─────────────────────────── helpers ────────────────────────────────

def _update_seen(nick, channel, message, ts=None):
    """Upsert a seen record. Only overwrites if ts is newer than stored."""
    nick_lower = nick.lower()
    epoch = ts if ts is not None else int(time.time())
    with _db_lock, _get_conn() as conn:
        conn.execute("""
            INSERT INTO seen (nick_lower, channel, nick, message, seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(nick_lower, channel) DO UPDATE SET
                nick    = excluded.nick,
                message = excluded.message,
                seen_at = excluded.seen_at
            WHERE excluded.seen_at > seen.seen_at
        """, (nick_lower, channel.lower(), nick, message, epoch))


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


# ─────────────────────────── log backfill ───────────────────────────

def _parse_log_line(line):
    """
    Parse one line from a Sopel raw log.
    Returns (epoch, nick, channel, message) or None.
    """
    if '<<' not in line or 'PRIVMSG' not in line:
        return None

    ts_m = _TS_RE.match(line)
    if not ts_m:
        return None

    # Everything after the << marker
    rest = line[ts_m.end():].strip()

    # Strip outer quote character (' or ")
    if rest and rest[0] in ('"', "'"):
        rest = rest[1:]

    # Strip trailing escaped \r\n and closing quote
    rest = re.sub(r'\\r\\n[\'"]?\s*$', '', rest)

    irc_m = _IRC_RE.match(rest)
    if not irc_m:
        return None

    nick, channel, text = irc_m.groups()

    # Skip CTCP messages that aren't ACTIONs
    action_m = _ACTION_RE.match(text)
    if action_m:
        message = f'* {nick} {action_m.group(1)}'
    elif text.startswith('\\x01'):
        return None
    else:
        message = text

    try:
        t = time.strptime(ts_m.group(1), '%Y-%m-%d %H:%M:%S')
        epoch = int(calendar.timegm(t))
    except ValueError:
        return None

    return epoch, nick, channel, message


def _backfill(bot_nick):
    """Parse all raw log files and populate the seen DB. Runs once ever."""
    with _db_lock, _get_conn() as conn:
        done = conn.execute(
            "SELECT 1 FROM seen_meta WHERE key = 'backfill_done'"
        ).fetchone()
    if done:
        LOG.info('seen: backfill already done, skipping')
        return

    LOG.info('seen: starting log backfill from %s', LOG_DIR)

    # Collect all raw log files; dated files sort before current by date suffix
    all_files = glob.glob(os.path.join(LOG_DIR, '*.raw.log*'))

    def _sort_key(f):
        base = os.path.basename(f)
        # e.g. 'glitchy.raw.log.2025-12-06' → date portion sorts correctly
        m = re.search(r'(\d{4}-\d{2}-\d{2})$', base)
        return m.group(1) if m else '9999-99-99'  # current file sorts last

    all_files.sort(key=_sort_key)

    bot_nick_lower = bot_nick.lower()
    count = 0

    for filepath in all_files:
        try:
            with open(filepath, 'r', errors='replace') as fh:
                for line in fh:
                    result = _parse_log_line(line)
                    if result is None:
                        continue
                    epoch, nick, channel, message = result
                    if nick.lower() == bot_nick_lower:
                        continue
                    _update_seen(nick, channel, message, epoch)
                    count += 1
        except Exception:
            LOG.exception('seen: error reading %s', filepath)

    with _db_lock, _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO seen_meta (key, value) VALUES ('backfill_done', ?)",
            (str(int(time.time())),)
        )

    LOG.info('seen: backfill complete — %d entries processed', count)


# ─────────────────────────── lifecycle ──────────────────────────────

def setup(bot):
    _init_db()
    t = threading.Thread(target=_backfill, args=(bot.nick,), daemon=True)
    t.start()
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
