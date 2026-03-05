"""facepalm.py -- small Sopel plugin

When someone does "/me facepalms" (ACTION), the bot replies with a
random facepalm action. The plugin uses a per-channel cooldown to
avoid spamming the channel.

This is intentionally tiny and side-effect free.
"""
from __future__ import annotations

import time
import random
import threading
from sopel import module
import re

# How many seconds to wait between reactions per channel
COOLDOWN_SECONDS = 15

# Simple in-memory last-seen timestamps (keyed by channel)
_channel_last: dict[str, float] = {}
_lock = threading.Lock()

# Pool of facepalm responses - one is chosen at random each time
FACEPALM_RESPONSES = [
    "facepalms so hard the desk breaks (－‸ლ)",
    "buries face into hands (ಠ_ಠ) 🤦",
    "facepalms with both hands 🤦‍♂️🤦‍♀️",
    "facepalms and sighs deeply (ノ°Д°）ノ︵ ┻━┻",
    "drags hand down face slowly... 😩 ugh.",
    "facepalms so hard it echoes (－‸ლ) 💥",
    "covers face with a pillow and screams internally 😫🛏️",
    "slaps forehead and questions all life choices 🤦 ( ._. )",
    "facepalms violently (╯°□°）╯︵ ┻━┻  ... then flips it back ┬─┬ ノ( ゜-゜ノ)",
    "facepalms so hard a new crater forms on the moon 🌕💢",
    "is absolutely done. (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ ... jk, done. 🤦",
    "slowly places palm to face 😤 ( -_-) ...",
    "facepalms with the force of a thousand suns ☀️ (－‸ლ) ☀️",
    "collapses dramatically 🤦 ...and stays there",
    "facepalms and mutters something about reading comprehension 📖 (－‸ლ)",
]

# Precompile pattern for Sopel.rule compatibility across versions
FACEPALM_PATTERN = re.compile(r"^(?:facepalm|facepalms|facepalmed)\b", re.IGNORECASE)


@module.rule(FACEPALM_PATTERN)
@module.intent("ACTION")
@module.example('/me facepalms', 'Bot replies with a random facepalm action (once per cooldown)')
def react_facepalm(bot, trigger):
    """React to action messages that start with facepalm/facepalms/facepalmed.

    The handler responds with a single action containing a random facepalm.
    Responses are throttled per-channel to avoid spam.
    """
    # Only react in channels (not in PMs)
    try:
        sender = trigger.sender or ''
    except Exception:
        sender = ''

    if not sender.startswith('#'):
        return

    now = time.time()
    with _lock:
        last = _channel_last.get(sender, 0)
        if now - last < COOLDOWN_SECONDS:
            return
        _channel_last[sender] = now

    response = random.choice(FACEPALM_RESPONSES)
    bot.say(f"{trigger.nick} {response}")
