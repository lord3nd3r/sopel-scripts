"""
cat.py - Print a unicode cat.

Author: Kristopher Craig
Commands:
    $cat - one of the cats below
"""

import random

from sopel import plugin

# Same blocky unicode look as ᓚᘏᗢ. No emoji cats.
CATS = [
    "ᓚᘏᗢ",
    "ᘛ⁐̤ᕐᐷ",
    "ᓚ₍ ^.ᗜ.^₎",
    "ᓚ₍ ^. .^₎",
    "/ᐠ｡ꞈ｡ᐟ\\",
    "/ᐠ.ꞈ.ᐟ\\",
    "/ᐠ｡‸｡ᐟ\\",
    "ฅᨓฅ",
    "ฅ^•ﻌ•^ฅ",
    "ᵔᴥᵔ",
    "(ᓀ ᓀ)",
    "ᓄᘏᗢ",
    "(ﾐචᆽචﾐ)",
    "(=චᆽච=)",
    "ᓚᘏᗢᗣ",
]

_last = None


@plugin.command('cat')
@plugin.example('$cat')
def cat(bot, trigger):
    """Print a cat."""
    global _last
    choices = [c for c in CATS if c != _last] or CATS
    picked = random.choice(choices)
    _last = picked
    bot.say(picked)
