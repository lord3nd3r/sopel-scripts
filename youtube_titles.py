from sopel import plugin
from sopel.tools import web
import json
import re

YOUTUBE_RE = r'https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/\S*'

@plugin.url(YOUTUBE_RE)
def youtube_title(bot, trigger, match):
    url = match.group(0)

    # Build oEmbed request
    api = "https://www.youtube.com/oembed?url={}&format=json".format(url)

    try:
        data = web.get(api)
    except Exception:
        return  # Fail quietly

    try:
        obj = json.loads(data)
    except Exception:
        return

    title = obj.get("title")
    author = obj.get("author_name")

    if not title:
        return

    if author:
        bot.say("YouTube: {} — {}".format(title, author))
    else:
        bot.say("YouTube: {}".format(title))

