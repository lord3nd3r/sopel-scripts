from sopel import plugin, config
import json
import re
import requests

YOUTUBE_RE = r'https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/\S*'
DB_KEY = 'youtube_titles_disabled'


def _is_disabled(bot, channel):
    """Check if YouTube titles are disabled for this channel."""
    try:
        val = bot.db.get_channel_value(channel, DB_KEY)
        return bool(val)
    except Exception:
        return False


@plugin.command('yt')
@plugin.example('$yt off', '$yt on')
@plugin.require_chanmsg('This command only works in channels.')
def yt_toggle(bot, trigger):
    """Toggle YouTube title fetching on or off for this channel. Requires op or owner."""
    nick = trigger.nick
    channel = trigger.sender

    # Check if the user is a channel op or the bot owner
    is_op = False
    try:
        privs = bot.channels[channel].privileges.get(nick, 0)
        # OP = 2 (halfop=1, op=2, admin=4, owner=8)
        is_op = privs >= 2
    except Exception:
        pass

    is_owner = (nick == bot.settings.core.owner)

    if not is_op and not is_owner:
        bot.say('You need to be a channel op to do that.')
        return

    arg = trigger.group(2)
    if not arg or arg.strip().lower() not in ('on', 'off'):
        # Show current status
        if _is_disabled(bot, channel):
            bot.say('YouTube titles are currently OFF for {}. Use $yt on to enable.'.format(channel))
        else:
            bot.say('YouTube titles are currently ON for {}. Use $yt off to disable.'.format(channel))
        return

    arg = arg.strip().lower()
    if arg == 'off':
        bot.db.set_channel_value(channel, DB_KEY, True)
        bot.say('YouTube titles disabled for {}.'.format(channel))
    elif arg == 'on':
        bot.db.set_channel_value(channel, DB_KEY, False)
        bot.say('YouTube titles enabled for {}.'.format(channel))


@plugin.url(YOUTUBE_RE)
def youtube_title(bot, trigger, match=None):
    # Check if disabled for this channel
    if trigger.sender and _is_disabled(bot, trigger.sender):
        return

    # ibot passes (bot, trigger); Sopel passes (bot, trigger, match)
    if match is not None:
        url = match.group(0)
    else:
        # search the full raw message for a YouTube URL
        raw = str(trigger.group(0)) if trigger.group(0) else ''
        m = re.search(YOUTUBE_RE, raw)
        if not m:
            return
        url = m.group(0)

    # Strip trailing punctuation that got caught by \S*
    url = re.sub(r'[>)\]\'\\"]+$', '', url)

    api = 'https://www.youtube.com/oembed?url={}&format=json'.format(url)

    try:
        resp = requests.get(api, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        obj = resp.json()
    except Exception:
        return

    title = obj.get('title')
    author = obj.get('author_name')

    if not title:
        return

    if author:
        bot.say('YouTube: {} — {}'.format(title, author))
    else:
        bot.say('YouTube: {}'.format(title))
