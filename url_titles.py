# -*- coding: utf-8 -*-
"""
url_titles.py — Fetch and display the <title> of URLs posted in chat.

Ignores YouTube links (handled by youtube_titles.py).
"""

import logging
import re

import requests
from bs4 import BeautifulSoup
from sopel import plugin

LOG = logging.getLogger(__name__)

URL_RE = r'https?://[^\s>)"\']+'

# Domains handled by other plugins — skip them
SKIP_DOMAINS = re.compile(
    r'(?:youtube\.com|youtu\.be)',
    re.IGNORECASE
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}
MAX_BYTES  = 65_536   # read at most 64 KB to find the title
TIMEOUT    = 8
MAX_TITLE  = 200


@plugin.rule('.*')
@plugin.priority('low')
@plugin.thread(True)
def url_title(bot, trigger):
    if not trigger.sender or not str(trigger.sender).startswith('#'):
        return

    raw = str(trigger.group(0) or '')
    m = re.search(URL_RE, raw)
    if not m:
        return
    url = re.sub(r'[>)\]\'\".,!?]+$', '', m.group(0))

    if SKIP_DOMAINS.search(url):
        return

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return

        raw_html = b''
        for chunk in resp.iter_content(chunk_size=4096):
            raw_html += chunk
            if len(raw_html) >= MAX_BYTES:
                break

        encoding = resp.apparent_encoding or 'utf-8'
        html = raw_html.decode(encoding, errors='replace')

    except Exception:
        return

    try:
        soup = BeautifulSoup(html, 'html.parser')
        tag = soup.find('title')
        if not tag or not tag.string:
            return
        title = ' '.join(tag.string.strip().split())
    except Exception:
        return

    if not title:
        return

    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip() + '…'

    bot.say(f'\x02[\x02 {title} \x02]\x02')
