# -*- coding: utf-8 -*-
"""
Ultimate Moo Plugin for Sopel – v3.8 – Legendary Edition
- Per-user-per-channel cooldowns
- sudo moo: once/hour per user per channel
- Global & per-channel stats and leaderboards
- moohelp PM-only with all commands + aliases listed
- /me moos increments moo count with no cooldown

✨ Prettier, emoji-rich output styled like karma.py. ✨

FIXES APPLIED (Sopel 8.0.4):
✅ Prevent `sudo moo` (and whitespace variants) from triggering generic moo detector (no double count/output)
✅ Legacy DB setup uses IF NOT EXISTS (reload-safe)
✅ Session upserts use `excluded` for better portability
✅ sudo moo uses shared increment logic (milestones still fire) without random moo output
✅ Added 8 more Linux/terminal moos to the `moos` list (total: 16 linux moos)
"""

from sopel import plugin
import random
import logging
import time
from sqlalchemy import text

logger = logging.getLogger(__name__)
# Bot nick (set at setup)
BOT_NICK_LOWER = None

# Default behavior values (can be overridden from the `moo` config section)
# Cooldowns (seconds)
MOO_COOLDOWN = 6         # moo cooldown
SUDO_COOLDOWN = 3600     # sudo moo cooldown (1 hour)

# Legendary moo chance (0.0 - 1.0)
LEGENDARY_CHANCE = 0.02

# sudo moo big loss chance (0.0 - 1.0)
# (Default is intentionally very low; -100 moos should be rare.)
SUDO_BIG_LOSS_CHANCE = 0.005

# Use monotonic clock for cooldowns
_time = time.monotonic

# Cooldown tracking: (channel, nick) → timestamp
LAST_MOO = {}
LAST_SUDO = {}


def _is_channel(name):
    """Return True if this looks like a real channel name."""
    return bool(name) and name.startswith(("#", "&", "+", "!"))


def _prune_cooldowns(store, max_age):
    """Lightly prune old cooldown entries to prevent unbounded growth."""
    now = _time()
    to_delete = [k for k, t in store.items() if now - t > max_age]
    for k in to_delete:
        del store[k]


# --------------------------------------------------------------
# Config reader
# --------------------------------------------------------------
def get_config(bot, option, default=None):
    parser = getattr(bot.config, "parser", None)
    if not parser or not parser.has_section("moo"):
        return default
    if not parser.has_option("moo", option):
        return default

    val = parser.get("moo", option).strip().lower()
    if val in ("true", "yes", "on", "1"):
        return True
    if val in ("false", "no", "off", "0"):
        return False
    try:
        return int(val)
    except ValueError:
        return parser.get("moo", option).strip()


# --------------------------------------------------------------
# Setup DB tables
# --------------------------------------------------------------
def setup(bot):
    global BOT_NICK_LOWER
    global MOO_COOLDOWN, SUDO_COOLDOWN, LEGENDARY_CHANCE, SUDO_BIG_LOSS_CHANCE
    BOT_NICK_LOWER = bot.nick.lower()

    parser = getattr(bot.config, "parser", None)
    if parser:
        if not parser.has_section("moo"):
            parser.add_section("moo")
        if not parser.has_option("moo", "leet_moo"):
            parser.set("moo", "leet_moo", "true")

    # Load configurable settings from the config parser (if present).
    try:
        # Use get_config which returns int/bool when possible
        MOO_COOLDOWN = int(get_config(bot, "moo_cooldown", MOO_COOLDOWN))
    except Exception:
        logger.exception("Invalid moo_cooldown in config; using default")
        MOO_COOLDOWN = MOO_COOLDOWN

    try:
        SUDO_COOLDOWN = int(get_config(bot, "sudo_cooldown", SUDO_COOLDOWN))
    except Exception:
        logger.exception("Invalid sudo_cooldown in config; using default")
        SUDO_COOLDOWN = SUDO_COOLDOWN

    try:
        LEGENDARY_CHANCE = float(get_config(bot, "legendary_chance", LEGENDARY_CHANCE))
    except Exception:
        logger.exception("Invalid legendary_chance in config; using default")
        LEGENDARY_CHANCE = LEGENDARY_CHANCE

    try:
        SUDO_BIG_LOSS_CHANCE = float(get_config(bot, "sudo_big_loss_chance", SUDO_BIG_LOSS_CHANCE))
    except Exception:
        logger.exception("Invalid sudo_big_loss_chance in config; using default")
        SUDO_BIG_LOSS_CHANCE = SUDO_BIG_LOSS_CHANCE

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                # Global counts per nick
                s.execute(text("""
                    CREATE TABLE IF NOT EXISTS moo_counts (
                        nick TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0
                    )
                """))

                # Per-channel counts per nick
                s.execute(text("""
                    CREATE TABLE IF NOT EXISTS moo_counts_chan (
                        nick TEXT,
                        channel TEXT,
                        count INTEGER DEFAULT 0,
                        PRIMARY KEY (nick, channel)
                    )
                """))

                s.commit()
        else:
            conn = bot.db.connect()
            # Global counts per nick
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moo_counts (
                    nick TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            # Per-channel counts per nick
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moo_counts_chan (
                    nick TEXT,
                    channel TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (nick, channel)
                )
            """)
            conn.commit()
            conn.close()
    except Exception:
        logger.exception("Moo setup error")


# --------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------
def db_helper(bot, nick, op="get", val=0):
    """Global moo counts (network-wide per nick)."""
    nick = nick.strip().lower()
    bot_nick = (BOT_NICK_LOWER or bot.nick.lower())

    # Never track stats for the bot itself; treat as 0
    if nick == bot_nick:
        return 0

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                if op == "get":
                    row = s.execute(
                        text("SELECT count FROM moo_counts WHERE nick = :n"),
                        {"n": nick}
                    ).fetchone()
                    return row[0] if row else 0

                # increment
                row = s.execute(
                    text("SELECT count FROM moo_counts WHERE nick = :n"),
                    {"n": nick}
                ).fetchone()
                new = (row[0] if row else 0) + val

                s.execute(
                    text("""
                        INSERT INTO moo_counts (nick, count)
                        VALUES (:n, :c)
                        ON CONFLICT(nick) DO UPDATE SET count = excluded.count
                    """),
                    {"n": nick, "c": new}
                )
                s.commit()
                return new

        # Legacy sqlite
        else:
            conn = bot.db.connect()
            cur = conn.cursor()

            if op == "get":
                cur.execute("SELECT count FROM moo_counts WHERE nick = ?", (nick,))
                row = cur.fetchone()
                conn.close()
                return row[0] if row else 0

            cur.execute("SELECT count FROM moo_counts WHERE nick = ?", (nick,))
            row = cur.fetchone()
            new = (row[0] if row else 0) + val
            cur.execute(
                "INSERT OR REPLACE INTO moo_counts (nick, count) VALUES (?, ?)",
                (nick, new)
            )
            conn.commit()
            conn.close()
            return new

    except Exception as e:
        logger.exception("DB error (global)")
        return -1


def db_helper_chan(bot, nick, channel, op="get", val=0):
    """Per-channel moo counts per nick."""
    nick = nick.strip().lower()
    channel = (channel or "").strip().lower()
    if not channel:
        return 0  # no channel context → treat as 0 for per-channel

    bot_nick = (BOT_NICK_LOWER or bot.nick.lower())
    # Never track stats for the bot itself; treat as 0
    if nick == bot_nick:
        return 0

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                if op == "get":
                    row = s.execute(
                        text(
                            "SELECT count FROM moo_counts_chan "
                            "WHERE nick = :n AND channel = :c"
                        ),
                        {"n": nick, "c": channel}
                    ).fetchone()
                    return row[0] if row else 0

                row = s.execute(
                    text(
                        "SELECT count FROM moo_counts_chan "
                        "WHERE nick = :n AND channel = :c"
                    ),
                    {"n": nick, "c": channel}
                ).fetchone()
                new = (row[0] if row else 0) + val

                s.execute(
                    text("""
                        INSERT INTO moo_counts_chan (nick, channel, count)
                        VALUES (:n, :c, :v)
                        ON CONFLICT(nick, channel) DO UPDATE SET count = excluded.count
                    """),
                    {"n": nick, "c": channel, "v": new}
                )
                s.commit()
                return new

        else:
            conn = bot.db.connect()
            cur = conn.cursor()

            if op == "get":
                cur.execute(
                    "SELECT count FROM moo_counts_chan WHERE nick = ? AND channel = ?",
                    (nick, channel)
                )
                row = cur.fetchone()
                conn.close()
                return row[0] if row else 0

            cur.execute(
                "SELECT count FROM moo_counts_chan WHERE nick = ? AND channel = ?",
                (nick, channel)
            )
            row = cur.fetchone()
            new = (row[0] if row else 0) + val
            cur.execute(
                "INSERT OR REPLACE INTO moo_counts_chan (nick, channel, count) "
                "VALUES (?, ?, ?)",
                (nick, channel, new)
            )
            conn.commit()
            conn.close()
            return new

    except Exception as e:
        logger.exception("DB error (channel)")
        return -1


# --------------------------------------------------------------
# Moo responses
# --------------------------------------------------------------
moos = [
    "Moo", "Moooooo", "MOOOOOO", "Moo?", "Moo Moo", "MOOOOO!",
    "mOoOoO", "Moooooooo!", "SuperMoo!", "Moo-calypse now!",
    "Schrödingcow", "sudo moo", "Moo on the rocks",
    "404: Moo not found", "Moo.exe has stopped responding",
    "Live, laugh, moo", "Moo-mentum conserved", "Moo++",
    "m0000000000000000", "MOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO",
    "Moo²", "Moo³", "Moo is love, moo is life",
    "Cowabunga!", "MooCoin to the mooooon", "MooBERT",
    "There is no cloud. It's just someone else's pasture.",
    "ELON JUST TWEETED A COW EMOJI",
    "Kernel panic: not enough moo", "Segmoo fault",
    "docker run moo", "systemctl restart cows",
    "More cowbell!", "Quantum cow",
    "The final moo is not the end",

    # linux nerd moos (original 16)
    "moo@localhost:~$",
    "sudo: moo: command not found",
    "Segmentation moo (core dumped)",
    "Permission denied: /dev/moo",
    "dmesg | grep moo",
    "systemd[1]: moo.service failed",
    "pkill -9 moo",
    "Welcome to Moo GNU/Linux",
    "bash: moo: No such file or pasture",
    "apt install moo",
    "pacman -S moo",
    "make moo && make install",
    "cron[1337]: (root) CMD (moo)",
    "ssh moo@pasture.local",
    "mount: /mnt/moo: bad supercow",
    "OOM killer: killed process moo",

    # 8 more linux nerd moos (added)
    "journalctl -u moo.service -n 50",
    "systemctl status moo.service",
    "tail -f /var/log/moo.log",
    "export MOOFLAGS='--verbose'",
    "chmod +x /usr/bin/moo",
    "ln -s /usr/bin/cowsay /usr/local/bin/moo",
    "grep -R \"moo\" /etc 2>/dev/null",
    "ps aux | awk '/moo/ {print $2}' | xargs kill",
]


legendary_moos = [
    "🌈 LEGENDARY MOO DROPS FROM THE SKY 🌈",
    "🔥 MOOCRITICAL HIT! 20x DAMAGE! 🔥",
    "✨ Shiny Golden Moo appears! ✨",
    "🌟 Cosmic Cow bellows across the universe: MOOOOOOOO 🌟",
    "💎 Diamond-encrusted Moo echoes through the pasture 💎",
    "⚡ THUNDERMOO STRIKES! The ground trembles... ⚡",
    "🧬 Genetic Supercow says: MOO+MOO = MOO² 🧬",
    "👑 KING OF COWS DECLARES: This is a LEGENDARY MOO 👑"
]

SUDO_BIG_WIN_MSGS = [
    "🐮 {nick}, the Supercow showers you in clover! +{amt} moos — the herd chants your name!",
    "🎉 {nick} hit the moo jackpot! +{amt} moos! The pasture throws a party.",
    "🍀 Lucky bovine day! {nick} gets +{amt} moos. Don't spend it all on hay.",
]

SUDO_BIG_LOSS_MSGS = [
    "😬 {nick}, the pasture protested and reclaimed {amt} moos. Oof.",
    "💩 Bad barn karma! {nick} lost {amt} moos — even the chickens are laughing.",
    "🕳️ {nick} dropped {amt} moos down a mysterious hole. We're sorry.",
]

MILESTONES = {
    1: "First moo! The herd welcomes you. 🐄",
    10: "Moo Adept achieved! ⭐",
    50: "Certified Mooologist 🎓",
    100: "Moo Master rank up! 🧙‍♂️🐄",
    500: "Legendary Cow status: UNLOCKED 💫",
    1000: "MOO GOD HAS AWAKENED ⚡",
    2000: "The cows are writing fanfics about you now 📚🐄",
    5000: "Global moo shortage declared 🚨",
    10000: "ELON JUST TWEETED: 'this guy moos too much' 🐂🚀"
}


def _handle_moo_increment(bot, nick, chan, legendary=None, say_response=True, inc_override=None):
    """
    Shared increment logic for moo triggers.

    legendary: if None, decide randomly; otherwise force True/False.
    say_response: if True, bot.say() a moo line.
    inc_override: if not None, force increment amount (e.g. sudo moo +10)
    """
    legendary = (random.random() < LEGENDARY_CHANCE) if legendary is None else legendary

    if say_response:
        msg = random.choice(legendary_moos if legendary else moos)
        bot.say(msg)

    if inc_override is not None:
        inc = inc_override
    else:
        inc = 20 if legendary else 1

    # Global count
    g_count = db_helper(bot, nick, "inc", inc)

    # Per-channel count (only if in a real channel)
    if _is_channel(chan):
        db_helper_chan(bot, nick, chan, "inc", inc)

    # Legendary message only for normal moo events (not sudo override)
    if legendary and g_count >= 0 and inc_override is None:
        bot.say(
            f"🌈 LEGENDARY MOO! {nick} gains +{inc} moos "
            f"(🌐 total: {g_count:,})"
        )

    # Only announce milestones on valid (non-error) counts
    if g_count > 0 and g_count in MILESTONES:
        bot.say(f"📈 Milestone unlocked for {nick} ({g_count:,} moos): {MILESTONES[g_count]}")


# --------------------------------------------------------------
# Moo detector (text) — EXCLUDES "sudo moo" (incl whitespace variants)
# --------------------------------------------------------------
@plugin.rule(r"(?i)^(?!\s*sudo\s+moo\s*$).*?\b(m[0o]+s?)\b")
def moo_response(bot, trigger):
    if not trigger.nick or trigger.nick.lower() == bot.nick.lower():
        return

    # CTCP ACTIONs (e.g. /me moos) are handled by moo_action().
    # Sopel can run @rule handlers for ACTION events too; avoid double-firing.
    if getattr(trigger, "event", "").upper() == "ACTION":
        return
    if getattr(trigger, "ctcp", None) == "ACTION":
        return
    try:
        if getattr(trigger, "args", None) and len(trigger.args) > 1:
            if isinstance(trigger.args[1], str) and trigger.args[1].startswith("\x01ACTION"):
                return
    except Exception:
        pass

    chan = (trigger.sender or "").lower()
    nick = trigger.nick
    key = (chan, nick.lower())

    now = _time()
    _prune_cooldowns(LAST_MOO, 3600)

    if now - LAST_MOO.get(key, 0) < MOO_COOLDOWN:
        return
    LAST_MOO[key] = now

    # Ignore zero-moo when leet_moo is OFF
    moo_token = (trigger.group(1) or "")
    if not get_config(bot, "leet_moo", True) and "0" in moo_token:
        return

    _handle_moo_increment(bot, nick, chan, legendary=None, say_response=True)


# --------------------------------------------------------------
# /me moos (ACTION) with NO cooldown
# --------------------------------------------------------------
# Match CTCP ACTIONs like: /me moos  OR  /me moos! (allow simple punctuation)
# Register common punctuation variants to avoid using unsupported decorators
@plugin.action_commands("moos", "moos!", "moos?", "moos.")
def moo_action(bot, trigger):
    """
    Handle /me moos (CTCP ACTION "moos") as a moo with no cooldown.
    """
    if not trigger.nick or trigger.nick.lower() == bot.nick.lower():
        return

    chan = (trigger.sender or "").lower()
    nick = trigger.nick

    # No cooldown check here – always counts
    _handle_moo_increment(bot, nick, chan, legendary=None, say_response=True)


# --------------------------------------------------------------
# sudo moo (1/hour per user per channel) — uses shared increment logic
# --------------------------------------------------------------
@plugin.rule(r"(?i)^\s*sudo\s+moo\s*$")
def sudo_moo(bot, trigger):
    if not trigger.nick or trigger.nick.lower() == bot.nick.lower():
        return

    chan = (trigger.sender or "").lower()
    nick = trigger.nick
    key = (chan, nick.lower())

    now = _time()
    _prune_cooldowns(LAST_SUDO, 86400)

    last = LAST_SUDO.get(key, 0)

    if now - last < SUDO_COOLDOWN:
        remaining = int(SUDO_COOLDOWN - (now - last))
        m = remaining // 60
        s = remaining % 60
        if m > 0:
            bot.say(f"⏳ sudo moo cooldown for {nick}: {m}m {s}s left.")
        else:
            bot.say(f"⏳ sudo moo cooldown for {nick}: {s}s left.")
        return

    LAST_SUDO[key] = now

    # Outcome probabilities (exclusive ranges):
    #  - 5% chance: big win (+30 moos)
    #  - next SUDO_BIG_LOSS_CHANCE: big loss (-100 moos)
    #  - otherwise: normal sudo reward (+10 moos)
    r = random.random()
    if r < 0.05:
        msg = random.choice(SUDO_BIG_WIN_MSGS).format(nick=nick, amt=30)
        bot.say(msg)
        _handle_moo_increment(bot, nick, chan, legendary=False, say_response=False, inc_override=30)
    elif r < 0.05 + max(0.0, min(1.0, SUDO_BIG_LOSS_CHANCE)):
        msg = random.choice(SUDO_BIG_LOSS_MSGS).format(nick=nick, amt=100)
        bot.say(msg)
        _handle_moo_increment(bot, nick, chan, legendary=False, say_response=False, inc_override=-100)
    else:
        bot.say("🐄⚡ Super Cow Powers activated! (+10 moos!)")
        _handle_moo_increment(bot, nick, chan, legendary=False, say_response=False, inc_override=10)


# --------------------------------------------------------------
# .moocount / .mymoo / .moos
# --------------------------------------------------------------
@plugin.commands("moocount", "mymoo")
def moocount(bot, trigger):
    arg = (trigger.group(2) or "").strip()
    target = arg or trigger.nick

    global_count = db_helper(bot, target, "get")

    chan = (trigger.sender or "").lower()
    is_channel = _is_channel(chan)
    if is_channel:
        chan_count = db_helper_chan(bot, target, chan, "get")
        bot.say(
            f"📊 {target}: 🐄 {chan_count:,} moo"
            f"{'' if chan_count == 1 else 's'} in {chan} | "
            f"🌐 {global_count:,} moo"
            f"{'' if global_count == 1 else 's'} total"
        )
    else:
        bot.say(
            f"📊 {target} has 🌐 {global_count:,} moo"
            f"{'' if global_count == 1 else 's'} total."
        )


# --------------------------------------------------------------
# .mootop / .topmoo (global leaderboard)
# --------------------------------------------------------------
@plugin.commands("mootop", "topmoo")
def mootop_global(bot, trigger):
    try:
        limit = int((trigger.group(2) or "10").split()[0])
    except Exception:
        limit = 10

    limit = max(1, min(50, limit))
    query_limit = limit + 1  # in case bot is in list

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                rows = s.execute(
                    text(
                        "SELECT nick, count FROM moo_counts "
                        "ORDER BY count DESC, nick LIMIT :l"
                    ),
                    {"l": query_limit}
                ).fetchall()
        else:
            conn = bot.db.connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT nick, count FROM moo_counts "
                "ORDER BY count DESC, nick LIMIT ?",
                (query_limit,)
            )
            rows = cur.fetchall()
            conn.close()

        botnick = BOT_NICK_LOWER or bot.nick.lower()
        entries = [(n, c) for (n, c) in rows if n.lower() != botnick]

        if not entries:
            bot.say("🏆 No moo legends yet.")
            return

        line = " | ".join(f"{n} == {c:,}" for (n, c) in entries[:limit])
        bot.say(f"🏆 Global Moo Legends: {line}")

    except Exception:
        logger.exception("Moo leaderboard error")
        bot.say("⚠️ Moo leaderboard error.")


# --------------------------------------------------------------
# .mootopchan / .chanmootop / .topmoochan (per-channel leaderboard)
# --------------------------------------------------------------
@plugin.commands("mootopchan", "chanmootop", "topmoochan")
def mootop_channel(bot, trigger):
    chan = (trigger.sender or "").lower()
    if not _is_channel(chan):
        bot.say("📺 Channel-only command. Try this inside a channel.")
        return

    try:
        limit = int((trigger.group(2) or "10").split()[0])
    except Exception:
        limit = 10

    limit = max(1, min(50, limit))
    query_limit = limit + 1

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                rows = s.execute(
                    text(
                        "SELECT nick, count FROM moo_counts_chan "
                        "WHERE channel = :c "
                        "ORDER BY count DESC, nick LIMIT :l"
                    ),
                    {"c": chan, "l": query_limit}
                ).fetchall()
        else:
            conn = bot.db.connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT nick, count FROM moo_counts_chan "
                "WHERE channel = ? "
                "ORDER BY count DESC, nick LIMIT ?",
                (chan, query_limit)
            )
            rows = cur.fetchall()
            conn.close()

        botnick = BOT_NICK_LOWER or bot.nick.lower()
        entries = [(n, c) for (n, c) in rows if n.lower() != botnick]

        if not entries:
            bot.say(f"🏆 No moo legends yet in {chan}.")
            return

        line = " | ".join(f"{n} == {c:,}" for (n, c) in entries[:limit])
        bot.say(f"🏆 Moo leaderboard in {chan}: {line}")

    except Exception:
        logger.exception("Channel moo leaderboard error")
        bot.say("⚠️ Channel moo leaderboard error.")


# --------------------------------------------------------------
# .totalmoo / .moostats
# --------------------------------------------------------------
@plugin.commands("totalmoo", "moostats")
def totalmoo(bot, trigger):
    """Global total & optionally this-channel total (for .moostats)."""
    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                total_global = s.execute(
                    text("SELECT SUM(count) FROM moo_counts")
                ).scalar() or 0
        else:
            conn = bot.db.connect()
            cur = conn.cursor()
            cur.execute("SELECT SUM(count) FROM moo_counts")
            row = cur.fetchone()
            total_global = (row[0] or 0) if row else 0
            conn.close()
    except Exception:
        logger.exception("Failed to calculate total moos")
        bot.say("⚠️ Failed to calculate total moos.")
        return

    cmd = trigger.group(1).lower() if trigger.group(1) else "totalmoo"

    chan = (trigger.sender or "").lower()
    is_channel = _is_channel(chan)

    if cmd == "moostats" and is_channel:
        try:
            if hasattr(bot.db, "session"):
                with bot.db.session() as s:
                    total_chan = s.execute(
                        text(
                            "SELECT SUM(count) FROM moo_counts_chan "
                            "WHERE channel = :c"
                        ),
                        {"c": chan}
                    ).scalar() or 0
            else:
                conn = bot.db.connect()
                cur = conn.cursor()
                cur.execute(
                    "SELECT SUM(count) FROM moo_counts_chan WHERE channel = ?",
                    (chan,)
                )
                row = cur.fetchone()
                total_chan = (row[0] or 0) if row else 0
                conn.close()

            bot.say(
                f"📊 Moo stats — 🌐 total: {total_global:,} | "
                f"📺 in {chan}: {total_chan:,}"
            )
        except Exception:
            bot.say(f"📊 Moo stats — 🌐 total: {total_global:,}")
    else:
        bot.say(f"📊 Total moos (🌐 network-wide): {total_global:,}.")


# --------------------------------------------------------------
# .mooreset (admin only)
# --------------------------------------------------------------
@plugin.commands("mooreset")
@plugin.require_admin()
def mooreset(bot, trigger):
    target = (trigger.group(2) or "").strip() or None

    try:
        if hasattr(bot.db, "session"):
            with bot.db.session() as s:
                if target:
                    low = target.lower()
                    s.execute(
                        text("DELETE FROM moo_counts WHERE nick = :n"),
                        {"n": low}
                    )
                    s.execute(
                        text("DELETE FROM moo_counts_chan WHERE nick = :n"),
                        {"n": low}
                    )
                else:
                    s.execute(text("DELETE FROM moo_counts"))
                    s.execute(text("DELETE FROM moo_counts_chan"))
                s.commit()
        else:
            conn = bot.db.connect()
            if target:
                low = target.lower()
                conn.execute(
                    "DELETE FROM moo_counts WHERE nick = ?",
                    (low,)
                )
                conn.execute(
                    "DELETE FROM moo_counts_chan WHERE nick = ?",
                    (low,)
                )
            else:
                conn.execute("DELETE FROM moo_counts")
                conn.execute("DELETE FROM moo_counts_chan")
            conn.commit()
            conn.close()

        if target:
            bot.say(f"🧹 Moo stats reset for {target}.")
        else:
            bot.say("🧹 All moo stats have been reset.")
    except Exception:
        logger.exception("Moo reset failed")
        bot.say("⚠️ Moo reset failed.")


# --------------------------------------------------------------
# moohelp / aboutmoo (PM-only)
# --------------------------------------------------------------
@plugin.commands("moohelp", "aboutmoo")
def moohelp(bot, trigger):
    """Send help ONLY to user privately (no channel spam)."""
    target = trigger.nick
    leet = "ON" if get_config(bot, "leet_moo", True) else "OFF"

    lines = [
        "🐄 Moo Plugin v3.8 – Legendary Edition",
        f"• Leet-moo: {leet}",
        "",
        "🔔 Automatic moo replies:",
        "   • moo / mooo / m000 → random moo (+1) or LEGENDARY (+20)",
        "",
        "🎭 /me moos (CTCP ACTION):",
        "   • Counts as a moo (+1 or LEGENDARY) with NO cooldown",
        "",
        "⏳ Cooldowns:",
        f"   • moo → {MOO_COOLDOWN}s per user per channel",
        f"   • sudo moo → {SUDO_COOLDOWN // 3600} hour per user per channel",
        "",
        "📊 Stats & Commands:",
        "   • .moocount /.mymoo [nick]",
        "       → Show moo count 🎯 in this channel + 🌐 total",
        "   • .mootop /.topmoo [N]",
        "       → 🏆 Top mooers (network-wide)",
        "   • .mootopchan /.chanmootop /.topmoochan [N]",
        "       → 🏆 Top mooers in this channel",
        "   • .totalmoo",
        "       → 📊 Total moos (network-wide)",
        "   • .moostats",
        "       → 📊 Total moos (network-wide + this channel)",
        "   • .mooreset [nick] (admin)",
        "       → 🧹 Reset moo stats (global + per-channel) for one user or everyone",
        "   • .moohelp /.aboutmoo",
        "       → This help message (PM only)",
        "",
        "💥 Extra:",
        "   • sudo moo → 🐄⚡ Super Cow Powers (+10 moos), once/hour per user per channel",
        "",
        "Tip: Start by mooing in any channel. The herd is listening. 🐄✨",
    ]

    for line in lines:
        bot.notice(line, target)



