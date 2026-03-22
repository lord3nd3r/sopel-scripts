"""
chanstats.py - Sopel port of arfer's Eggdrop chanstats.tcl (2026 edition)
Author: Kristopher Craig + original by arfer
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

from sopel import plugin

LOGGER = logging.getLogger(__name__)

# ========================= CONFIG =========================
SAVE_EVERY_EVENTS = 20      # flush idle-prune after this many events
SAVE_EVERY_MINUTES = 10     # also prune on this interval
IDLE_DAYS = 2               # discard nicks unseen for this long
IGNORE_GUESTS = True        # skip guestXXXX nicks
B = "\x02"                  # bold
B_OFF = "\x02"              # bold off (toggle)
COLOR_RESET = "\x03"
SEP = "\x0314 · \x03"       # grey dot separator
# ==========================================================

VALID_FIELDS = frozenset({
    "lines", "words", "actions", "kicks", "bans",
    "joins", "parts", "splits", "quits", "nickchanges",
})


# ====================== DB HELPERS ======================

def setup(bot):
    db_dir = getattr(bot.config.core, "db_dir", None) or os.path.expanduser("~/.sopel")
    db_path = os.path.join(db_dir, "chanstats.db")
    bot.memory["chanstats_db"] = db_path
    bot.memory["chanstats_count"] = 0

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
                 channel TEXT NOT NULL,
                 nick TEXT NOT NULL,
                 lines INTEGER DEFAULT 0,
                 words INTEGER DEFAULT 0,
                 actions INTEGER DEFAULT 0,
                 kicks INTEGER DEFAULT 0,
                 bans INTEGER DEFAULT 0,
                 joins INTEGER DEFAULT 0,
                 parts INTEGER DEFAULT 0,
                 splits INTEGER DEFAULT 0,
                 quits INTEGER DEFAULT 0,
                 nickchanges INTEGER DEFAULT 0,
                 last_seen INTEGER,
                 PRIMARY KEY (channel, nick))''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_stats_channel ON stats(channel)")
    conn.commit()
    conn.close()
    LOGGER.info("chanstats: database ready at %s", db_path)


def _get_db(bot):
    conn = sqlite3.connect(bot.memory["chanstats_db"])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def accrue(bot, nick, channel, field, amount=1):
    """Increment a stat field for nick in channel."""
    if field not in VALID_FIELDS:
        return
    if amount <= 0:
        return
    if IGNORE_GUESTS and nick.lower().startswith("guest") and len(nick) > 5 and nick[-4:].isdigit():
        return
    if not str(channel).startswith("#"):
        return

    nick = nick.lower()
    channel = str(channel).lower()
    now = int(time.time())

    conn = _get_db(bot)
    try:
        # field is validated against VALID_FIELDS above — safe to format
        conn.execute(
            f"""INSERT INTO stats (channel, nick, last_seen, {field})
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel, nick) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    {field} = {field} + ?""",
            (channel, nick, now, amount, amount),
        )
        conn.commit()
    except Exception:
        LOGGER.exception("chanstats: accrue error for %s/%s/%s", channel, nick, field)
    finally:
        conn.close()

    bot.memory["chanstats_count"] = bot.memory.get("chanstats_count", 0) + 1
    if bot.memory["chanstats_count"] >= SAVE_EVERY_EVENTS:
        _prune_idle(bot, "events")
        bot.memory["chanstats_count"] = 0


def _prune_idle(bot, reason="manual"):
    """Remove records for nicks not seen within IDLE_DAYS."""
    conn = _get_db(bot)
    try:
        cutoff = int(time.time()) - (IDLE_DAYS * 86400)
        cur = conn.execute("DELETE FROM stats WHERE last_seen < ?", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
    except Exception:
        LOGGER.exception("chanstats: prune error")
        deleted = 0
    finally:
        conn.close()

    if deleted:
        LOGGER.info("chanstats: pruned %d idle records (%s)", deleted, reason)


# ====================== EVENT HANDLERS ======================

@plugin.thread(True)
@plugin.rule(".*")
def pubmsg(bot, trigger):
    """Track lines, words, and /me actions for channel messages."""
    if not str(trigger.sender).startswith("#"):
        return
    if trigger.nick == bot.nick:
        return

    raw = trigger.raw or ""
    if "\x01ACTION" in raw:
        accrue(bot, trigger.nick, trigger.sender, "actions")
        return

    text = trigger.group(0) or ""
    accrue(bot, trigger.nick, trigger.sender, "lines")
    word_count = len(text.split())
    if word_count > 0:
        accrue(bot, trigger.nick, trigger.sender, "words", word_count)


@plugin.thread(True)
@plugin.event("KICK")
@plugin.rule(".*")
def on_kick(bot, trigger):
    """Track kicks given."""
    if str(trigger.sender).startswith("#"):
        accrue(bot, trigger.nick, trigger.sender, "kicks")


@plugin.thread(True)
@plugin.event("MODE")
@plugin.rule(".*")
def on_mode(bot, trigger):
    """Track bans set (+b)."""
    raw = trigger.raw or ""
    if "+b" in raw and str(trigger.sender).startswith("#"):
        accrue(bot, trigger.nick, trigger.sender, "bans")


@plugin.thread(True)
@plugin.event("JOIN")
@plugin.rule(".*")
def on_join(bot, trigger):
    if str(trigger.sender).startswith("#"):
        if trigger.nick != bot.nick:
            accrue(bot, trigger.nick, trigger.sender, "joins")


@plugin.thread(True)
@plugin.event("PART")
@plugin.rule(".*")
def on_part(bot, trigger):
    if str(trigger.sender).startswith("#"):
        accrue(bot, trigger.nick, trigger.sender, "parts")


@plugin.thread(True)
@plugin.event("QUIT")
@plugin.rule(".*")
def on_quit(bot, trigger):
    """Track quits. Detect netsplits by quit message format (server1 server2)."""
    quit_msg = trigger.group(0) or ""
    pieces = quit_msg.strip().split()
    is_split = (
        len(pieces) == 2
        and "." in pieces[0]
        and "." in pieces[1]
    )
    field = "splits" if is_split else "quits"

    for chan in bot.channels:
        if trigger.nick in bot.channels[chan].users:
            accrue(bot, trigger.nick, chan, field)


@plugin.thread(True)
@plugin.event("NICK")
@plugin.rule(".*")
def on_nickchange(bot, trigger):
    """Track nick changes."""
    old_nick = trigger.nick
    for chan in bot.channels:
        if old_nick in bot.channels[chan].users:
            accrue(bot, old_nick, chan, "nickchanges")


# ====================== HELPER FUNCTIONS ======================

def _fmt_duration(seconds):
    """Format seconds into a compact human-readable string."""
    if seconds < 0:
        seconds = 0
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


# ====================== COMMANDS ======================

@plugin.thread(True)
@plugin.command("stats")
def cmd_stats(bot, trigger):
    """$stats [nick] [#channel] — Show stats for a user."""
    text = (trigger.group(2) or "").strip().split()
    nick = None
    chan = None

    for arg in text:
        if arg.startswith("#"):
            chan = arg.lower()
        elif nick is None:
            nick = arg.lower()

    if nick is None:
        nick = trigger.nick.lower()
    if chan is None:
        chan = str(trigger.sender).lower()

    if not chan.startswith("#"):
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Use this in a channel or specify one.")
        return

    conn = _get_db(bot)
    try:
        row = conn.execute(
            "SELECT lines, words, actions, kicks, bans, joins, parts, splits, quits, nickchanges, last_seen "
            "FROM stats WHERE channel=? AND nick=?",
            (chan, nick),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        bot.say(f"\x0304⚠{COLOR_RESET} No stats for {B}{nick}{B_OFF} in {B}{chan}{B_OFF}.")
        return

    lines, words, actions, kicks, bans, joins, parts, splits, quits, nicks, last_seen = row
    ago = int(time.time()) - (last_seen or 0)

    bot.say(
        f"📊 {B}{nick}{B_OFF} in {B}{chan}{B_OFF}{SEP}"
        f"💬 Lines: {B}{lines:,}{B_OFF}{SEP}"
        f"📝 Words: {B}{words:,}{B_OFF}{SEP}"
        f"🎭 Actions: {B}{actions:,}{B_OFF}{SEP}"
        f"🚪 Joins: {B}{joins:,}{B_OFF}{SEP}"
        f"👋 Parts: {B}{parts:,}{B_OFF}"
    )
    # Second line for less-common stats + last seen
    extras = []
    if kicks:
        extras.append(f"🦵 Kicks: {B}{kicks:,}{B_OFF}")
    if bans:
        extras.append(f"🔨 Bans: {B}{bans:,}{B_OFF}")
    if splits:
        extras.append(f"💥 Splits: {B}{splits:,}{B_OFF}")
    if quits:
        extras.append(f"🚫 Quits: {B}{quits:,}{B_OFF}")
    if nicks:
        extras.append(f"🔄 Nicks: {B}{nicks:,}{B_OFF}")
    extras.append(f"🕐 Last seen: {B}{_fmt_duration(ago)}{B_OFF} ago")
    bot.say(SEP.join(extras))


@plugin.thread(True)
@plugin.command("rank")
def cmd_rank(bot, trigger):
    """$rank [field] [#channel] — Top 10 users for a stat. Default: lines."""
    text = (trigger.group(2) or "").strip().split()

    field = "lines"
    chan = str(trigger.sender).lower()

    for arg in text:
        if arg.startswith("#"):
            chan = arg.lower()
        elif arg.lower() in VALID_FIELDS:
            field = arg.lower()

    if not chan.startswith("#"):
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Use this in a channel or specify one.")
        return

    conn = _get_db(bot)
    try:
        # field is validated against VALID_FIELDS — safe to format
        rows = conn.execute(
            f"SELECT nick, {field} FROM stats "
            f"WHERE channel=? AND {field} > 0 "
            f"ORDER BY {field} DESC LIMIT 10",
            (chan,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        bot.say(f"\x0304⚠{COLOR_RESET} No {B}{field}{B_OFF} stats for {B}{chan}{B_OFF}.")
        return

    # Field emoji map for the header
    field_emoji = {
        "lines": "💬", "words": "📝", "actions": "🎭", "kicks": "🦵",
        "bans": "🔨", "joins": "🚪", "parts": "👋", "splits": "💥",
        "quits": "🚫", "nickchanges": "🔄",
    }
    emoji = field_emoji.get(field, "📊")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    parts = []
    for i, (nick, value) in enumerate(rows, start=1):
        medal = medals.get(i, f"\x0314{i}.\x03")
        parts.append(f"{medal} {B}{nick}{B_OFF} ({value:,})")

    bot.say(f"{emoji} {B}Top {field.capitalize()}{B_OFF} in {B}{chan}{B_OFF}{SEP}{SEP.join(parts)}")


@plugin.thread(True)
@plugin.command("chanstats")
def cmd_chanstats(bot, trigger):
    """$chanstats [#channel] — Total stats for the entire channel."""
    chan = (trigger.group(2) or str(trigger.sender)).strip().lower()

    if not chan.startswith("#"):
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Use this in a channel or specify one.")
        return

    conn = _get_db(bot)
    try:
        row = conn.execute(
            """SELECT COUNT(DISTINCT nick),
                      COALESCE(SUM(lines), 0),
                      COALESCE(SUM(words), 0),
                      COALESCE(SUM(actions), 0),
                      COALESCE(SUM(kicks), 0),
                      COALESCE(SUM(bans), 0),
                      COALESCE(SUM(joins), 0),
                      COALESCE(SUM(parts), 0),
                      COALESCE(SUM(splits), 0),
                      COALESCE(SUM(quits), 0),
                      COALESCE(SUM(nickchanges), 0)
               FROM stats WHERE channel=?""",
            (chan,),
        ).fetchone()
    finally:
        conn.close()

    if not row or row[0] == 0:
        bot.say(f"\x0304⚠{COLOR_RESET} No stats for {B}{chan}{B_OFF}.")
        return

    users, lines, words, actions, kicks, bans, joins, parts, splits, quits, nicks = row

    bot.say(
        f"📊 {B}Channel Stats{B_OFF} — {B}{chan}{B_OFF}{SEP}"
        f"👥 Users: {B}{users:,}{B_OFF}{SEP}"
        f"💬 Lines: {B}{lines:,}{B_OFF}{SEP}"
        f"📝 Words: {B}{words:,}{B_OFF}{SEP}"
        f"🎭 Actions: {B}{actions:,}{B_OFF}"
    )
    extras = []
    if kicks:
        extras.append(f"🦵 Kicks: {B}{kicks:,}{B_OFF}")
    if bans:
        extras.append(f"🔨 Bans: {B}{bans:,}{B_OFF}")
    extras.append(f"🚪 Joins: {B}{joins:,}{B_OFF}")
    extras.append(f"👋 Parts: {B}{parts:,}{B_OFF}")
    if splits:
        extras.append(f"💥 Splits: {B}{splits:,}{B_OFF}")
    if quits:
        extras.append(f"🚫 Quits: {B}{quits:,}{B_OFF}")
    if nicks:
        extras.append(f"🔄 Nicks: {B}{nicks:,}{B_OFF}")
    bot.say(SEP.join(extras))


@plugin.thread(True)
@plugin.command("chanrank")
def cmd_chanrank(bot, trigger):
    """$chanrank — Top 10 channels by activity (total lines)."""
    conn = _get_db(bot)
    try:
        rows = conn.execute(
            """SELECT channel,
                      COUNT(DISTINCT nick) AS users,
                      COALESCE(SUM(lines), 0) AS total_lines,
                      COALESCE(SUM(words), 0) AS total_words
               FROM stats
               GROUP BY channel
               HAVING total_lines > 0
               ORDER BY total_lines DESC
               LIMIT 10""",
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        bot.say(f"\x0304⚠{COLOR_RESET} No channel stats recorded yet.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    parts = []
    for i, (chan, users, total_lines, total_words) in enumerate(rows, start=1):
        medal = medals.get(i, f"\x0314{i}.\x03")
        parts.append(
            f"{medal} {B}{chan}{B_OFF} — "
            f"💬 {B}{total_lines:,}{B_OFF} lines, "
            f"👥 {B}{users:,}{B_OFF} users"
        )

    bot.say(f"🏆 {B}Top Channels by Activity{B_OFF}")
    # Send in batches to avoid flooding — up to 5 per message
    for start in range(0, len(parts), 5):
        bot.say(SEP.join(parts[start:start + 5]))


@plugin.thread(True)
@plugin.command("zapstats")
@plugin.require_owner("Only the owner can zap stats")
def cmd_zap(bot, trigger):
    """$zapstats [#channel] — Wipe all stats for a channel. Owner only."""
    chan = (trigger.group(2) or str(trigger.sender)).strip().lower()

    if not chan.startswith("#"):
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Specify a channel.")
        return

    conn = _get_db(bot)
    try:
        cur = conn.execute("DELETE FROM stats WHERE channel=?", (chan,))
        deleted = cur.rowcount
        conn.commit()
    except Exception:
        LOGGER.exception("chanstats: zapstats error")
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Failed to zap stats.")
        return
    finally:
        conn.close()

    bot.say(
        f"🗑️ {B}Stats Reset{B_OFF}{SEP}"
        f"{B}{chan}{B_OFF} wiped by {B}{trigger.nick}{B_OFF}{SEP}"
        f"{B}{deleted:,}{B_OFF} records removed"
    )


@plugin.thread(True)
@plugin.command("zapnick")
@plugin.require_privilege(plugin.OP, "You need to be at least an op to use this.")
def cmd_zapnick(bot, trigger):
    """$zapnick <nick> [#channel] — Remove a single nick's stats. Op+ only."""
    text = (trigger.group(2) or "").strip().split()
    nick = None
    chan = str(trigger.sender).lower()

    for arg in text:
        if arg.startswith("#"):
            chan = arg.lower()
        elif nick is None:
            nick = arg.lower()

    if not nick:
        bot.say(f"\x0304⚠ Usage:{COLOR_RESET} {B}!zapnick{B_OFF} <nick> [#channel]")
        return
    if not chan.startswith("#"):
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Specify a channel.")
        return

    conn = _get_db(bot)
    try:
        cur = conn.execute("DELETE FROM stats WHERE channel=? AND nick=?", (chan, nick))
        deleted = cur.rowcount
        conn.commit()
    except Exception:
        LOGGER.exception("chanstats: zapnick error")
        bot.say(f"\x0304⚠ Error:{COLOR_RESET} Failed to remove stats.")
        return
    finally:
        conn.close()

    if deleted:
        bot.say(
            f"🗑️ {B}Stats Removed{B_OFF}{SEP}"
            f"{B}{nick}{B_OFF} cleared from {B}{chan}{B_OFF} by {B}{trigger.nick}{B_OFF}"
        )
    else:
        bot.say(f"\x0304⚠{COLOR_RESET} No stats found for {B}{nick}{B_OFF} in {B}{chan}{B_OFF}.")


@plugin.command("statshelp")
def cmd_statshelp(bot, trigger):
    """$statshelp — PM the user a list of all stats commands."""
    nick = trigger.nick

    bot.notice(f"📊 {B}Channel Stats Commands{B_OFF}", nick)
    bot.notice(f" ", nick)
    bot.notice(
        f"  {B}!stats{B_OFF} [nick] [#channel]  —  "
        f"Show stats for a user (defaults to you in the current channel)",
        nick,
    )
    bot.notice(
        f"  {B}!rank{B_OFF} [field] [#channel]  —  "
        f"Top 10 users for a stat field (default: lines)",
        nick,
    )
    bot.notice(
        f"  {B}!chanstats{B_OFF} [#channel]  —  "
        f"Total aggregate stats for the entire channel",
        nick,
    )
    bot.notice(
        f"  {B}!chanrank{B_OFF}  —  "
        f"Top 10 channels ranked by total lines",
        nick,
    )
    bot.notice(
        f"  {B}!zapstats{B_OFF} [#channel]  —  "
        f"Wipe all stats for a channel (owner only)",
        nick,
    )
    bot.notice(
        f"  {B}!zapnick{B_OFF} <nick> [#channel]  —  "
        f"Remove a single nick's stats (op+ only)",
        nick,
    )
    bot.notice(f" ", nick)
    bot.notice(
        f"📝 {B}Valid rank fields:{B_OFF} lines, words, actions, kicks, bans, "
        f"joins, parts, splits, quits, nickchanges",
        nick,
    )

    bot.say(f"📬 {B}{nick}{B_OFF}, check your notices for the stats command list!")


# ====================== INTERVAL SAVE ======================

@plugin.thread(True)
@plugin.interval(SAVE_EVERY_MINUTES * 60)
def autosave(bot):
    _prune_idle(bot, "schedule")


def shutdown(bot):
    """Final prune on clean shutdown."""
    _prune_idle(bot, "shutdown")
    LOGGER.info("chanstats: shutdown complete")