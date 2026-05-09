# -*- coding: utf-8 -*-
"""
wolframalpha.py — Sopel plugin for Wolfram Alpha queries.

Commands: .wa  .calc  .math  .convert
Get a free API key at: https://developer.wolframalpha.com/
"""

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from sopel import plugin

LOG = logging.getLogger(__name__)

# ─── config ─────────────────────────────────────────────────────────
WA_API_KEY = 'YOUR_APPID_HERE'   # https://developer.wolframalpha.com/
# ────────────────────────────────────────────────────────────────────

API_URL   = 'http://api.wolframalpha.com/v2/query'
QUERY_URL = 'https://www.wolframalpha.com/input/?i={}'
MAX_LEN   = 300


@plugin.commands('wa', 'calc', 'math', 'convert', 'wolframalpha')
@plugin.example('.wa speed of light in mph')
@plugin.example('.calc 2^32')
@plugin.example('.convert 100 USD to EUR')
def wolframalpha(bot, trigger):
    """<query> — Look up anything on Wolfram Alpha."""
    query = (trigger.group(2) or '').strip()
    if not query:
        bot.reply('Usage: .wa <query>')
        return

    if WA_API_KEY == 'YOUR_APPID_HERE':
        bot.reply('Wolfram Alpha API key not configured.')
        return

    params = {
        'input': query,
        'appid': WA_API_KEY,
        'format': 'plaintext',
        'podstate': 'Step-by-step solution',
    }

    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        LOG.exception('wolframalpha: request error')
        bot.reply(f'Request failed: {e}')
        return

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        bot.reply('Failed to parse Wolfram Alpha response.')
        return

    if root.attrib.get('success') != 'true':
        # Check for suggestions
        suggestions = [d.attrib.get('val', '') for d in root.findall('.//didyoumean')]
        if suggestions:
            bot.reply(f'No results. Did you mean: {", ".join(suggestions[:3])}?')
        else:
            bot.reply('No results.')
        return

    pod_texts = []
    for pod in root.findall('.//pod[@primary="true"]'):
        if pod.attrib.get('id') == 'Input':
            continue
        title = pod.attrib.get('title', '')
        results = []
        for text in pod.findall('.//subpod/plaintext'):
            if text.text:
                val = text.text.strip().replace('\n', '; ')
                val = re.sub(r'\s+', ' ', val)
                if val:
                    results.append(val)
        if results:
            pod_texts.append(f'{title}: {", ".join(results)}')

    if not pod_texts:
        # Fall back to first non-input pod
        for pod in root.findall('.//pod'):
            if pod.attrib.get('id') in ('Input', 'InputInterpretation'):
                continue
            for text in pod.findall('.//subpod/plaintext'):
                if text.text and text.text.strip():
                    val = text.text.strip().replace('\n', '; ')
                    val = re.sub(r'\s+', ' ', val)
                    pod_texts.append(f'{pod.attrib.get("title", "Result")}: {val}')
                    break
            if pod_texts:
                break

    if not pod_texts:
        bot.reply('No results.')
        return

    result = ' — '.join(pod_texts)
    # strip stray backslash escapes
    result = re.sub(r'\\(.)', r'\1', result)
    if len(result) > MAX_LEN:
        result = result[:MAX_LEN].rstrip() + '…'

    url = QUERY_URL.format(urllib.parse.quote_plus(query))
    bot.say(f'{result}  \x02[\x02 {url} \x02]\x02')
