"""curse.py — Sopel plugin: Demolition Man Verbal Morality Statute fines

When this plugin is enabled in a channel, any message containing a
swear word is met with an automated fine citation — just like the
verbal morality booths in Demolition Man (1993).

Commands:
  .curse on   — enable in the current channel (op / bot-admin only)
  .curse off  — disable in the current channel (op / bot-admin only)

The plugin is DISABLED by default in every channel.
"""
from __future__ import annotations

import re
import threading

from sopel import module, plugin

# ============================================================
# ==================  CONFIGURATION  ========================
# ============================================================

PLUGIN_NAME = "curse"

# Words that earn a fine.  Listed as plain stems; the regex is built
# automatically so partial matches (e.g. "bullshit" → "shit") are caught.
BANNED_WORDS: list[str] = [
    "fuck", "shit", "ass", "bitch", "bastard", "cunt", "cock", "dick",
    "pussy", "whore", "slut", "damn", "hell", "crap", "piss", "douche",
    "twat", "wanker", "bollocks", "arse", "fag", "prick", "jerk",
    "motherfucker", "asshole", "douchebag", "dumbass", "jackass",
    "bullshit", "horseshit", "dipshit", "shithead", "fuckhead",
    "clusterfuck", "fucktard", "bastardize", "bitchass", "dumbfuck",
    "goddamn", "goddammit", "dammit", "friggin", "freaking", "freakin",
    "friggin", "sumbitch",
]

# Demolition Man–flavoured fine messages.
# {nick} → offending user,  {word} → the offending term.
# Every message references the Verbal Morality Statute / code section.
FINE_MESSAGES: list[str] = [
    # --- Classic booth style ---
    "⚠️  ATTENTION {nick}: You have been fined one credit for violation of the Verbal Morality Statute §1.1. Please collect your ticket. 📜🎫",
    "🚨 VERBAL MORALITY STATUTE §2.0 VIOLATION — {nick}, that will be one credit. Thank you for your compliance. 🤖💳",
    "📋 CITATION ISSUED: {nick}, use of \"{word}\" violates San Angeles Verbal Morality Code §3.7. One credit will be debited. 💸🎫",
    "🔊 *BLEEP* — Verbal Morality Statute §1.1 activated. {nick}, civil language is mandatory. Fine: 1 credit. 🏛️📜",
    "💳 Verbal Morality Code §4.2 infraction detected! {nick}, one credit has been deducted from your account. 😬⚖️",
    "🎫 TICKET DISPENSED: Verbal Morality Statute §6.0 — {nick}, \"{word}\" is morally unacceptable. Fine: 1 credit. Have a nice day! ☀️🤖",
    "⚖️  INFRACTION LOGGED — {nick}: \"{word}\" violates San Angeles Verbal Morality Code §7.4. Fine: 1 credit. 🏙️💳",
    "📢 Automated citation under Verbal Morality Statute §5.3: {nick}, your account has been debited 1 credit for language unbecoming of a civilized society. 🌆✨",
    "🤖 VERBAL MORALITY TERMINAL §2.9: Obscene utterance \"{word}\" detected from {nick}. Fine of 1 credit processed. Please remain civil. 🙏📋",
    "🚔 LINGUISTIC ENFORCEMENT — Verbal Morality Code §8.1: {nick}, \"{word}\" is not appropriate for polite society. One credit fine assessed. Compliance is appreciated! 😊⚠️",
    # --- Department / Authority style ---
    "🏛️ The San Angeles Department of Verbal Compliance (§3.3) has issued {nick} a citation for obscene language. Fine: 1 credit. 📜🤖",
    "📡 AUTOMATED MORALITY SCAN — Verbal Morality Statute §1.1: Profanity detected. {nick}, your fine of 1 credit has been logged. Have a sanitised day! 🧼✨",
    "🖨️ FINE RECEIPT — Verbal Morality Code §9.0: {nick} owes 1 credit for the utterance of \"{word}\". Please retain this ticket for your records. 🎫📋",
    "🔐 San Angeles Civil Conduct Authority — §5.5: {nick}, use of prohibited language \"{word}\" carries a mandatory 1-credit fine. No exceptions. 🏙️⚖️",
    "📣 PUBLIC SERVICE NOTICE under Verbal Morality Statute §2.4: {nick}, your language has been flagged. One credit deducted. Let's keep San Angeles beautiful! 🌸🏙️",
    "🛡️ MORALITY ENFORCEMENT DIVISION §6.6: {nick}, the term \"{word}\" is listed under Schedule A of the Verbal Morality Statute. Fine: 1 credit. 💳📜",
    "🗂️ CASE FILE OPENED — Verbal Morality Code §4.8: Subject {nick} uttered \"{word}\" in a public channel. Penalty: 1 credit. Compliance expected going forward. 🤖📋",
    "📊 INFRACTION REPORT §7.7: {nick} has accumulated a new violation under the Verbal Morality Statute. Offending term: \"{word}\". Credit deducted: 1. 💸⚠️",
    "🖥️ SYSTEM ALERT — Verbal Morality Statute §1.1: Language filter triggered by {nick}. Word: \"{word}\". Automated fine of 1 credit issued. Thank you. 🤖💳",
    "🔔 COMPLIANCE NOTIFICATION §3.1: {nick}, the San Angeles Morality Grid has detected a prohibited utterance. Fine applied: 1 credit. 🏙️🔔",
    # --- Polite / sarcastically cheerful style ---
    "😊 Oopsie! Verbal Morality Statute §2.2 reminder for {nick}: \"{word}\" is not permitted in civilised chat. One credit fine — have a lovely day! 🌼💳",
    "🌟 Friendly reminder from the Verbal Morality Bureau §4.4: {nick}, that language just cost you 1 credit. Every day is a chance to be better! ☀️📜",
    "🤗 The San Angeles Courtesy Council (§5.1) gently reminds {nick} that \"{word}\" is a fineable offence. 1 credit, please! 💛🎫",
    "🌺 Your neighbourhood Verbal Morality Terminal §8.3 has issued {nick} a fine of 1 credit. Positivity is mandatory! 😄🏙️",
    "✨ Just a little nudge from Verbal Morality Code §6.2, {nick} — \"{word}\" is on the prohibited list. Fine: 1 credit. Stay positive! 🌈💳",
    # --- Stern / bureaucratic style ---
    "🗃️ FORMAL NOTICE — Per Verbal Morality Statute §9.9, Section IV: {nick} is hereby fined 1 credit for use of the term \"{word}\". Continued violations may result in escalation. ⚖️📜",
    "🚫 PROHIBITED LANGUAGE DETECTED — Verbal Morality Code §7.0: {nick}, this is your official record of infraction. Fine: 1 credit. This notice will be retained in your compliance file. 🗂️🤖",
    "⛔ VIOLATION RECORDED — Verbal Morality Statute §3.9, Sub-clause 2: {nick} has used language in direct contravention of San Angeles civil conduct laws. Penalty: 1 credit. ⚖️🏛️",
    "📌 OFFICIAL CITATION §6.8: The Verbal Morality Statute prohibits the use of \"{word}\" in public discourse. {nick}, your fine of 1 credit is non-negotiable. 🤖💳",
    "🧾 RECEIPT OF PENALTY — Verbal Morality Code §2.7: {nick} — fine amount: 1 credit. Reason: use of classified offensive term \"{word}\". No appeal period applies. 📋⚖️",
    # --- Theatrical / dramatic style ---
    "💥 MORALITY BREACH! Verbal Morality Statute §1.1 has been triggered by {nick}! The word \"{word}\" has shaken the very foundations of San Angeles! Fine: 1 credit! 😱🏙️",
    "🎭 Oh dear… {nick}, the Verbal Morality Code §5.9 weeps at the utterance of \"{word}\". The booth has no choice. Fine: 1 credit. The drama! 😩📜",
    "🌊 A WAVE OF VERBAL POLLUTION detected from {nick}! Verbal Morality Statute §4.7 demands immediate remedy. Fine issued: 1 credit. San Angeles will recover. 💧🏙️",
    "⚡ CRITICAL INFRACTION — Verbal Morality Statute §8.8: {nick} dropped a \"{word}\" in the presence of civilised citizens! Fine: 1 credit. For shame! 😤📋",
    "🎺 HEAR YE, HEAR YE — Verbal Morality Code §3.6 has been invoked against {nick} for the utterance of \"{word}\"! The fine of 1 credit shall be paid! Long live San Angeles! 👑🤖",
    "🌋 ERUPTION OF IMPROPRIETY from {nick} — Verbal Morality Statute §9.3 activated! \"{word}\" is strictly forbidden! Fine: 1 credit. Contain yourself, citizen! 🫡⚖️",
    # --- Robotic / AI terminal style ---
    "🤖 [MORALITY_BOT v4.1 — §1.1]: BANNED_WORD=\"{word}\" | USER={nick} | ACTION=FINE | AMOUNT=1_CREDIT | STATUS=PROCESSED ✅",
    "🖥️ [SAN_ANGELES_VM — VERBAL MORALITY CODE §2.6]: INPUT_FLAG=OBSCENE | NICK={nick} | TERM=\"{word}\" | DEBIT=1CR | HAVE_A_NICE_DAY=TRUE 🤖💳",
    "📟 [VMS-TERMINAL §7.2 — AUTOMATED RESPONSE]: Citizen {nick} has violated statutes governing acceptable speech. Term logged: \"{word}\". Fine: 1 credit. Compliance module updated. 🛡️📡",
    "⚙️ [LINGUISTIC_FILTER §5.7 — TRIGGER FIRED]: Prohibited utterance from {nick}. Statute: Verbal Morality Code §5.7. Penalty unit: 1 credit. Retraining recommended. 🔧🤖",
    "📲 [morality_daemon §6.9 PID:2032]: alert — profanity_match word=\"{word}\" user={nick} channel=PUBLIC fine=1 statute=\"VMS §6.9\" ack_required=false 🖥️✅",
    # --- Pop-culture twist style ---
    "🌇 Welcome to San Angeles, {nick}. Here, we don't say \"{word}\". Verbal Morality Statute §4.0 has assessed your fine: 1 credit. Be well, citizen! 🏙️😌",
    "🔭 In the future, language is clean and people are polite — except you, {nick}. Verbal Morality Code §8.5 disagrees with \"{word}\". Fine: 1 credit. 🤖📜",
    "👮 Officer Lenina Huxley of the SAPD has cited {nick} under Verbal Morality Statute §3.2 for saying \"{word}\". Fine: 1 credit. You're lucky she didn't use the Sonic Disruptor. 🎶⚖️",
    "🍔 Taco Bell may have won the restaurant wars, but {nick} just lost the language wars. Verbal Morality Code §7.8: fine of 1 credit for \"{word}\". 🌮💳",
    "❄️ Even in cryo-stasis {nick} shouldn't be dreaming about words like \"{word}\". Verbal Morality Statute §2.1: 1 credit fine upon thawing. 🧊⚖️",
    "🏆 San Angeles Morality Achievement Unlocked — {nick}: \"First Offence Under Verbal Morality Statute §1.1!\" Reward: a fine of 1 credit and a complimentary ticket! 🎫🥇",
]

# ============================================================
# =====================  INTERNALS  ==========================
# ============================================================

# {channel_lower: bool} — missing key → disabled (default)
_channel_toggles: dict[str, bool] | None = None
_toggles_lock = threading.Lock()

# Short words that appear innocently inside common English words (e.g. "hell"
# in "seashells", "ass" in "classic").  These require a word boundary at the
# start of the match.  Longer / more specific profane roots ("fuck", "shit",
# etc.) are unlikely to appear innocently mid-word, so they match anywhere and
# will still catch compounds like "sheepfucker" or "clusterfuck".
STRICT_BOUNDARY_WORDS: set[str] = {
    "ass", "hell", "cock", "dick", "prick", "fag", "jerk", "damn",
}

_strict_alts = sorted(
    (w for w in BANNED_WORDS if w in STRICT_BOUNDARY_WORDS), key=len, reverse=True
)
_free_alts = sorted(
    (w for w in BANNED_WORDS if w not in STRICT_BOUNDARY_WORDS), key=len, reverse=True
)

# Group 1 → strict (word-boundary anchored), Group 2 → free (anywhere in word)
_BANNED_RE: re.Pattern = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _strict_alts) + r")"
    r"|(" + "|".join(re.escape(w) for w in _free_alts) + r")",
    re.IGNORECASE,
)


def _load_toggles(bot) -> dict[str, bool]:
    global _channel_toggles
    with _toggles_lock:
        if _channel_toggles is None:
            val = bot.db.get_plugin_value(PLUGIN_NAME, "channel_toggles")
            _channel_toggles = val if isinstance(val, dict) else {}
        return _channel_toggles


def _save_toggles(bot, toggles: dict[str, bool]) -> None:
    bot.db.set_plugin_value(PLUGIN_NAME, "channel_toggles", toggles)


def _is_enabled(bot, channel: str) -> bool:
    """Return True only if the plugin has been explicitly enabled in *channel*."""
    toggles = _load_toggles(bot)
    # Default is False (disabled)
    return toggles.get(channel.lower(), False)


def _set_enabled(bot, channel: str, enabled: bool) -> None:
    toggles = _load_toggles(bot)
    toggles[channel.lower()] = enabled
    _save_toggles(bot, toggles)


def _is_op_or_admin(bot, trigger) -> bool:
    """Return True if *trigger* belongs to a channel op, half-op, admin, or owner."""
    # Bot owner / configured admins
    if getattr(trigger, "owner", False) or getattr(trigger, "admin", False):
        return True
    # Also check core config admins list
    try:
        cfg_admins = getattr(bot.config.core, "admins", None)
        if isinstance(cfg_admins, (list, tuple, set)):
            if trigger.nick.lower() in {a.lower() for a in cfg_admins}:
                return True
    except Exception:
        pass
    # Channel privileges — check for op (+o) or higher
    channel_name = str(trigger.sender)
    try:
        chan = bot.channels.get(channel_name)
        if chan:
            priv = chan.privileges.get(trigger.nick, 0)
            # plugin.OP covers @, plugin.HALFOP covers %, plugin.ADMIN covers &, plugin.OWNER covers ~
            if priv >= plugin.HALFOP:
                return True
    except Exception:
        pass
    return False


# ============================================================
# ===================  COMMAND: .curse  ======================
# ============================================================

@module.commands("curse")
def curse_toggle(bot, trigger):
    """Enable or disable the Verbal Morality Statute in this channel.

    Usage: .curse on | .curse off
    Requires channel op or bot admin/owner.
    """
    if not trigger.sender.startswith("#"):
        bot.reply("This command only works in a channel.")
        return

    arg = (trigger.group(2) or "").strip().lower()

    if arg not in ("on", "off"):
        status = "enabled 🟢" if _is_enabled(bot, str(trigger.sender)) else "disabled 🔴"
        bot.reply(
            f"Verbal Morality Statute is currently {status} in {trigger.sender}. "
            "Use '.curse on' or '.curse off' to change it."
        )
        return

    if not _is_op_or_admin(bot, trigger):
        bot.reply("⛔ You need to be a channel op or bot admin to change this setting.")
        return

    enable = arg == "on"
    _set_enabled(bot, str(trigger.sender), enable)

    if enable:
        bot.say(
            f"⚖️  VERBAL MORALITY STATUTE ACTIVATED in {trigger.sender}. "
            "Inappropriate language will result in an automated fine. "
            "Enjoy your San Angeles experience! 🏙️🤖"
        )
    else:
        bot.say(
            f"🔕 Verbal Morality Statute deactivated in {trigger.sender}. "
            "You may now speak freely… for now. 😏"
        )


# ============================================================
# =================  LISTENER: fine offenders  ===============
# ============================================================

@module.rule(r".*")
@module.unblockable
def monitor_language(bot, trigger):
    """Listen for banned words and issue a fine if triggered."""
    # Only act in channels where the plugin is enabled
    if not trigger.sender.startswith("#"):
        return
    if not _is_enabled(bot, str(trigger.sender)):
        return
    # Don't respond to the bot's own messages
    if trigger.nick == bot.nick:
        return
    # Ignore ACTION messages (optional — remove this block to fine /me actions too)
    if trigger.event == "ACTION":
        return

    match = _BANNED_RE.search(trigger.group(0) or "")
    if not match:
        return

    import random
    word = next(g for g in match.groups() if g is not None).lower()
    template = random.choice(FINE_MESSAGES)
    bot.say(template.format(nick=trigger.nick, word=word))
