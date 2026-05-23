"""
autoop.py - Sopel Auto-Op / Auto-Voice Plugin
Adds users to an auto-mode list so they are granted +o, +h, or +v on join.
"""

from sopel import module
import logging

LOG = logging.getLogger(__name__)

def _get_data(bot):
    """Retrieve the autoop data from the bot's database."""
    data = bot.db.get_plugin_value('autoop', 'data')
    if not isinstance(data, dict):
        data = {}
    return data

def _save_data(bot, data):
    """Save the autoop data to the bot's database."""
    bot.db.set_plugin_value('autoop', 'data', data)

def _set_mode(bot, channel, nick, mode):
    data = _get_data(bot)
    if channel not in data:
        data[channel] = {}
    data[channel][nick.lower()] = mode
    _save_data(bot, data)

def _del_mode(bot, channel, nick, expected_mode=None):
    data = _get_data(bot)
    channel = channel.lower()
    nick_lower = nick.lower()
    
    if channel in data and nick_lower in data[channel]:
        current_mode = data[channel][nick_lower]
        if expected_mode and current_mode != expected_mode:
            return False, current_mode
        del data[channel][nick_lower]
        _save_data(bot, data)
        return True, current_mode
    return False, None

# --- Auto-Op ---

@module.require_admin
@module.commands('aop')
def cmd_aop(bot, trigger):
    """$aop <nick> - Add a user to the auto-op (+o) list for this channel."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $aop <nick>")
    
    _set_mode(bot, trigger.sender.lower(), nick.strip(), 'o')
    bot.reply(f"✅ Added \x02{nick.strip()}\x02 to the auto-op (+o) list for {trigger.sender}.")

@module.require_admin
@module.commands('dop')
def cmd_dop(bot, trigger):
    """$dop <nick> - Remove a user from the auto-op list."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $dop <nick>")
    
    success, current = _del_mode(bot, trigger.sender.lower(), nick.strip(), expected_mode='o')
    if success:
        bot.reply(f"✅ Removed \x02{nick.strip()}\x02 from the auto-op list.")
    elif current:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is in the list, but for +{current}, not +o. Use $dvoice or $dhop instead.")
    else:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is not in the auto-mode list.")

# --- Auto-HalfOp ---

@module.require_admin
@module.commands('ahop')
def cmd_ahop(bot, trigger):
    """$ahop <nick> - Add a user to the auto-halfop (+h) list for this channel."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $ahop <nick>")
    
    _set_mode(bot, trigger.sender.lower(), nick.strip(), 'h')
    bot.reply(f"✅ Added \x02{nick.strip()}\x02 to the auto-halfop (+h) list for {trigger.sender}.")

@module.require_admin
@module.commands('dhop')
def cmd_dhop(bot, trigger):
    """$dhop <nick> - Remove a user from the auto-halfop list."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $dhop <nick>")
    
    success, current = _del_mode(bot, trigger.sender.lower(), nick.strip(), expected_mode='h')
    if success:
        bot.reply(f"✅ Removed \x02{nick.strip()}\x02 from the auto-halfop list.")
    elif current:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is in the list, but for +{current}, not +h.")
    else:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is not in the auto-mode list.")

# --- Auto-Voice ---

@module.require_admin
@module.commands('avoice')
def cmd_avoice(bot, trigger):
    """$avoice <nick> - Add a user to the auto-voice (+v) list for this channel."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $avoice <nick>")
    
    _set_mode(bot, trigger.sender.lower(), nick.strip(), 'v')
    bot.reply(f"✅ Added \x02{nick.strip()}\x02 to the auto-voice (+v) list for {trigger.sender}.")

@module.require_admin
@module.commands('dvoice')
def cmd_dvoice(bot, trigger):
    """$dvoice <nick> - Remove a user from the auto-voice list."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    nick = trigger.group(2)
    if not nick:
        return bot.reply("Usage: $dvoice <nick>")
    
    success, current = _del_mode(bot, trigger.sender.lower(), nick.strip(), expected_mode='v')
    if success:
        bot.reply(f"✅ Removed \x02{nick.strip()}\x02 from the auto-voice list.")
    elif current:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is in the list, but for +{current}, not +v.")
    else:
        bot.reply(f"⚠️ \x02{nick.strip()}\x02 is not in the auto-mode list.")

# --- List Commands ---

@module.require_admin
@module.commands('alist')
def cmd_alist(bot, trigger):
    """$alist - List all auto-modes for the current channel."""
    if not trigger.sender.startswith('#'):
        return bot.reply("This command must be used in a channel.")
    
    channel = trigger.sender.lower()
    data = _get_data(bot)
    chan_data = data.get(channel, {})
    
    if not chan_data:
        return bot.reply(f"No auto-modes set for {trigger.sender}.")
    
    ops = []
    hops = []
    voices = []
    
    for nick, mode in chan_data.items():
        if mode == 'o': ops.append(nick)
        elif mode == 'h': hops.append(nick)
        elif mode == 'v': voices.append(nick)
    
    lines = []
    if ops: lines.append(f"+o: {', '.join(ops)}")
    if hops: lines.append(f"+h: {', '.join(hops)}")
    if voices: lines.append(f"+v: {', '.join(voices)}")
    
    bot.reply(f"Auto-modes for {trigger.sender} | " + " | ".join(lines))


# --- Event Handler ---

@module.event('JOIN')
@module.rule('.*')
def on_join(bot, trigger):
    """Automatically apply modes when a registered user joins."""
    if not trigger.sender or not trigger.sender.startswith('#'):
        return
        
    channel = trigger.sender
    nick = trigger.nick
    
    # Don't try to op the bot itself
    if nick.lower() == bot.nick.lower():
        return
        
    data = _get_data(bot)
    chan_data = data.get(channel.lower(), {})
    
    mode = chan_data.get(nick.lower())
    if not mode:
        return
        
    # The bot must have the appropriate privileges to give modes,
    # but we just send the MODE command and let the IRC server handle rejection if the bot isn't opped.
    bot.write(['MODE', channel, f'+{mode}', nick])
    LOG.info(f"Auto-mode +{mode} applied to {nick} in {channel}")
