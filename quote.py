# -*- coding: utf-8 -*-
"""
quote.py — Quote system for Sopel
Commands (all triggered with !quote):
  !quote                     — random quote (current channel)
  !quote <id>                — get quote by ID
  !quote add <nick> <text>   — add a quote attributed to <nick>
  !quote search <term>       — search quotes by text or nick
  !quote by <nick>           — random quote attributed to <nick>
  !quote del <id>            — delete a quote (admins/owner only)
  !quote count               — total quotes in this channel
  !quote last                — most recently added quote
  !quote info <id>           — who added it and when
  !quote top                 — top 5 most-quoted nicks

Database: ~/.sopel/quotes.db  (SQLite, one DB shared across all channels)
"""

import os
import sqlite3
import threading
import time
import datetime
import random
import logging

from sopel import plugin

log = logging.getLogger('sopel.modules.quote')

# ──────────────────────────────────────────────────────────────
# DB setup
# ──────────────────────────────────────────────────────────────
DB_PATH = os.path.expanduser('~/.sopel/quotes.db')
_db_lock = threading.Lock()


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db_lock, _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                channel   TEXT    NOT NULL COLLATE NOCASE,
                nick      TEXT    NOT NULL COLLATE NOCASE,
                text      TEXT    NOT NULL,
                added_by  TEXT    NOT NULL COLLATE NOCASE,
                added_at  TEXT    NOT NULL,
                deleted   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quotes_channel ON quotes(channel)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quotes_nick ON quotes(channel, nick)"
        )
        conn.commit()


# ──────────────────────────────────────────────────────────────
# Sopel lifecycle
# ──────────────────────────────────────────────────────────────
def setup(bot):
    _init_db()


# ──────────────────────────────────────────────────────────────
# IRC formatting helpers
# ──────────────────────────────────────────────────────────────
BOLD  = '\x02'
RESET = '\x0f'
CYAN  = '\x0312'
GREEN = '\x0303'
GREY  = '\x0314'


def _fmt_quote(row):
    """Format a quote row for IRC output."""
    return (
        f"{BOLD}#{row['id']}{RESET} "
        f"\"{row['text']}\" "
        f"{GREY}— {BOLD}{row['nick']}{RESET}"
    )


# ──────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────
def _add_quote(channel, nick, text, added_by):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    with _db_lock, _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO quotes (channel, nick, text, added_by, added_at) VALUES (?,?,?,?,?)",
            (channel, nick, text, added_by, ts)
        )
        conn.commit()
        return cur.lastrowid


def _get_by_id(channel, qid):
    with _db_lock, _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM quotes WHERE id=? AND channel=? AND deleted=0",
            (qid, channel)
        ).fetchone()


def _random_quote(channel, nick=None):
    with _db_lock, _get_conn() as conn:
        if nick:
            rows = conn.execute(
                "SELECT * FROM quotes WHERE channel=? AND nick=? AND deleted=0",
                (channel, nick)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM quotes WHERE channel=? AND deleted=0",
                (channel,)
            ).fetchall()
    return random.choice(rows) if rows else None


def _search_quotes(channel, term, limit=5):
    pattern = f"%{term}%"
    with _db_lock, _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM quotes WHERE channel=? AND deleted=0 "
            "AND (text LIKE ? OR nick LIKE ?) "
            "ORDER BY id DESC LIMIT ?",
            (channel, pattern, pattern, limit)
        ).fetchall()


def _delete_quote(channel, qid):
    with _db_lock, _get_conn() as conn:
        cur = conn.execute(
            "UPDATE quotes SET deleted=1 WHERE id=? AND channel=? AND deleted=0",
            (qid, channel)
        )
        conn.commit()
        return cur.rowcount > 0


def _count_quotes(channel):
    with _db_lock, _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM quotes WHERE channel=? AND deleted=0",
            (channel,)
        ).fetchone()
    return row['c'] if row else 0


def _last_quote(channel):
    with _db_lock, _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM quotes WHERE channel=? AND deleted=0 ORDER BY id DESC LIMIT 1",
            (channel,)
        ).fetchone()


def _top_nicks(channel, limit=5):
    with _db_lock, _get_conn() as conn:
        return conn.execute(
            "SELECT nick, COUNT(*) AS c FROM quotes "
            "WHERE channel=? AND deleted=0 "
            "GROUP BY nick ORDER BY c DESC LIMIT ?",
            (channel, limit)
        ).fetchall()


# ──────────────────────────────────────────────────────────────
# Permission helper
# ──────────────────────────────────────────────────────────────
def _is_admin(bot, trigger):
    return (
        trigger.admin
        or trigger.owner
        or bot.db.get_nick_value(trigger.nick, 'admin')
    )


# ──────────────────────────────────────────────────────────────
# Main command dispatcher
# ──────────────────────────────────────────────────────────────
@plugin.command('quote', 'q')
@plugin.example('!quote', 'Returns a random quote.')
@plugin.example('!quote 42', 'Returns quote #42.')
@plugin.example('!quote add Nick Said something funny', 'Adds a quote.')
@plugin.example('!quote search funny', 'Searches quotes for "funny".')
@plugin.example('!quote by Nick', 'Random quote attributed to Nick.')
@plugin.example('!quote del 42', 'Deletes quote #42 (admins only).')
@plugin.example('!quote count', 'Shows number of quotes.')
@plugin.example('!quote last', 'Shows the last added quote.')
@plugin.example('!quote info 42', 'Shows metadata for quote #42.')
@plugin.example('!quote top', 'Shows top 5 most-quoted nicks.')
def cmd_quote(bot, trigger):
    """Quote database. Subcommands: add, search, by, del, count, last, info, top.
    Use !quote <id> for a specific quote or !quote for a random one."""

    if not trigger.is_privmsg and not trigger.sender:
        bot.reply("Quotes only work in channels.")
        return

    channel = trigger.sender if not trigger.is_privmsg else None
    if channel is None:
        bot.reply("Quotes are channel-based; use me in a channel.")
        return

    args = (trigger.group(2) or '').strip()

    # ── !quote (no args) ─────────────────────────────────────
    if not args:
        q = _random_quote(channel)
        if q:
            bot.say(_fmt_quote(q))
        else:
            bot.reply("No quotes yet. Add one with: !quote add <nick> <text>")
        return

    parts = args.split(None, 1)
    sub   = parts[0].lower()
    rest  = parts[1].strip() if len(parts) > 1 else ''

    # ── !quote <number> ──────────────────────────────────────
    if sub.isdigit():
        q = _get_by_id(channel, int(sub))
        if q:
            bot.say(_fmt_quote(q))
        else:
            bot.reply(f"No quote #{sub} found in {channel}.")
        return

    # ── !quote add <nick> <text> ─────────────────────────────
    if sub == 'add':
        if not rest:
            bot.reply("Usage: !quote add <nick> <text>")
            return
        add_parts = rest.split(None, 1)
        if len(add_parts) < 2:
            bot.reply("Usage: !quote add <nick> <text>")
            return
        quoted_nick = add_parts[0]
        quote_text  = add_parts[1].strip()
        if not quote_text:
            bot.reply("Quote text can't be empty.")
            return
        qid = _add_quote(channel, quoted_nick, quote_text, str(trigger.nick))
        bot.say(f"{GREEN}Quote #{qid} added{RESET} \"{quote_text}\" — {quoted_nick}")
        return

    # ── !quote search <term> ─────────────────────────────────
    if sub == 'search':
        if not rest:
            bot.reply("Usage: !quote search <term>")
            return
        results = _search_quotes(channel, rest)
        if not results:
            bot.reply(f"No quotes matching \"{rest}\".")
            return
        bot.say(f"Found {len(results)} result(s) for \"{rest}\":")
        for row in results:
            bot.say(_fmt_quote(row))
        return

    # ── !quote by <nick> ─────────────────────────────────────
    if sub == 'by':
        if not rest:
            bot.reply("Usage: !quote by <nick>")
            return
        nick_arg = rest.split()[0]
        q = _random_quote(channel, nick=nick_arg)
        if q:
            bot.say(_fmt_quote(q))
        else:
            bot.reply(f"No quotes attributed to {nick_arg}.")
        return

    # ── !quote del <id> ──────────────────────────────────────
    if sub in ('del', 'delete', 'remove'):
        if not rest or not rest.split()[0].isdigit():
            bot.reply("Usage: !quote del <id>")
            return
        if not _is_admin(bot, trigger):
            bot.reply("Only admins can delete quotes.")
            return
        qid = int(rest.split()[0])
        if _delete_quote(channel, qid):
            bot.say(f"Quote #{qid} deleted.")
        else:
            bot.reply(f"No quote #{qid} in {channel} (or already deleted).")
        return

    # ── !quote count ─────────────────────────────────────────
    if sub == 'count':
        n = _count_quotes(channel)
        bot.say(f"{channel} has {BOLD}{n}{RESET} quote(s).")
        return

    # ── !quote last ──────────────────────────────────────────
    if sub == 'last':
        q = _last_quote(channel)
        if q:
            bot.say(_fmt_quote(q))
        else:
            bot.reply("No quotes yet.")
        return

    # ── !quote info <id> ─────────────────────────────────────
    if sub == 'info':
        if not rest or not rest.split()[0].isdigit():
            bot.reply("Usage: !quote info <id>")
            return
        qid = int(rest.split()[0])
        q = _get_by_id(channel, qid)
        if not q:
            bot.reply(f"No quote #{qid} in {channel}.")
            return
        bot.say(
            f"{BOLD}#{q['id']}{RESET} — "
            f"added by {BOLD}{q['added_by']}{RESET} "
            f"on {q['added_at']} UTC"
        )
        return

    # ── !quote top ───────────────────────────────────────────
    if sub == 'top':
        rows = _top_nicks(channel)
        if not rows:
            bot.reply("No quotes yet.")
            return
        medals = ['🥇', '🥈', '🥉', '4.', '5.']
        parts_out = [
            f"{medals[i]} {row['nick']} ({row['c']})"
            for i, row in enumerate(rows)
        ]
        bot.say(f"Top quoted in {channel}: {' | '.join(parts_out)}")
        return

    # ── !quote random ────────────────────────────────────────
    if sub == 'random':
        q = _random_quote(channel)
        if q:
            bot.say(_fmt_quote(q))
        else:
            bot.reply("No quotes yet.")
        return

    # ── fallback: treat whole arg string as a search ─────────
    results = _search_quotes(channel, args, limit=3)
    if results:
        bot.say(f"Search results for \"{args}\":")
        for row in results:
            bot.say(_fmt_quote(row))
    else:
        bot.reply(
            "Unknown subcommand. Try: add, search, by, del, count, last, info, top, random — or !quote <id>"
        )
