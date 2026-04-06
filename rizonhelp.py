# rizonhelp.py — Rizon IRC Network help script for Sopel
# Knowledge sourced from https://wiki.rizon.net/
# Disabled in all channels by default. Enable with $rizonhelpon.
from sopel import plugin


# ---------------------------------------------------------------------------
# Per-channel enable / disable
# ---------------------------------------------------------------------------

@plugin.command("rizonhelpon")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to use this command.")
def cmd_on(bot, trigger):
    """$rizonhelpon — Enable Rizon help in this channel."""
    channel = str(trigger.sender)
    bot.db.set_channel_value(channel, "rizonhelp", True)
    bot.reply("Rizon help enabled.")


@plugin.command("rizonhelpoff")
@plugin.require_chanmsg("This command only works in channels.")
@plugin.require_privilege(plugin.OP, "You must be a channel operator to use this command.")
def cmd_off(bot, trigger):
    """$rizonhelpoff — Disable Rizon help in this channel."""
    channel = str(trigger.sender)
    bot.db.set_channel_value(channel, "rizonhelp", False)
    bot.reply("Rizon help disabled.")


def _enabled(bot, trigger):
    channel = str(trigger.sender)
    return bool(bot.db.get_channel_value(channel, "rizonhelp"))


# ---------------------------------------------------------------------------
# Topic database — all content from https://wiki.rizon.net/
# ---------------------------------------------------------------------------

TOPICS = {
    # ---- Nick Registration ----
    "register": {
        "title": "Nick Registration",
        "aliases": ["register", "regnick", "nickserv register", "reg"],
        "content": [
            "Register your nick: /msg NickServ REGISTER yourPassword your@email.address",
            "Check your email and confirm: /msg NickServ CONFIRM ConfirmationCodeFromEmail",
            "The code expires in 24 hours. Use a real email — Yahoo/Hotmail may filter it to spam.",
            "If you entered the wrong email: /msg NickServ CANCEL registrationPassword",
            "More: https://wiki.rizon.net/index.php?title=Register_your_nickname",
        ],
    },
    "identify": {
        "title": "Identify / Login",
        "aliases": ["identify", "id", "login", "nickserv identify", "auth"],
        "content": [
            "Identify to your nick: /msg NickServ IDENTIFY yourPassword",
            "Or set up SASL for automatic identification (see $rhelp sasl).",
            "Or use CertFP for certificate-based auth (see $rhelp certfp).",
        ],
    },
    "password": {
        "title": "Change / Reset Password",
        "aliases": ["password", "resetpass", "reset password", "forgot password", "changepass"],
        "content": [
            "Change password (must be identified): /msg NickServ SET PASSWORD newPassword",
            "Forgot password: /msg NickServ RESETPASS yourNick",
            "Check email, then: /msg NickServ ENTERCODE yourNick codeFromEmail (expires in 24h)",
            "You'll get a temp password — identify with it, then change it with SET PASSWORD.",
            "More: https://wiki.rizon.net/index.php?title=Register_your_nickname#Reset_Password",
        ],
    },
    "group": {
        "title": "NickServ Groups",
        "aliases": ["group", "nickgroup", "nick group", "groupnick"],
        "content": [
            "Group lets you share channel access, memos & settings across up to 10 nicks.",
            "1. Make sure the new nick is NOT registered: /msg NickServ INFO newNick",
            "2. Switch to it: /nick newNick",
            "3. Group it: /msg NickServ GROUP MainNick passwordOfMainNick",
            "To drop a grouped nick: /msg NickServ DROP nickToDrop (then confirm with the code).",
            "More: https://wiki.rizon.net/index.php?title=Register_your_nickname#NickServ_Groups",
        ],
    },
    "expired": {
        "title": "Expired Nickname",
        "aliases": ["expired", "expire", "nick expired", "inactive nick"],
        "content": [
            "Nicks expire after 90 days of inactivity (not identified for 90 days).",
            "All channel access tied to that nick is also removed.",
            "You'll need to re-register it if it expires.",
        ],
    },

    # ---- Channel Registration ----
    "chanreg": {
        "title": "Channel Registration",
        "aliases": ["chanreg", "register channel", "regchan", "channel registration", "channel register"],
        "content": [
            "Requirements: registered nick, identified, and have @ or higher in the channel.",
            "Join an empty unregistered channel to auto-get @, then:",
            "/msg ChanServ REGISTER #channel password description",
            "Registered channels are dropped if completely empty for 30 consecutive days.",
            "More: https://wiki.rizon.net/index.php?title=Channel_Registration",
        ],
    },

    # ---- Channel Management 101 ----
    "xop": {
        "title": "Channel Access — xOP System",
        "aliases": ["xop", "vop", "hop", "aop", "sop", "channel access", "op"],
        "content": [
            "VOP (+v voice) | HOP (% halfop) | AOP (@ op) | SOP (& protect)",
            "Add: /msg ChanServ VOP #chan ADD nick  (same for HOP, AOP, SOP)",
            "Del: /msg ChanServ VOP #chan DEL nick",
            "View list: /msg ChanServ ACCESS #channel LIST",
            "Higher levels can manage lower ones. Founder can manage all.",
            "More: https://wiki.rizon.net/index.php?title=Channel_Management_101",
        ],
    },
    "flags": {
        "title": "Channel Access — FLAGS System",
        "aliases": ["flags", "channel flags"],
        "content": [
            "FLAGS is the most powerful access system — assigns specific permissions per user.",
            "Each user gets a list of flags (e.g. KICK, TOPIC, BAN, etc.).",
            "Use: /msg ChanServ HELP FLAGS for full details.",
            "More: https://wiki.rizon.net/index.php?title=Channel_Management_101#FLAGS",
        ],
    },
    "access": {
        "title": "Channel Access — ACCESS (Numerical Levels)",
        "aliases": ["access", "access list", "numerical access", "levels"],
        "content": [
            "ACCESS gives each user a number (1-9999). Higher numbers dominate lower ones.",
            "You can specify what each level can do (e.g., level 3+ can KICK).",
            "To use ACCESS instead of xOP: /msg ChanServ SET #channel XOP OFF",
            "Add user: /msg ChanServ ACCESS #channel ADD nick level",
            "Del user: /msg ChanServ ACCESS #channel DEL nick",
            "View list: /msg ChanServ ACCESS #channel LIST",
            "To auto-voice ALL joining users, you must use ACCESS (not xOP).",
            "More: https://wiki.rizon.net/index.php?title=Channel_Management_101#ACCESS",
        ],
    },
    "ownermode": {
        "title": "Owner & Protect Modes",
        "aliases": ["ownermode", "protectmode", "owner", "protect"],
        "content": [
            "Enable owner (~): /msg ChanServ SET #channel OWNERMODE ON",
            "Enable protect (&): /msg ChanServ SET #channel PROTECTMODE ON",
            "After setting, rejoin or: /msg ChanServ SYNC #channel",
        ],
    },
    "botserv": {
        "title": "BotServ",
        "aliases": ["botserv", "bot", "funserv"],
        "content": [
            "BotServ lets you bring a Rizon bot into your registered channel.",
            "View available bots: /msg BotServ BOTLIST",
            "Assign one: /msg BotServ ASSIGN #channel botName",
            "With BotServ, you can use ChanServ commands via channel text (e.g. .kick Joe).",
            "Custom bots: apply at http://s.rizon.net/authline if you meet the requirements.",
            "More: https://wiki.rizon.net/index.php?title=Channel_Management_101#BotServ",
        ],
    },

    # ---- Channel Management 102 ----
    "successor": {
        "title": "Channel Successor",
        "aliases": ["successor", "channel successor"],
        "content": [
            "Set a successor who inherits the channel if your nick expires/is dropped:",
            "/msg ChanServ SET #channel SUCCESSOR nick",
            "The successor may claim ownership if you don't identify for 30 days.",
        ],
    },
    "chanpass": {
        "title": "Channel Password",
        "aliases": ["chanpass", "channel password"],
        "content": [
            "Change channel founder password: /msg ChanServ SET #channel PASSWORD newPassword",
        ],
    },
    "chandesc": {
        "title": "Channel Description",
        "aliases": ["chandesc", "channel description", "channel desc"],
        "content": [
            "Change channel description (shown in INFO): /msg ChanServ SET #channel DESC description",
        ],
    },
    "entrymsg": {
        "title": "Channel Entry Message",
        "aliases": ["entrymsg", "entry message", "greet"],
        "content": [
            "Set a message sent to everyone who joins: /msg ChanServ SET #channel ENTRYMSG message",
            "To clear it, run the command with no message.",
        ],
    },
    "secureops": {
        "title": "Secure Ops & Secure Founder",
        "aliases": ["secureops", "secure ops", "securefounder", "secure founder"],
        "content": [
            "Secure ops — only users on the access list get ops:",
            "/msg ChanServ SET #channel SECUREOPS ON",
            "Secure founder — only the real founder can drop/change founder/password:",
            "/msg ChanServ SET #channel SECUREFOUNDER ON  (enabled by default)",
        ],
    },
    "signkick": {
        "title": "Sign Kick",
        "aliases": ["signkick", "sign kick"],
        "content": [
            "Show who issued a ChanServ kick in the reason:",
            "/msg ChanServ SET #channel SIGNKICK ON",
            "Use LEVEL to hide kicks from high-level users. OFF to disable.",
        ],
    },
    "topiclock": {
        "title": "Topic Lock",
        "aliases": ["topiclock", "topic lock"],
        "content": [
            "Prevent topic changes except via ChanServ TOPIC command:",
            "/msg ChanServ SET #channel TOPICLOCK ON",
        ],
    },
    "founder": {
        "title": "Transfer Channel Founder (WARNING!)",
        "aliases": ["founder", "transfer channel", "transfer founder"],
        "content": [
            "WARNING: This gives away your channel permanently!",
            "/msg ChanServ SET #channel FOUNDER nick",
            "You must enter the command TWICE to confirm. Once transferred, it's no longer yours.",
        ],
    },

    # ---- Channel Modes ----
    "chanmodes": {
        "title": "Channel Modes",
        "aliases": ["chanmodes", "channel modes", "cmode", "cmodes"],
        "content": [
            "+c no colors | +C no CTCPs | +n no external msgs | +m moderated | +M reg-only talk",
            "+N no notices | +i invite-only | +R reg-only join | +S SSL-only | +t ops-topic",
            "+s secret | +p paranoia | +B bandwidth saver | +k key (password) | +l user limit",
            "+b ban | +e ban exempt | +I invite exempt",
            "Set: /mode #chan +mode  |  Unset: /mode #chan -mode",
            "Full list: https://wiki.rizon.net/index.php?title=Channel_Modes",
        ],
    },

    # ---- User Modes ----
    "usermodes": {
        "title": "User Modes",
        "aliases": ["usermodes", "user modes", "umode", "umodes"],
        "content": [
            "+C no CTCP | +D deaf (no channel msgs) | +g caller ID (block PMs unless /accept'ed)",
            "+G soft caller ID (block PMs from non-shared-channel users) | +R reg-only PMs",
            "+i invisible | +p private (hide channels/idle in whois) | +x cloaked hostname",
            "Set: /mode yourNick +mode  |  Unset: /mode yourNick -mode",
            "+r (registered) and +S (SSL) are set by the server automatically.",
            "Full list: https://wiki.rizon.net/index.php?title=User_Modes",
        ],
    },

    # ---- vHost ----
    "vhost": {
        "title": "vHost (Virtual Host)",
        "aliases": ["vhost", "virtual host", "hostserv", "host"],
        "content": [
            "A vHost hides your real hostname with a custom one (e.g. i.am.awesome).",
            "Request: /msg HostServ REQUEST desired.vhost.here",
            "Rules: must contain a dot, no IPs, no resolving domains, no offensive/gov/network terms,",
            "       max 63 chars. Wait 7 days between requests (1 day for grouped nicks).",
            "After approval: /msg HostServ ON",
            "More: https://wiki.rizon.net/index.php?title=VHost",
        ],
    },

    # ---- RizonBNC ----
    "bnc": {
        "title": "RizonBNC",
        "aliases": ["bnc", "rizonbnc", "bouncer"],
        "content": [
            "Free bouncer — stay connected 24/7 and store offline messages. Rizon only.",
            "Rules: use it at least once every 2 weeks. One account per person.",
            "Request: nick must be registered for 7+ days, connect via SSL, /join #RizonBNC,",
            "  then: /msg RizonBNC request EU  or  /msg RizonBNC request US",
            "Wait for approval memo: /msg MemoServ READ LAST",
            "Connect: /server rizonbnc.LOCATION.rizon.net +12345 BNCuser:BNCpassword",
            "Change BNC password: /join #RizonBNC then /msg RizonBNC CHANGEPASS newPassword",
            "More: https://wiki.rizon.net/index.php?title=RizonBNC_FAQ",
        ],
    },

    # ---- SSL/TLS ----
    "ssl": {
        "title": "SSL/TLS Secure Connection",
        "aliases": ["ssl", "tls", "secure", "secure connection"],
        "content": [
            "Connect to Rizon securely on port +6697 or +9999.",
            "Rizon uses Let's Encrypt certificates (per-server, rotated frequently).",
            "For help setting up SSL in your client, join #SSL.",
            "See also: $rhelp sasl, $rhelp certfp",
        ],
    },

    # ---- SASL ----
    "sasl": {
        "title": "SASL Authentication",
        "aliases": ["sasl"],
        "content": [
            "SASL auto-identifies you during connection — no manual /msg NickServ needed.",
            "Two types: SASL PLAIN (nick+password) and SASL EXTERNAL (CertFP).",
            "--- SASL PLAIN ---",
            "mIRC: Tools > Options > Connect > Add server, Login Method: SASL (/CAP), Password: yours, Port: +6697",
            "HexChat: Network List > Rizon > Edit, Login method: SASL (username + password)",
            "WeeChat: /set irc.server.rizon.sasl_mechanism plain",
            "  /set irc.server.rizon.sasl_username YourNick",
            "  /secure set rizon YourPassword",
            "Irssi: /NETWORK ADD -sasl_mechanism PLAIN -sasl_username YourNick -sasl_password YourPass Rizon",
            "More: https://wiki.rizon.net/index.php?title=SASL",
        ],
    },

    # ---- CertFP ----
    "certfp": {
        "title": "Client Certificate Fingerprint (CertFP)",
        "aliases": ["certfp", "cert", "certificate", "fingerprint"],
        "content": [
            "CertFP lets you auto-identify via SSL client certificate — no password needed.",
            "1. Generate cert: openssl req -nodes -newkey rsa:4096 -keyout Rizon.key -x509 -days 365 -out Rizon.cer",
            "2. Combine: cat Rizon.cer Rizon.key > Rizon.pem  (Linux)  |  copy Rizon.cer+Rizon.key Rizon.pem  (Windows)",
            "3. Configure your client to use Rizon.pem (varies by client).",
            "4. Connect via SSL, identify, then: /msg NickServ ACCESS ADD FINGERPRINT",
            "5. Set client to use SASL External login method, reconnect.",
            "More: https://wiki.rizon.net/index.php?title=CertFP",
        ],
    },

    # ---- Servers ----
    "servers": {
        "title": "Rizon Servers",
        "aliases": ["servers", "server list", "connect"],
        "content": [
            "Connect: irc.rizon.net — Port: +6697/+9999 (SSL) or 6660-6670/7000 (insecure)",
            "NA: lithium (Fremont CA), magnet (Berkeley SC), irc.rizon.io (Dallas TX),",
            "    irc.shells.org (Raleigh NC), solenoid (The Dalles OR), irc.xtremeprovider.com (LA),",
            "    irc.rizon.life (Montreal QC)",
            "SA: hydrogen (São Paulo) | EU: irc.rizon.cc (London), irc.mufff.in (Germany),",
            "    irc.rizon.club (France), irc.uworld.se (Sweden), irc.tngnet.com & irc.rizon.foo (NL)",
            "Asia: helium (Mumbai), irc.losslessone.com (Tokyo)",
            "You can't connect directly to individual servers — irc.rizon.net auto-routes you.",
        ],
    },

    # ---- Staff ----
    "staff": {
        "title": "Rizon Staff & Teams",
        "aliases": ["staff", "ircop", "opers", "admin"],
        "content": [
            "Need staff help? /join #services",
            "Staff levels: IRC Operators > Services Operators > Channel Services Operators > Services Admins > Network Admins",
            "Teams: #help (Help Team) | #abuse (Abuse Team) | #dev (Dev Team)",
            "       vHost Team | KLine Team (http://abuse.rizon.net for ban reviews) | Routing Team",
            "More: https://wiki.rizon.net/index.php?title=Staff",
        ],
    },

    # ---- Help Channels ----
    "helpchannels": {
        "title": "Help Channels",
        "aliases": ["helpchannels", "help channels", "help chan"],
        "content": [
            "#help — main help channel | #services — staff help for network/services issues",
            "#SSL — SSL setup help | #abuse — IRC operator abuse reports",
            "#dev — IRCd questions | #help.script — scripting/coding help",
            "Translations: #help.br (Portuguese), #help.de (German), #help.es (Spanish), #help.nl (Dutch)",
            "#antivirus — malware help | #computers — general PC help | #linux — Linux help",
            "#xdcc-help — DCC/XDCC file sharing help",
        ],
    },

    # ---- FAQ: Banned ----
    "banned": {
        "title": "Help, I'm Banned!",
        "aliases": ["banned", "ban", "kicked", "channel ban", "unban"],
        "content": [
            "Banned from a channel? Talk to the channel founder/ops. Rizon staff won't intervene — channel ops can run their channel as they see fit.",
            "If founder ignores you, stay away and find another channel or make your own.",
            "Founder locked out? Try: /msg ChanServ CLEAR #channel MODES",
            "  Invite-only: /msg ChanServ INVITE #channel",
            "  Key needed: /msg ChanServ GETKEY #channel, then /join #channel theKey",
            "  Full: /msg ChanServ SET #channel MLOCK -l",
            "  Banned: /msg ChanServ UNBAN #channel",
            "  Check who re-bans you: /msg ChanServ CHECKBAN #channel",
        ],
    },

    # ---- FAQ: Flooding ----
    "flooded": {
        "title": "My Channel is Being Flooded!",
        "aliases": ["flooded", "flood", "flooding"],
        "content": [
            "Set channel modes to mitigate: +m (moderated), +R (reg-only join), +M (reg-only talk).",
            "Use +b *!*@offending.host to ban the source.",
            "For persistent bot floods, report to #services.",
            "More: https://wiki.rizon.net/index.php?title=Channel_Related_FAQ",
        ],
    },

    # ---- FAQ: Ban Evading ----
    "banevade": {
        "title": "Ban Evading",
        "aliases": ["banevade", "ban evade", "ban evading", "evade"],
        "content": [
            "Bad ban: +b Nick!*@* — user just changes nick. Better: +b *!*@their.host",
            "Use /whois nick to find their host, then ban on that.",
            "If they keep changing hosts, add to AKICK: /msg ChanServ AKICK #channel ADD nick reason",
            "Persistent evaders: report to #services.",
        ],
    },

    # ---- FAQ: Spammers ----
    "spammers": {
        "title": "Spammers in My Channel",
        "aliases": ["spammers", "spam", "spamming"],
        "content": [
            "Report spammers to #services on sight.",
            "Do NOT click any links they post.",
            "Set +R (registered-only join) or +M (registered-only talk) to prevent drive-by spam.",
        ],
    },

    # ---- FAQ: Troublemakers ----
    "trolls": {
        "title": "Dealing with Troublemakers",
        "aliases": ["trolls", "troll", "troublemaker", "troublemakers", "ignore"],
        "content": [
            "Ban them from the channel, or use /ignore *!*@their.host",
            "Don't engage — that's what they want.",
            "Block PMs from unknowns: /mode yourNick +g (strict) or +G (soft — blocks non-shared-channel users)",
            "Add someone to your accept list: /accept nick",
            "No need to report trolls to #help unless they break network rules.",
        ],
    },

    # ---- FAQ: Takeover ----
    "takeover": {
        "title": "Channel Takeover",
        "aliases": ["takeover", "channel takeover", "claim channel"],
        "content": [
            "If the founder is inactive for 30+ days, the successor (if set) can claim ownership.",
            "Read the Channel Takeover Policy for eligibility and instructions.",
            "Contact #services for assistance.",
        ],
    },

    # ---- FAQ: Remove modes ----
    "removemode": {
        "title": "Remove Channel Modes",
        "aliases": ["removemode", "remove mode", "unset mode", "-k", "-i"],
        "content": [
            "Remove a mode: /mode #channel -X  (where X is the mode letter)",
            "E.g. remove key: /mode #channel -k | remove invite-only: /mode #channel -i",
            "Reset ALL modes: /msg ChanServ CLEAR #channel MODES",
        ],
    },

    # ---- Webchat ----
    "webchat": {
        "title": "Rizon Webchat",
        "aliases": ["webchat", "qchat", "web chat"],
        "content": [
            "Webchat: https://qchat.rizon.net/",
            "SSL webchat available at the same URL.",
            "Embed webchat on your site: click the arrow button (top-left of qchat) > 'Add webchat to your site'.",
        ],
    },

    # ---- IP/Hostname ----
    "ip": {
        "title": "IP Address / Hostname Privacy",
        "aliases": ["ip", "hostname", "whois ip", "hide ip"],
        "content": [
            "Only you and Rizon staff can see your real IP in /whois.",
            "Rizon auto-cloaks hostnames on connect (+x user mode).",
            "For extra customization, request a vHost: $rhelp vhost",
        ],
    },

    # ---- Session/Connection Limits ----
    "session": {
        "title": "Session / Connection Limits",
        "aliases": ["session", "session limit", "connection limit", "clones"],
        "content": [
            "Rizon limits the number of connections from one IP.",
            "If you need more (e.g. running bots), request an exemption in #services.",
        ],
    },

    # ---- MemoServ ----
    "memo": {
        "title": "MemoServ",
        "aliases": ["memo", "memoserv", "memos"],
        "content": [
            "Send a memo: /msg MemoServ SEND nick message",
            "Read last memo: /msg MemoServ READ LAST",
            "List memos: /msg MemoServ LIST",
            "Delete a memo: /msg MemoServ DEL number",
            "Full help: /msg MemoServ HELP",
        ],
    },
}

# Build a lookup index: alias -> topic key
_LOOKUP = {}
for key, data in TOPICS.items():
    _LOOKUP[key] = key
    for alias in data["aliases"]:
        _LOOKUP[alias.lower()] = key

# Sorted unique topic keys for the list command
_TOPIC_LIST = sorted(TOPICS.keys())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@plugin.command("rhelp")
def cmd_rhelp(bot, trigger):
    """$rhelp [topic] — Look up a Rizon help topic. No args = list topics."""
    if not trigger.is_privmsg and not _enabled(bot, trigger):
        return bot.reply("Rizon help is not enabled in this channel. An op can enable it with $rizonhelpon")

    query = (trigger.group(2) or "").strip().lower()

    if not query:
        bot.reply(
            "Topics: " + ", ".join(_TOPIC_LIST)
            + " — Use $rhelp <topic> for details."
        )
        return

    topic_key = _LOOKUP.get(query)

    # Fuzzy fallback: check if query is a substring of any alias
    if not topic_key:
        for alias, key in _LOOKUP.items():
            if query in alias or alias in query:
                topic_key = key
                break

    if not topic_key:
        bot.reply("Unknown topic '%s'. Use $rhelp to see available topics." % query)
        return

    data = TOPICS[topic_key]
    bot.say("\x02%s\x02" % data["title"])
    for line in data["content"]:
        bot.say(line)
