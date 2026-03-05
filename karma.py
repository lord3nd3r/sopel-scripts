# -*- coding: utf-8 -*-
"""
karma.py - Karma module for Sopel 7/8+
10-minute cooldown per user *per channel* + per-channel & global leaderboards
Now with extra ✨fun✨.
"""

from sopel import module, tools
from sqlalchemy.sql import text
import re
import time

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
KARMA_COOLDOWN = 600  # 10 minutes
SELF_KARMA_MESSAGE = "Nice try 😏 but you can't karma yourself."
PRIVATE_KARMA_MESSAGE = "Karma changes belong in public channels. 🗣️"
COOLDOWN_NOTICE = (
    "⏳ Easy there! You can give karma again in {time}. "
    "(Cooldown is per channel.)"
)

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def get_karma(db, target):
    """Global karma helper."""
    target_id = tools.Identifier(target)
    karma = db.get_nick_value(target_id, 'karma')
    return int(str(karma).replace('"', '')) if karma is not None else 0


def set_karma(db, target, value):
    db.set_nick_value(tools.Identifier(target), 'karma', str(int(value)))


def add_channel_karma(db, target, channel, delta):
    """Per-channel karma helper."""
    target_id = tools.Identifier(target)
    chan_key = f'karma_channel_{tools.Identifier(channel)}'
    current = db.get_nick_value(target_id, chan_key) or '0'
    db.set_nick_value(
        target_id,
        chan_key,
        str(int(str(current).replace('"', '')) + int(delta)),
    )


def get_channel_karma(db, target, channel):
    """Get per-channel karma (int), stripping old quoted values."""
    target_id = tools.Identifier(target)
    chan_key = f'karma_channel_{tools.Identifier(channel)}'
    raw = db.get_nick_value(target_id, chan_key)
    if raw is None:
        return 0
    try:
        return int(str(raw).replace('"', ''))
    except ValueError:
        return 0


def format_time_remaining(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} sec"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes} min {secs} sec" if secs else f"{minutes} min"


def get_cooldowns(bot):
    """Return cooldown dict keyed as (giver_identifier, channel_identifier)."""
    if 'karma_cooldown' not in bot.memory:
        bot.memory['karma_cooldown'] = {}
    return bot.memory['karma_cooldown']


# Cleanup old cooldown entries
def cleanup_cooldowns(bot):
    cooldowns = bot.memory.get('karma_cooldown')
    if not cooldowns:
        return
    now = time.time()
    expired = [k for k, t in cooldowns.items()
               if now - t > KARMA_COOLDOWN + 3600]
    for k in expired:
        del cooldowns[k]


@module.interval(7200)
def cooldown_cleanup(bot):
    cleanup_cooldowns(bot)


# ──────────────────────────────────────────────────────────────
# ++ / -- handler
# ──────────────────────────────────────────────────────────────
@module.rule(r'^\s*[^^\s\+\-][^\s]*?(?:\+\+|--)\s*$')
def karma_increment_decrement(bot, trigger):
    if trigger.is_privmsg:
        return bot.reply(PRIVATE_KARMA_MESSAGE)

    # Ignore messages from the bot itself to avoid self-triggering
    try:
        if trigger.nick and str(trigger.nick).lower() == str(bot.nick).lower():
            return
    except Exception:
        pass

    # Find all karma patterns in the message (capture nick + sign pair)
    # We'll strip surrounding punctuation from the captured nick below.
    matches = re.findall(r'^\s*([^\s\+\-][^\s]*?)(\+\+|--)\s*$', trigger.group(0))
    if not matches:
        return

    giver_id = tools.Identifier(trigger.nick)
    chan_id = tools.Identifier(trigger.sender)

    # Check cooldown
    cooldown_key = (giver_id, chan_id)
    cooldowns = get_cooldowns(bot)
    now = time.time()
    last = cooldowns.get(cooldown_key, 0)
    remaining = KARMA_COOLDOWN - (now - last)
    if remaining > 0:
        bot.say(
            COOLDOWN_NOTICE.format(time=format_time_remaining(remaining)),
            trigger.nick,
        )
        return

    processed_targets = set()
    for target, sign in matches:
        # Strip common surrounding punctuation from target
        target = target.strip('()[]{}<>"\',:;.!?')
        target_id = tools.Identifier(target)

        # Skip if already processed this target in the message
        if target_id in processed_targets:
            continue
        processed_targets.add(target_id)

        # Self-karma block
        if target_id == giver_id:
            continue  # Maybe don't reply for each, just skip

        try:
            if bot.db.get_nick_id(target_id) == bot.db.get_nick_id(giver_id):
                continue
        except ValueError:
            pass

        # Apply karma (sign is '++' or '--' from the new regex)
        delta = 1 if sign == '++' else -1
        new_global = get_karma(bot.db, target) + delta
        set_karma(bot.db, target, new_global)

        # Friendly message bits
        if delta > 0:
            action_verb = "gained"
            mood = "✨"
            lead = "🆙 Karma boost!"
        else:
            action_verb = "lost"
            mood = "😬"
            lead = "⬇ Karma drop..."

        # Apply CHANNEL karma and respond
        if trigger.sender.startswith('#'):
            add_channel_karma(bot.db, target, trigger.sender, delta)
            chan_karma = get_channel_karma(bot.db, target, trigger.sender)
            bot.say(
                f"{lead} {target} {action_verb} {abs(delta)} karma {mood} "
                f"(🎯 {chan_karma} in {trigger.sender} | 🌐 {new_global} global)"
            )
        else:
            bot.say(
                f"{lead} {target} {action_verb} {abs(delta)} karma {mood} "
                f"(🌐 {new_global} global)"
            )

    # Update cooldown timer after processing
    cooldowns[cooldown_key] = now


# ──────────────────────────────────────────────────────────────
# Inline == (foo ==)
# ──────────────────────────────────────────────────────────────
@module.rule(r'^\S+\s*==\s*$')
def karma_show_inline(bot, trigger):
    target = trigger.group(0).split('==', 1)[0].strip()
    karma = get_karma(bot.db, target)
    bot.say(f"📊 {target} == {karma} karma globally")


# ──────────────────────────────────────────────────────────────
# .karma — stats or command list (PM)
# ──────────────────────────────────────────────────────────────
@module.commands('karma')
def cmd_karma(bot, trigger):
    """
    .karma <nick> → show channel + global karma
    .karma        → PM full command list + cooldown info (multi-line)
    """
    args = (trigger.group(3) or "").strip()

    # No arguments → send help via multi-line PM
    if not args:
        lines = [
            "🤖 Karma Help:",
            "• nick++ / nick-- — Give or remove karma (10-minute per-channel cooldown)",
            "• .karma [nick] — Show channel karma + global karma",
            "• .channeltop / .ctop — Top karma holders in this channel",
            "• .channelbottom / .cbottom — Lowest karma in this channel",
            "• .karmatop / .ktop — Global top karma",
            "• .karmabottom / .kbottom — Global lowest karma",
            "• .setkarma <nick> <value> — OP-only",
            "",
            "⏳ Cooldown: You may give karma once every 10 minutes *per channel*.",
        ]

        for line in lines:
            bot.say(line, trigger.nick)
        return

    # Display karma stats
    target = args.split()[0]
    global_karma = get_karma(bot.db, target)

    if trigger.sender.startswith('#'):
        channel = trigger.sender
        channel_karma = get_channel_karma(bot.db, target, channel)
        bot.say(
            f"📊 {target}: 🎯 {channel_karma} in {channel} | "
            f"🌐 {global_karma} global"
        )
    else:
        bot.say(f"📊 {target} has 🌐 {global_karma} karma globally.")


# ──────────────────────────────────────────────────────────────
# Global leaderboards
# ──────────────────────────────────────────────────────────────
def _global_leaderboard(bot, trigger, descending=True, default_limit=5):
    arg = trigger.group(2)
    limit = default_limit
    if arg and arg.isdigit():
        limit = max(1, min(50, int(arg)))
    order = "DESC" if descending else "ASC"

    query = text(f"""
        SELECT COALESCE(nicknames.canonical, nicknames.slug) AS nick,
               CAST(REPLACE(nick_values.value, '"', '') AS INTEGER) AS karma
        FROM nick_values
        JOIN nicknames ON nick_values.nick_id = nicknames.nick_id
        WHERE nick_values.key = 'karma'
        ORDER BY karma {order}
        LIMIT :limit
    """)

    with bot.db.engine.connect() as conn:
        results = conn.execute(query, {"limit": limit}).fetchall()

    if not results:
        return bot.say("🏆 No karma recorded yet.")

    line = " | ".join(f"{nick} == {karma}" for nick, karma in results)
    bot.say(f"🏆 Global karma leaderboard: {line}")


@module.commands('karmatop', 'ktop')
def karmatop(bot, trigger):
    _global_leaderboard(bot, trigger, True, 5)


@module.commands('karmabottom', 'kbottom')
def karmabottom(bot, trigger):
    _global_leaderboard(bot, trigger, False, 5)


# ──────────────────────────────────────────────────────────────
# Channel leaderboards
# ──────────────────────────────────────────────────────────────
def _channel_leaderboard(bot, trigger, descending=True, default_limit=10):
    if not trigger.sender.startswith('#'):
        return bot.say("Channel leaderboards only work in channels. 📺")

    arg = trigger.group(2)
    limit = default_limit
    if arg and arg.isdigit():
        limit = max(1, min(50, int(arg)))
    order = "DESC" if descending else "ASC"

    chan_key = f'karma_channel_{tools.Identifier(trigger.sender)}'

    query = text(f"""
        SELECT COALESCE(nicknames.canonical, nicknames.slug) AS nick,
               CAST(REPLACE(nick_values.value, '"', '') AS INTEGER) AS karma
        FROM nick_values
        JOIN nicknames ON nick_values.nick_id = nicknames.nick_id
        WHERE nick_values.key = :chan_key
        ORDER BY karma {order}
        LIMIT :limit
    """)

    with bot.db.engine.connect() as conn:
        results = conn.execute(
            query,
            {"chan_key": chan_key, "limit": limit},
        ).fetchall()

    if not results:
        return bot.say(f"🏆 No karma recorded in {trigger.sender} yet.")

    line = " | ".join(f"{nick} == {karma}" for nick, karma in results)
    bot.say(f"🏆 Karma in {trigger.sender}: {line}")


@module.commands('channeltop', 'ctop')
def channel_top(bot, trigger):
    _channel_leaderboard(bot, trigger, True, 10)


@module.commands('channelbottom', 'cbottom')
def channel_bottom(bot, trigger):
    _channel_leaderboard(bot, trigger, False, 10)


# ──────────────────────────────────────────────────────────────
# .setkarma (OP only)
# ──────────────────────────────────────────────────────────────
@module.commands('setkarma')
@module.require_privilege(module.OP)
@module.require_chanmsg("Setting karma works only in channels.")
def setkarma(bot, trigger):
    text_arg = trigger.group(2)
    if not text_arg:
        return bot.reply("Usage: .setkarma <nick> <value>")

    parts = text_arg.strip().split(None, 2)
    if len(parts) != 2:
        return bot.reply("Usage: .setkarma <nick> <integer>")

    target, value_str = parts
    try:
        value = int(value_str)
    except ValueError:
        return bot.reply("Karma value must be an integer. 🔢")

    set_karma(bot.db, target, value)
    bot.say(f"🛠️ {target}'s karma has been set to {value}.")

