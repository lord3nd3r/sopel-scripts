# markov.py — Markov chain bot plugin for Sopel
# Originally by ComputerTech, updated by End3r
# Learns from channel chat and generates random sentences from word trigrams.
import random
import re
import threading

import requests
from sqlalchemy import text
from sopel import plugin

URL_REGEX = re.compile(r"https?://\S+")
MAX_OUTPUT_LEN = 440  # stay within IRC message limits

NO_MARKOV = "Markov chains are not enabled in this channel."

_load_thread = None
_engine = None


def setup(bot):
    global _engine
    _engine = bot.db.engine
    with _engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS markov (
                channel     TEXT    NOT NULL,
                first_word  TEXT,
                second_word TEXT,
                third_word  TEXT,
                frequency   INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (channel, first_word, second_word, third_word)
            )
            """
        ))


@plugin.command("markovon")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to use this command.")
def cmd_markovon(bot, trigger):
    """$markovon [chance] — Enable markov in this channel. Optional chance 0-100 for auto-trigger."""
    channel = str(trigger.sender)
    bot.db.set_channel_value(channel, "markov", True)
    arg = (trigger.group(2) or "").strip()
    if arg.isdigit():
        chance = max(0, min(100, int(arg)))
        bot.db.set_channel_value(channel, "markov-chance", chance)
        bot.reply("Markov enabled (auto-trigger: %d%%)." % chance)
    else:
        bot.reply("Markov enabled. Use $markovchance <0-100> to set auto-trigger rate.")


@plugin.command("markovoff")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to use this command.")
def cmd_markovoff(bot, trigger):
    """$markovoff — Disable markov in this channel."""
    channel = str(trigger.sender)
    bot.db.set_channel_value(channel, "markov", False)
    bot.db.set_channel_value(channel, "markov-chance", 0)
    bot.reply("Markov disabled.")


@plugin.command("markovchance")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to use this command.")
def cmd_markovchance(bot, trigger):
    """$markovchance <0-100> — Set auto-trigger percentage."""
    channel = str(trigger.sender)
    if not bot.db.get_channel_value(channel, "markov"):
        return bot.reply(NO_MARKOV)
    arg = (trigger.group(2) or "").strip()
    if not arg.isdigit():
        return bot.reply("Usage: $markovchance <0-100>")
    chance = max(0, min(100, int(arg)))
    bot.db.set_channel_value(channel, "markov-chance", chance)
    bot.reply("Auto-trigger chance set to %d%%." % chance)


@plugin.rule(r".+")
def on_channel_message(bot, trigger):
    if trigger.is_privmsg:
        return

    channel = str(trigger.sender)
    markov_chance = int(bot.db.get_channel_value(channel, "markov-chance") or 0)

    if markov_chance > 0 and random.randint(0, 99) < markov_chance:
        words = trigger.group(0).split()
        random.shuffle(words)
        for word in words:
            out = _generate(bot, channel, [word])
            if out:
                bot.say(out)
                break

    if bot.db.get_channel_value(channel, "markov"):
        _create(bot, channel, trigger.group(0))


@plugin.command("markov")
@plugin.require_chanmsg("This command only works in channels.")
def cmd_markov(bot, trigger):
    channel = str(trigger.sender)
    if not bot.db.get_channel_value(channel, "markov"):
        return bot.reply(NO_MARKOV)

    first_words = trigger.group(2).split() if trigger.group(2) else []
    out = _generate(bot, channel, first_words)
    if out is not None:
        bot.say(out)
    else:
        bot.reply("Failed to generate a Markov chain.")


@plugin.command("markovfor")
def cmd_markovfor(bot, trigger):
    if not trigger.group(2):
        return bot.reply("Usage: !markovfor <#channel> [seed-word]")

    parts = trigger.group(2).split()
    target_name = parts[0]
    first_words = parts[1:]

    if target_name not in bot.channels:
        return bot.reply("Unknown channel.")

    channel = bot.channels[target_name]
    channel_name = str(channel.name)

    if trigger.is_privmsg and trigger.nick not in channel.users:
        return bot.reply(
            "You must be in %s to run this from a private message." % channel_name
        )

    if not bot.db.get_channel_value(channel_name, "markov"):
        return bot.reply(NO_MARKOV)

    out = _generate(bot, channel_name, first_words)
    if out is not None:
        bot.say(out)
    else:
        bot.reply("Failed to generate a Markov chain.")


@plugin.command("clearmarkov")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OWNER, "You must be the channel owner to use this command.")
def cmd_clearmarkov(bot, trigger):
    channel = str(trigger.sender)

    with _engine.begin() as conn:
        conn.execute(
            text("DELETE FROM markov WHERE channel = :channel"),
            {"channel": channel},
        )

    bot.reply("Cleared the Markov chain for %s." % channel)


@plugin.command("markovlog")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to load logs.")
def cmd_markovlog(bot, trigger):
    global _load_thread

    channel = str(trigger.sender)
    if not bot.db.get_channel_value(channel, "markov"):
        return bot.reply(NO_MARKOV)

    if _load_thread is not None and _load_thread.is_alive():
        return bot.reply("A log import is already in progress.")

    url = (trigger.group(2) or "").strip()
    if not url:
        return bot.reply("Usage: !markovlog <url>")

    # Only allow http/https URLs to prevent SSRF against local services
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return bot.reply("Only http/https URLs are allowed.")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        return bot.reply("Failed to fetch log: %s" % exc)

    bot.reply("Importing...")
    _load_thread = threading.Thread(
        target=_load_loop,
        args=(bot, channel, response.text),
        daemon=True,
    )
    _load_thread.start()


def _load_loop(bot, channel, data):
    global _load_thread
    for line in data.split("\n"):
        line = line.strip()
        if line:
            _create(bot, channel, line)
    _load_thread = None


def _create(bot, channel, line):
    if URL_REGEX.search(line):
        return

    words = [w.lower() for w in line.split() if w]
    if len(words) <= 2:
        return

    inserts = [
        (None, None, words[0]),
        (None, words[0], words[1]),
    ]
    for i in range(len(words) - 2):
        inserts.append(tuple(words[i : i + 3]))
    inserts.append((words[-2], words[-1], None))

    with _engine.begin() as conn:
        for first, second, third in inserts:
            conn.execute(
                text(
                    """
                    INSERT INTO markov
                        (channel, first_word, second_word, third_word, frequency)
                    VALUES (:channel, :first, :second, :third, 1)
                    ON CONFLICT (channel, first_word, second_word, third_word)
                    DO UPDATE SET frequency = frequency + 1
                    """
                ),
                {
                    "channel": channel,
                    "first": first,
                    "second": second,
                    "third": third,
                },
            )


def _choose(pairs):
    items, weights = zip(*pairs)
    return random.choices(items, weights=weights, k=1)[0]


def _generate(bot, channel, first_words):
    with _engine.connect() as conn:
        if not first_words:
            rows = conn.execute(
                text(
                    """
                    SELECT third_word, frequency FROM markov
                     WHERE channel     = :channel
                       AND first_word  IS NULL
                       AND second_word IS NULL
                       AND third_word  IS NOT NULL
                    """
                ),
                {"channel": channel},
            ).fetchall()
            if not rows:
                return None
            first_word = _choose(rows)

            rows = conn.execute(
                text(
                    """
                    SELECT third_word, frequency FROM markov
                     WHERE channel     = :channel
                       AND first_word  IS NULL
                       AND second_word = :second
                       AND third_word  IS NOT NULL
                    """
                ),
                {"channel": channel, "second": first_word},
            ).fetchall()
            if not rows:
                return None

            second_word = _choose(rows)
            words = [first_word, second_word]

        elif len(first_words) == 1:
            first_word = first_words[0].lower()
            rows = conn.execute(
                text(
                    """
                    SELECT second_word, third_word, frequency FROM markov
                     WHERE channel     = :channel
                       AND first_word  = :first
                       AND second_word IS NOT NULL
                       AND third_word  IS NOT NULL
                    """
                ),
                {"channel": channel, "first": first_word},
            ).fetchall()
            if not rows:
                return None

            second_word, third_word = _choose(
                [((s, t), f) for s, t, f in rows]
            )
            words = [first_word, second_word, third_word]

        else:
            words = [w.lower() for w in first_words]

        for _ in range(30):
            rows = conn.execute(
                text(
                    """
                    SELECT third_word, frequency FROM markov
                     WHERE channel     = :channel
                       AND first_word  = :first
                       AND second_word = :second
                    """
                ),
                {"channel": channel, "first": words[-2], "second": words[-1]},
            ).fetchall()
            if not rows:
                break

            next_word = _choose(rows)
            if next_word is None:
                break

            words.append(next_word)

            # Cap output length to stay within IRC limits
            if len(" ".join(words)) >= MAX_OUTPUT_LEN:
                break

    if words == first_words:
        return None

    out = " ".join(words)
    if len(out) > MAX_OUTPUT_LEN:
        out = out[:MAX_OUTPUT_LEN].rsplit(" ", 1)[0]
    return out
