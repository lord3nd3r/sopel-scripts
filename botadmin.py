# botadmin.py — Owner/admin-only bot management commands
# Works in PM and in channels. All commands require bot owner or admin.
from __future__ import annotations

import os
import sys
import signal
import logging

from sopel import module

LOG = logging.getLogger(__name__)

# Owner nicks (lowercase) — hardcoded fallback if config parsing fails
OWNER_NICKS = {'end3r'}


def _is_owner(bot, trigger):
    """Check if the trigger nick is the bot owner."""
    nick = trigger.nick.lower()
    if nick in OWNER_NICKS:
        return True
    try:
        cfg_owner = bot.config.core.owner
        if isinstance(cfg_owner, (list, tuple, set)):
            if nick in {o.lower() for o in cfg_owner}:
                return True
        elif cfg_owner and nick == str(cfg_owner).lower():
            return True
    except Exception:
        pass
    return getattr(trigger, 'owner', False)


def _is_admin(bot, trigger):
    """Check if the trigger nick is an admin (or owner)."""
    if _is_owner(bot, trigger):
        return True
    if getattr(trigger, 'admin', False):
        return True
    try:
        cfg_admins = getattr(bot.config.core, 'admins', None)
        if isinstance(cfg_admins, (list, tuple, set)):
            return trigger.nick.lower() in {a.lower() for a in cfg_admins}
        if isinstance(cfg_admins, str) and cfg_admins.strip():
            import re
            admins = {a.strip().lower() for a in re.split(r'[,\s]+', cfg_admins) if a.strip()}
            return trigger.nick.lower() in admins
    except Exception:
        pass
    return False


def _deny(bot, trigger):
    bot.reply('⛔ You are not authorized to use this command.')


def _pm_reply(bot, trigger, msg):
    """Reply to PM or channel appropriately."""
    if trigger.sender.startswith('#'):
        bot.say(msg, trigger.sender)
    else:
        bot.say(msg, trigger.nick)


# ------------------------------------------------------------------
# $rehash — restart the bot process (clean restart)
# ------------------------------------------------------------------
@module.commands('rehash')
def rehash(bot, trigger):
    """$rehash — Restart the bot (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    _pm_reply(bot, trigger, '🔄 Rehashing — restarting bot process...')
    LOG.info('REHASH requested by %s', trigger.nick)
    try:
        bot.quit('Rehashing — be right back!')
    except Exception:
        pass
    # Re-exec the same process
    os.execvp(sys.executable, [sys.executable] + sys.argv)


# ------------------------------------------------------------------
# $reload <module> — reload a specific plugin
# ------------------------------------------------------------------
@module.commands('reload')
def reload_plugin(bot, trigger):
    """$reload <module> — Reload a specific plugin (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    arg = (trigger.group(2) or '').strip()
    if not arg:
        _pm_reply(bot, trigger, '❓ Usage: $reload <module_name|all>')
        return
    if arg.lower() == 'all':
        # Reload every loaded plugin
        if hasattr(bot, 'reload_plugins'):
            try:
                bot.reload_plugins()
                _pm_reply(bot, trigger, '✅ All plugins reloaded.')
            except Exception as e:
                _pm_reply(bot, trigger, f'❌ Failed to reload all: {e}')
                LOG.exception('Failed to reload all plugins')
        elif hasattr(bot, 'reload_plugin'):
            loaded = list(getattr(bot, '_plugins', {}).keys()) or []
            if not loaded:
                try:
                    loaded = list(bot.backend._modules.keys())
                except Exception:
                    loaded = []
            if not loaded:
                _pm_reply(bot, trigger, '⚠️ Cannot enumerate plugins. Use $rehash instead.')
                return
            ok, fail = 0, 0
            for name in loaded:
                try:
                    bot.reload_plugin(name)
                    ok += 1
                except Exception:
                    fail += 1
                    LOG.exception('Failed to reload plugin %s', name)
            _pm_reply(bot, trigger, f'✅ Reloaded {ok} plugins. {f"❌ {fail} failed." if fail else ""}')
        else:
            _pm_reply(bot, trigger, '⚠️ This Sopel version does not support live reload. Use $rehash instead.')
        return
    try:
        # Sopel 8 reload API
        if hasattr(bot, 'reload_plugin'):
            bot.reload_plugin(arg)
            _pm_reply(bot, trigger, f'✅ Reloaded plugin: {arg}')
        elif hasattr(bot, 'reload_module'):
            bot.reload_module(arg)
            _pm_reply(bot, trigger, f'✅ Reloaded module: {arg}')
        else:
            _pm_reply(bot, trigger, '⚠️ This Sopel version does not support live reload. Use $rehash instead.')
    except Exception as e:
        _pm_reply(bot, trigger, f'❌ Failed to reload {arg}: {e}')
        LOG.exception('Failed to reload plugin %s', arg)


# ------------------------------------------------------------------
# $botquit [message] — shut down the bot
# ------------------------------------------------------------------
@module.commands('botquit')
def botquit(bot, trigger):
    """$botquit [message] — Shut down the bot (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    msg = (trigger.group(2) or '').strip() or 'Shutting down — goodbye!'
    LOG.info('QUIT requested by %s: %s', trigger.nick, msg)
    try:
        bot.quit(msg)
    except Exception:
        pass


# ------------------------------------------------------------------
# $say <#channel|nick> <message> — make the bot say something
# ------------------------------------------------------------------
@module.commands('say')
def say_cmd(bot, trigger):
    """$say <#channel|nick> <message> — Send a message as the bot (admin only)."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    args = (trigger.group(2) or '').strip()
    if not args or ' ' not in args:
        _pm_reply(bot, trigger, '❓ Usage: $say <#channel|nick> <message>')
        return
    target, message = args.split(' ', 1)
    bot.say(message.strip(), target.strip())


# ------------------------------------------------------------------
# $act <#channel|nick> <action> — make the bot do /me
# ------------------------------------------------------------------
@module.commands('act')
def act_cmd(bot, trigger):
    """$act <#channel|nick> <action> — Send an action as the bot (admin only)."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    args = (trigger.group(2) or '').strip()
    if not args or ' ' not in args:
        _pm_reply(bot, trigger, '❓ Usage: $act <#channel|nick> <action>')
        return
    target, action = args.split(' ', 1)
    bot.action(action.strip(), target.strip())


# ------------------------------------------------------------------
# $raw <irc command> — send a raw IRC line
# ------------------------------------------------------------------
@module.commands('raw')
def raw_cmd(bot, trigger):
    """$raw <irc line> — Send raw IRC command (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    line = (trigger.group(2) or '').strip()
    if not line:
        _pm_reply(bot, trigger, '❓ Usage: $raw <irc command>')
        return
    LOG.info('RAW from %s: %s', trigger.nick, line)
    bot.write([line])
    _pm_reply(bot, trigger, f'📡 Sent: {line}')


# ------------------------------------------------------------------
# $botnick <newnick> — change bot's nick
# ------------------------------------------------------------------
@module.commands('botnick')
def botnick(bot, trigger):
    """$botnick <newnick> — Change the bot's IRC nick (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    newnick = (trigger.group(2) or '').strip()
    if not newnick:
        _pm_reply(bot, trigger, '❓ Usage: $botnick <newnick>')
        return
    LOG.info('NICK change requested by %s: %s -> %s', trigger.nick, bot.nick, newnick)
    bot.write(['NICK', newnick])
    _pm_reply(bot, trigger, f'✅ Nick change sent: {bot.nick} → {newnick}')


# ------------------------------------------------------------------
# $bjoin <#channel> [key] — join a channel
# ------------------------------------------------------------------
@module.commands('bjoin')
def bjoin(bot, trigger):
    """$bjoin <#channel> [key] — Make the bot join a channel (admin only)."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    args = (trigger.group(2) or '').strip().split()
    if not args or not args[0].startswith('#'):
        _pm_reply(bot, trigger, '❓ Usage: $bjoin #channel [key]')
        return
    channel = args[0]
    key = args[1] if len(args) > 1 else None
    bot.join(channel, key)
    _pm_reply(bot, trigger, f'✅ Joining {channel}')


# ------------------------------------------------------------------
# $bpart <#channel> [message] — leave a channel
# ------------------------------------------------------------------
@module.commands('bpart')
def bpart(bot, trigger):
    """$bpart <#channel> [message] — Make the bot leave a channel (admin only)."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    args = (trigger.group(2) or '').strip()
    if not args:
        _pm_reply(bot, trigger, '❓ Usage: $bpart #channel [message]')
        return
    parts = args.split(' ', 1)
    channel = parts[0]
    if not channel.startswith('#'):
        _pm_reply(bot, trigger, '❓ Usage: $bpart #channel [message]')
        return
    msg = parts[1].strip() if len(parts) > 1 else ''
    bot.part(channel, msg or None)
    _pm_reply(bot, trigger, f'✅ Parting {channel}')


# ------------------------------------------------------------------
# $bmode <#channel> <mode> [target] — set a channel mode
# ------------------------------------------------------------------
@module.commands('bmode')
def bmode(bot, trigger):
    """$bmode <#channel> <mode> [target] — Set channel mode (admin only)."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    args = (trigger.group(2) or '').strip().split()
    if len(args) < 2:
        _pm_reply(bot, trigger, '❓ Usage: $bmode #channel +o Nick')
        return
    channel = args[0]
    mode = args[1]
    target = args[2] if len(args) > 2 else None
    if target:
        bot.write(['MODE', channel, mode, target])
    else:
        bot.write(['MODE', channel, mode])
    _pm_reply(bot, trigger, f'✅ MODE {channel} {mode} {target or ""}')


# ------------------------------------------------------------------
# $bothelp — list available admin commands
# ------------------------------------------------------------------
@module.commands('bothelp')
def bothelp(bot, trigger):
    """$bothelp — List admin bot commands."""
    if not _is_admin(bot, trigger):
        _deny(bot, trigger)
        return
    lines = [
        '🛠️ Bot Admin Commands:',
        '  $rehash — Restart the bot (owner)',
        '  $reload <module|all> — Reload a plugin or all (owner)',
        '  $botquit [msg] — Shut down the bot (owner)',
        '  $say <target> <msg> — Say something (admin)',
        '  $act <target> <action> — /me action (admin)',
        '  $raw <irc line> — Raw IRC command (owner)',
        '  $botnick <nick> — Change bot nick (owner)',
        '  $bjoin #chan [key] — Join channel (admin)',
        '  $bpart #chan [msg] — Leave channel (admin)',
        '  $bmode #chan <mode> [nick] — Set mode (admin)',
    ]
    for line in lines:
        if trigger.sender.startswith('#'):
            bot.notice(line, trigger.nick)
        else:
            bot.say(line, trigger.nick)
