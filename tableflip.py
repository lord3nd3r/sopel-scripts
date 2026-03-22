from sopel import module

import time
import threading
from collections import defaultdict

MESSAGES = [
    "╭∩╮( º.º )╭∩╮",
    "┬─┬ノ( º _ ºノ)",
    "o(*≧▽≦)ツ┏━┓",
    "(╯°□°）╯︵ ┻━┻"
]


# Cooldown dictionary: {(channel, user): last_time}
cooldowns = defaultdict(float)
COOLDOWN_SECONDS = 60

def send_sequence(bot, trigger):
    for msg in MESSAGES:
        bot.say(msg, trigger.sender)
        time.sleep(2)

@module.commands('flip')
def tableflip(bot, trigger):
    channel = trigger.sender
    user = trigger.nick
    key = (channel, user)
    now = time.time()
    elapsed = now - cooldowns[key]
    if elapsed < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - elapsed)
        notice_msg = f"(｡•́︿•̀｡) Whoa! Please wait {remaining}s before flipping again! ⏳✨"
        bot.notice(notice_msg, user)
        return
    cooldowns[key] = now
    threading.Thread(target=send_sequence, args=(bot, trigger)).start()