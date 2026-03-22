import time
import random
import threading
import logging
from sopel import module, formatting

"""weed.py — Sopel command to share lighthearted "weed" messages.

Features:
- Commands: weed, bong, joint, keef, kief
- Channel-level and per-user-per-channel cooldowns (thread-safe)
- Non-blocking countdown via background thread
- Module-level constants for easy editing
"""

LOG = logging.getLogger(__name__)

# Cooldown in seconds (20 minutes = 1200 seconds)
COOLDOWN = 1200
# Per-user cooldown in seconds (30 seconds)
PER_USER_COOLDOWN = 30

# State (thread-safe access via LOCK)
LAST_USED = {}
PER_USER_LAST = {}
LOCK = threading.Lock()

# =======================
# WEED Content
# =======================
WEED_GIFTS = [
    "a hand-rolled joint 🌿",
    "a fat bong rip 🌊",
    "a tasty edible (brownie) 🍪",
    "a vape hit ☁️",
    "a classic blunt 🔥",
    "a dab (slab) ⚡",
    "a bowl packed and ready 🔥",
    "a CBD gummy 🍬",
    "a preroll cone 🌯",
    "a joint dusted in kief ✨",
    "a wax pen cartridge 🖊️",
    "a gravity bong hit 🌀",
    "a Thai stick 🎋",
    "a hash cookie 🍫",
    "a spliff (weed + tobacco) 🚬",
    "a cross joint ✖️",
    "a THC-infused drink 🥤",
    "a moon rock (nug dipped in oil & kief) 🌙",
    "a rosin press hit 💎",
    "a waterfall bong 💧",
    "some live resin 🍯",
    "a backwoods blunt 🍂",
    "a tulip joint 🌷",
    "a chillum pipe 🪈",
    "a one-hitter dugout 🎯",
    "a bubbler 🫧",
    "a tincture dropper 💧",
    "THC-infused honey 🍯",
    "a weed lollipop 🍭",
    "a cannagar (cannabis cigar) 🎩",
]

WEED_ACTION_MESSAGES = [
    "hands {target} {gift}",
    "passes {gift} to {target}",
    "slides {gift} across the table to {target}",
    "offers {target} {gift} — puff responsibly!",
    "tosses {gift} to {target} with a wink 😉",
]

WEED_FINAL_MESSAGES = [
    formatting.bold(formatting.color("Puff puff pass — light it up and keep it lit! 🌿🔥", formatting.colors.LIGHT_GREEN)),
    formatting.color("Roll a fat one, spark it, and pass the vibes 🙌🍁", formatting.colors.LIGHT_GREEN),
    formatting.color("Bong rip incoming — lean back and ride the clouds 🌊💨", formatting.colors.LIGHT_GREEN),
    formatting.color("Edible vibes: chill mode activated, munchies on standby 🍪🔥", formatting.colors.LIGHT_GREEN),
    formatting.color("Blunt sesh: slow hits, deep laughs, and loud tunes 🎶🌬️", formatting.colors.LIGHT_GREEN),
    formatting.color("Vape clouds: show off your fattest ring ☁️🏆", formatting.colors.LIGHT_GREEN),
    formatting.color("Dab night — small hit, big trip ⚡", formatting.colors.LIGHT_GREEN),
    formatting.color("Hotbox the room — windows up, vibes up 🚗💨", formatting.colors.LIGHT_GREEN),
    formatting.color("Kief it to the moon — sprinkle that goodness ✨", formatting.colors.LIGHT_GREEN),
    formatting.color("Keep it toasted and roasted — pass the flame 🔥🍞", formatting.colors.LIGHT_GREEN),
    formatting.color("Name your strain and flex it in chat — what's everyone smoking? 🌱👀", formatting.colors.LIGHT_GREEN),
    formatting.color("Snap a pic of your stash and share the glow-up 📸🌿", formatting.colors.LIGHT_GREEN),
    formatting.color("Munchies run! Pizza, tacos, cereal — vote now 🍕🌮🥣", formatting.colors.LIGHT_GREEN),
    formatting.color("Sesh soundtrack: drop a track and crank it up 🎵🔊", formatting.colors.LIGHT_GREEN),
    formatting.color("Cloud contest: who can make the biggest plume? 🌫️💨", formatting.colors.LIGHT_GREEN),
    formatting.color("Keep the sesh lit — only good vibes allowed ✌️🔥", formatting.colors.LIGHT_GREEN),
]

WEED_COUNTDOWN = [
    formatting.color("🌿 3... Get ready...", formatting.colors.GREEN),
    formatting.color("🔥 2... Spark it...", formatting.colors.YELLOW),
    formatting.color("💨 1... Inhale...", formatting.colors.RED),
]


# =======================
# BONG Content
# =======================
BONG_GIFTS = [
    "a freshly cleaned bong 🫧", "an ice-catch bong ❄️", "a gravity bong 🌀", 
    "a mini bubbler 🫧", "a percolator bong 💧", "a massive beaker bong 🧪", 
    "a gas mask bong 😷", "a straight tube bong 🌬️", "a silicone bong 🪀", 
    "a multi-chamber bong 🏙️"
]

BONG_ACTION_MESSAGES = [
    "passes {gift} to {target} 🫧",
    "rips {gift} and hands it to {target} 💨",
    "milks {gift} for {target} 🥛",
    "clears the chamber of {gift} and gives it to {target} 🧊",
    "packs {gift} for {target} 🌿"
]

BONG_FINAL_MESSAGES = [
    formatting.bold(formatting.color("Bong rip incoming — lean back and ride the clouds 🌊💨", formatting.colors.LIGHT_BLUE)),
    formatting.color("Clear that chamber! 🫧💨", formatting.colors.LIGHT_BLUE),
    formatting.color("Ice cold hits from the bong ❄️🧊", formatting.colors.CYAN),
    formatting.color("Don't drink the bong water! 🤢💧", formatting.colors.GREEN),
    formatting.color("That percolator is bubbling! 💧🫧", formatting.colors.LIGHT_BLUE),
]

BONG_COUNTDOWN = [
    formatting.color("🫧 3... Filling the water...", formatting.colors.LIGHT_BLUE),
    formatting.color("🧊 2... Adding ice...", formatting.colors.CYAN),
    formatting.color("🔥 1... Lighting the bowl...", formatting.colors.RED),
]


# =======================
# JOINT Content
# =======================
JOINT_GIFTS = [
    "a hand-rolled joint 🌿", "a cross joint ✖️", "a spliff 🚬", 
    "a fat cone 🍦", "a pinner joint 📍", "a kief-dusted joint ✨", 
    "a double-barrel joint ✌️", "a tulip joint 🌷", "a classic paper joint 📜", 
    "an infused joint 🍯", "a backwards-rolled joint 🔄"
]

JOINT_ACTION_MESSAGES = [
    "passes {gift} to {target} 🚬",
    "lights {gift} and hands it to {target} 🔥",
    "sparks up {gift} for {target} ✨",
    "rolls {gift} for {target} 📜",
    "tosses {gift} (lit) to {target} 🌿"
]

JOINT_FINAL_MESSAGES = [
    formatting.bold(formatting.color("Puff puff pass! 🌿🔥", formatting.colors.LIGHT_GREEN)),
    formatting.color("Don't bogart the joint! 🏃💨", formatting.colors.LIGHT_GREEN),
    formatting.color("Hotboxing with this joint 🚗💨", formatting.colors.LIGHT_GREEN),
    formatting.color("Spark it up and pass it around! 🔥🍁", formatting.colors.LIGHT_GREEN),
    formatting.color("A perfectly rolled joint. Enjoy! 📜🤌", formatting.colors.LIGHT_GREEN),
]

JOINT_COUNTDOWN = [
    formatting.color("📜 3... Grinding...", formatting.colors.GREEN),
    formatting.color("👅 2... Rolling...", formatting.colors.YELLOW),
    formatting.color("🔥 1... Sparking...", formatting.colors.RED),
]


# =======================
# KEEF Content
# =======================
KEEF_GIFTS = [
    "a bowl topped with keef ✨", "a keef puck 🥏", "a sprinkle of keef 🪄", 
    "a kief-coated moonrock 🌑", "a scoop of pure keef 🥄", "a keefy joint ☄️", 
    "a press of keef rosin 🍯", "a bowl full of pure keef 🥣"
]

KEEF_ACTION_MESSAGES = [
    "sprinkles {gift} for {target} ✨",
    "packs {gift} for {target} 🥣",
    "dusts {target}'s joint with {gift} 🪄",
    "shares {gift} with {target} 🏆",
    "presses {gift} for {target} 🥏"
]

KEEF_FINAL_MESSAGES = [
    formatting.bold(formatting.color("Keef it to the moon! ✨�", formatting.colors.YELLOW)),
    formatting.color("That keef hits different 🌌💫", formatting.colors.YELLOW),
    formatting.color("Golden dust vibes ✨🍯", formatting.colors.YELLOW),
    formatting.color("Sprinkle a little magic on it 🧚‍♀️🪄", formatting.colors.YELLOW),
    formatting.color("Careful with that keef, it's strong! ⚠️✨", formatting.colors.YELLOW),
]

KEEF_COUNTDOWN = [
    formatting.color("✨ 3... Collecting dust...", formatting.colors.YELLOW),
    formatting.color("🪄 2... Sprinkling...", formatting.colors.YELLOW),
    formatting.color("� 1... Melting...", formatting.colors.RED),
]


# =======================
# DMT Content
# =======================
DMT_GIFTS = [
    "a hit from a glass vapor genie 🌬️", "a breakthrough dose loaded in a pipe 🚀",
    "a DMT vape cart ☁️🌀", "a pharmahuasca capsule 💊", "a changa joint (DMT + MAOI herbs) 🌿🔥",
    "an ayahuasca brew 🍵🌀", "a crystal of pure freebase 💎", "a sandwich-method bowl 🪨",
    "an e-mesh loaded with 40mg ⚡", "a bufo toad secretion dose 🐸✨",
    "a DMT-infused honey stick 🍯🌀", "an enhanced leaf blend 🍂✨",
    "a sublingually-dosed tab 👅🌈", "a yopo seed pod 🌰👽",
]

DMT_ACTION_MESSAGES = [
    "loads {gift} for {target} — safe travels ✨🚀",
    "carefully hands {gift} to {target} — see you on the other side 🌀",
    "offers {gift} to {target} — hold on tight 👽",
    "presents {gift} to {target} — breathe deep 🌬️🌈",
    "places {gift} before {target} — the entities await 🔮",
]

DMT_FINAL_MESSAGES = [
    formatting.bold(formatting.color("B R E A K T H R O U G H — the chrysanthemum opens 🌸🌀👽", formatting.colors.PURPLE)),
    formatting.color("The machine elves are waving hello 🧙‍♂️👋✨ welcome to hyperspace", formatting.colors.PURPLE),
    formatting.color("Fractals within fractals within fractals 🌀🔯🌀 you are everything", formatting.colors.LIGHT_BLUE),
    formatting.color("The waiting room dissolves… geometric entities approach 🔶🔷🔶 do you have a question?", formatting.colors.PURPLE),
    formatting.color("Time has ceased to exist — you are the universe experiencing itself 🌌🧠✨", formatting.colors.LIGHT_BLUE),
    formatting.color("Jester entities juggle impossible shapes while singing in colors 🎪🎨🎶", formatting.colors.PURPLE),
    formatting.color("The cosmic serpent uncoils and shows you the DNA of reality 🐍🧬🌌", formatting.colors.TEAL),
    formatting.color("You have been yeeted through a kaleidoscope cannon into God's living room 💥🌀🛋️", formatting.colors.PURPLE),
]

DMT_COUNTDOWN = [
    formatting.color("🌬️  3... Inhale deeply...", formatting.colors.PURPLE),
    formatting.color("🌀  2... Hold it... hold it...", formatting.colors.LIGHT_BLUE),
    formatting.color("🚀  1... Let go...", formatting.colors.LIGHT_PURPLE),
]


# =======================
# SHROOMS Content
# =======================
SHROOMS_GIFTS = [
    "a handful of golden teachers 🍄✨", "a chocolate bar with 3.5g penis envy 🍫🍄",
    "a cup of shroom tea ☕🍄", "a dose of blue meanies 💙🍄",
    "a bag of liberty caps 🍂🍄", "a heroic dose of 5g dried 🦸🍄",
    "a microdose capsule (0.2g) 💊🌱", "some albino A+ caps 🦢🍄",
    "a jar of shroom honey 🍯🍄", "a lemon tek shot 🍋⚡",
    "some Amazonian cubensis 🌿🍄", "a psilocybin gummy bear 🐻🌈",
    "a fat stem of B+ 🍄🚀", "a truffle of psilocybe tampanensis 🪵✨",
]

SHROOMS_ACTION_MESSAGES = [
    "hands {target} {gift} — the mushroom speaks if you listen 🍄👂",
    "passes {gift} to {target} — nature's gift 🌿✨",
    "offers {gift} to {target} — enjoy the journey 🌈",
    "shares {gift} with {target} — mush love 🍄❤️",
    "drops {gift} into {target}'s hand — see the world breathe 🌍💫",
]

SHROOMS_FINAL_MESSAGES = [
    formatting.bold(formatting.color("The walls are breathing and the carpet is alive 🌊🍄🧘", formatting.colors.TEAL)),
    formatting.color("Trees are talking to each other and you can hear it 🌳🗣️🌳 shhhh listen", formatting.colors.GREEN),
    formatting.color("Everything is connected — you are the mycelial network 🍄🕸️🌍", formatting.colors.TEAL),
    formatting.color("The music has colors and the colors have feelings 🎨🎵😂😭", formatting.colors.GREEN),
    formatting.color("Time is a flat circle and you're sitting in the middle of it eating chips 🍕♾️😂", formatting.colors.TEAL),
    formatting.color("Your third eye is open and honestly it's a bit much 👁️🔮😅", formatting.colors.GREEN),
    formatting.color("You just had a 45-minute conversation with a tree. It was profound 🌲🧠💬", formatting.colors.TEAL),
    formatting.color("Ego? Never met her. You are stardust, friend ✨🌌🫠", formatting.colors.GREEN),
]

SHROOMS_COUNTDOWN = [
    formatting.color("🍄 3... Chewing...", formatting.colors.TEAL),
    formatting.color("🌊 2... The come-up begins...", formatting.colors.GREEN),
    formatting.color("🌈 1... Here it comes...", formatting.colors.LIGHT_GREEN),
]


# =======================
# ACID Content
# =======================
ACID_GIFTS = [
    "a tab of white-on-white 🧮✨", "a gel tab (300ug) 💎🌈",
    "a blotter with Grateful Dead art 💀⚡", "a sugar cube drop 🧂💧",
    "a liquid vial hit 🧪🌀", "a strip of dancing bears 🐻🎶",
    "a tab of bicycle day art 🚲🌈", "a double-dipped tab 👅👅",
    "a breathmint with a surprise inside 🌬️😈", "a microdose smart tab 🧠✨",
    "a gummy bear with 200ug 🐻🌟", "a ten-strip for the whole channel 🎟️🚀",
    "an Owsley original — vintage vibes 🎸✨", "a tab with Alex Grey art 👁️🎨",
]

ACID_ACTION_MESSAGES = [
    "places {gift} on {target}'s tongue 👅✨",
    "slides {gift} to {target} — buckle up 🎢",
    "hands {gift} to {target} — see you in 12 hours ⏰🌈",
    "drops {gift} for {target} — the walls will melt, it's fine 😉🌀",
    "offers {gift} to {target} — the fractals are calling 🔯",
]

ACID_FINAL_MESSAGES = [
    formatting.bold(formatting.color("The ceiling is a Mandelbrot set and you can zoom forever 🔯♾️🤯", formatting.colors.LIGHT_PURPLE)),
    formatting.color("Tracers on EVERYTHING — your hand just painted a rainbow across the room 🌈💫✋", formatting.colors.LIGHT_PURPLE),
    formatting.color("The music is a physical structure and you're walking through it 🎶🏛️🚶", formatting.colors.LIGHT_BLUE),
    formatting.color("You just understood the universe for 3 seconds and now it's gone 🌌🧠💨", formatting.colors.LIGHT_PURPLE),
    formatting.color("Is it still Tuesday? It's been Tuesday for 47 years 📅♾️😵‍💫", formatting.colors.LIGHT_BLUE),
    formatting.color("Your face in the mirror just winked at you independently 🧑‍🎤😉😱", formatting.colors.LIGHT_PURPLE),
    formatting.color("Every leaf on that tree is a separate universe and you can feel all of them 🍃🌌🍃", formatting.colors.LIGHT_BLUE),
    formatting.color("The come-up hits and you realize: we're all just vibrations pretending to be solid 🎵🌊🫠", formatting.colors.LIGHT_PURPLE),
]

ACID_COUNTDOWN = [
    formatting.color("👅 3... Under the tongue...", formatting.colors.LIGHT_PURPLE),
    formatting.color("🌀 2... The edges start to shimmer...", formatting.colors.LIGHT_BLUE),
    formatting.color("🎢 1... Liftoff...", formatting.colors.PURPLE),
]


# =======================
# PEYOTE Content
# =======================
PEYOTE_GIFTS = [
    "a dried peyote button 🌵✨", "a cup of San Pedro cactus tea ☕🌵",
    "a slice of fresh peyote 🪓🌵", "a mescaline extract capsule 💊🌟",
    "a sacred medicine bundle 🌿🔮", "a peyote stitch pouch (with actual peyote inside) 🧶🌵",
    "a mescaline sulfate crystal 💎🌈", "a handful of San Pedro chips 🌵🍺",
    "an ancestral vision dose 🧬🌌", "a cactus smoothie (yes, really) 🥤🌵",
]

PEYOTE_ACTION_MESSAGES = [
    "offers {gift} to {target} — the desert spirit calls 🏜️🌵",
    "hands {gift} to {target} with reverence 🙏✨",
    "shares {gift} with {target} — the cactus knows 🌵👁️",
    "places {gift} before {target} — sit with the medicine 🧘🌵",
    "presents {gift} to {target} — the grandfather spirit watches 🌞👁️",
]

PEYOTE_FINAL_MESSAGES = [
    formatting.bold(formatting.color("The desert is alive and every grain of sand is singing 🏜️🎶✨", formatting.colors.ORANGE)),
    formatting.color("Grandfather Peyote shows you the horizon where earth meets spirit 🌅👁️🌌", formatting.colors.ORANGE),
    formatting.color("The cactus is 10,000 years old and it has something to tell you 🌵🧓📜", formatting.colors.YELLOW),
    formatting.color("Colors you've never seen before drip from the stars like honey 🌟🍯🎨", formatting.colors.ORANGE),
    formatting.color("A coyote made of light trots across your field of vision and nods 🦊✨👍", formatting.colors.YELLOW),
    formatting.color("The fire ceremony has begun — shadows dance stories of creation 🔥💃🌌", formatting.colors.ORANGE),
    formatting.color("You ARE the desert. The wind is your breath. The sun is your heart 🏜️💨☀️", formatting.colors.YELLOW),
    formatting.color("The mescaline hits and suddenly every cactus looks like it's waving at you 🌵👋🌵👋🌵", formatting.colors.ORANGE),
]

PEYOTE_COUNTDOWN = [
    formatting.color("🌵 3... Chewing the bitter button...", formatting.colors.ORANGE),
    formatting.color("🏜️  2... The desert wind stirs...", formatting.colors.YELLOW),
    formatting.color("🌞 1... The grandfather speaks...", formatting.colors.RED),
]


# Content Mapping
DATA = {
    'weed': (WEED_GIFTS, WEED_ACTION_MESSAGES, WEED_FINAL_MESSAGES, WEED_COUNTDOWN),
    'bong': (BONG_GIFTS, BONG_ACTION_MESSAGES, BONG_FINAL_MESSAGES, BONG_COUNTDOWN),
    'joint': (JOINT_GIFTS, JOINT_ACTION_MESSAGES, JOINT_FINAL_MESSAGES, JOINT_COUNTDOWN),
    'keef': (KEEF_GIFTS, KEEF_ACTION_MESSAGES, KEEF_FINAL_MESSAGES, KEEF_COUNTDOWN),
    'kief': (KEEF_GIFTS, KEEF_ACTION_MESSAGES, KEEF_FINAL_MESSAGES, KEEF_COUNTDOWN),
    'trip': (DMT_GIFTS, DMT_ACTION_MESSAGES, DMT_FINAL_MESSAGES, DMT_COUNTDOWN),
    'shrooms': (SHROOMS_GIFTS, SHROOMS_ACTION_MESSAGES, SHROOMS_FINAL_MESSAGES, SHROOMS_COUNTDOWN),
    'mushrooms': (SHROOMS_GIFTS, SHROOMS_ACTION_MESSAGES, SHROOMS_FINAL_MESSAGES, SHROOMS_COUNTDOWN),
    'acid': (ACID_GIFTS, ACID_ACTION_MESSAGES, ACID_FINAL_MESSAGES, ACID_COUNTDOWN),
    'lsd': (ACID_GIFTS, ACID_ACTION_MESSAGES, ACID_FINAL_MESSAGES, ACID_COUNTDOWN),
    'peyote': (PEYOTE_GIFTS, PEYOTE_ACTION_MESSAGES, PEYOTE_FINAL_MESSAGES, PEYOTE_COUNTDOWN),
    'mescaline': (PEYOTE_GIFTS, PEYOTE_ACTION_MESSAGES, PEYOTE_FINAL_MESSAGES, PEYOTE_COUNTDOWN),
}


def _format_remaining(seconds):
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def _countdown_and_final(bot, channel, countdown_msgs, final_messages):
    try:
        if len(countdown_msgs) == 3:
            bot.say(countdown_msgs[0], channel)
            time.sleep(6)
            bot.say(countdown_msgs[1], channel)
            time.sleep(6)
            bot.say(countdown_msgs[2], channel)
            time.sleep(6)
        bot.say(random.choice(final_messages), channel)
    except Exception:
        LOG.exception("Error during countdown in %s", channel)


@module.commands('weed', 'bong', 'joint', 'keef', 'kief', 'trip', 'shrooms', 'mushrooms', 'acid', 'lsd', 'peyote', 'mescaline')
@module.example('$weed username', 'Give a user a random weed item/message')
def weed_commands(bot, trigger):
    """Send a lighthearted smoking message with cooldowns.

    If a `target` is given, send an action handing them a random gift and return.
    Otherwise, perform a short non-blocking countdown and post a final message.
    """
    channel = trigger.sender
    now = time.time()
    user_id = trigger.account or trigger.nick
    cmd = trigger.group(1).lower()
    
    gifts, action_msgs, final_msgs, countdown_msgs = DATA.get(cmd, DATA['weed'])

    # Shared cooldown key for all commands
    key = (channel, user_id)

    # If a target user is specified, give them a random item immediately (no countdown)
    if trigger.group(2):
        # Per-user cooldown check (only for give action)
        with LOCK:
            last_user = PER_USER_LAST.get(key)
            if last_user:
                elapsed_user = now - last_user
                if elapsed_user < PER_USER_COOLDOWN:
                    remaining = PER_USER_COOLDOWN - elapsed_user
                    bot.notice(f"You must wait {_format_remaining(remaining)} before giving {cmd} again in {channel}.", trigger.nick)
                    return
        
        # Update per-user cooldown
        with LOCK:
            PER_USER_LAST[key] = now
        
        target_user = trigger.group(2).strip()
        gift = random.choice(gifts)
        template = random.choice(action_msgs)
        bot.action(template.format(target=target_user, gift=gift))
        return

    # Channel cooldown check (only for countdown action)
    with LOCK:
        last_chan = LAST_USED.get(channel)
        if last_chan:
            elapsed = now - last_chan
            if elapsed < COOLDOWN:
                remaining = COOLDOWN - elapsed
                bot.notice(f"The countdown is on cooldown for {_format_remaining(remaining)} in {channel}.", trigger.nick)
                return

    # Update channel timestamp for countdown action
    with LOCK:
        LAST_USED[channel] = now

    # Start countdown+final message in a background thread to avoid blocking the bot
    t = threading.Thread(target=_countdown_and_final, args=(bot, channel, countdown_msgs, final_msgs), daemon=True)
    t.start()
