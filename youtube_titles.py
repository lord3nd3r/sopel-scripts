from sopel import plugin
import json
import re
import requests

YOUTUBE_RE = r'https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/\S*'

@plugin.url(YOUTUBE_RE)
def youtube_title(bot, trigger, match=None):
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
    url = re.sub(r'[>)\]\'\"]+$', '', url)

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

