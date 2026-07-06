# botadmin.py — Owner-only bot management commands (supplements built-in admin)
# Commands here are unique to this plugin and DO NOT duplicate the built-in
# admin plugin's commands (bjoin, bpart, bmode, say, act, raw, bnick, bquit,
# rehash, reload, load, unload, plugins, bstatus, enable, disable, disabled).
from __future__ import annotations

import os
import sys
import subprocess
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
            admins = {a.strip().lower() for a in re.split(r'[,\\s]+', cfg_admins) if a.strip()}
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
# $restart — restart the bot process (clean restart)
# ------------------------------------------------------------------
@module.commands('restart')
def restart(bot, trigger):
    """$restart — Restart the bot (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    _pm_reply(bot, trigger, '🔄 Rehashing — restarting bot process...')
    LOG.info('REHASH requested by %s', trigger.nick)
    # Find the config file the bot is using
    cfg_name = None
    try:
        cfg_path = bot.config.filename
        if cfg_path:
            cfg_name = os.path.basename(cfg_path)
    except Exception:
        pass
    # Use subprocess to restart via sopel CLI so the daemon re-spawns
    sopel_bin = os.path.join(os.path.dirname(sys.executable), 'sopel')
    cmd = [sopel_bin, 'restart']
    if cfg_name:
        cmd += ['-c', cfg_name]
    try:
        subprocess.Popen(cmd, cwd=os.path.expanduser('~/.sopel'))
    except Exception:
        LOG.exception('rehash: subprocess failed, falling back to bot.restart()')
        try:
            bot.restart('Rehashing — be right back!')
        except Exception:
            bot.quit('Rehashing — be right back!')


# ------------------------------------------------------------------
# $breload <module> — reload a specific plugin
# ------------------------------------------------------------------
@module.commands('breload')
def reload_plugin(bot, trigger):
    """$breload <module> — Reload a specific plugin (owner only)."""
    if not _is_owner(bot, trigger):
        _deny(bot, trigger)
        return
    arg = (trigger.group(2) or '').strip()
    if not arg:
        _pm_reply(bot, trigger, '❓ Usage: $breload <module_name|all>')
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
        '  $restart — Restart the bot process (owner)',
        '  $rehash — Hot-reload config and all plugins (owner)',
        '  $breload <module|all> — Reload a plugin or all (owner)',
        '  $reload <module> — Reload a single plugin (owner)',
        '  $bquit [msg] — Shut down the bot (owner)',
        '  $say <target> <msg> — Say something (admin)',
        '  $act <target> <action> — /me action (admin)',
        '  $raw <irc line> — Raw IRC command (owner)',
        '  $bnick <nick> — Change bot nick (owner)',
        '  $bjoin #chan [key] — Join channel (admin)',
        '  $bpart #chan [msg] — Leave channel (admin)',
        '  $bmode #chan <mode> [nick] — Set mode (admin)',
        '  $enable <plugin> <#chan> — Enable plugin in channel (admin, PM only)',
        '  $disable <plugin> <#chan> — Disable plugin in channel (admin, PM only)',
        '  $disabled [#chan] — List disabled plugins (admin, PM only)',
        '  $bstatus — Show bot status info (admin)',
    ]
    for line in lines:
        if trigger.sender.startswith('#'):
            bot.notice(line, trigger.nick)
        else:
            bot.say(line, trigger.nick)
