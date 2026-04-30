"""
wiki.py

A Sopel script that provides a `wiki` command to search Grokepedia first, then Wikipedia if not found.
"""
from sopel import plugin
import requests
import re
import urllib.parse

GROKEPEDIA_API = "https://grokepedia.org/api/v1/search"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "SopelWiki/1.0 (https://example.com; bot)"
}

@plugin.command('wiki')
@plugin.example('.wiki Turing test')
def wiki_search(bot, trigger):
    term = (trigger.group(2) or '').strip()
    if not term:
        bot.reply("Usage: .wiki <search term>")
        return

    grok_result = search_grokepedia(term)
    if grok_result:
        bot.say(f"[Grokepedia] {grok_result}")
        return

    wiki_result = search_wikipedia(term)
    if wiki_result:
        bot.say(wiki_result)
    else:
        bot.say("No results found on Grokepedia or Wikipedia.")


def search_grokepedia(term):
    try:
        resp = requests.get(GROKEPEDIA_API, params={"q": term}, timeout=8, headers=HEADERS)
        if resp.status_code == 200 and 'application/json' in resp.headers.get('content-type', ''):
            try:
                data = resp.json()
            except ValueError:
                data = None

            if isinstance(data, dict):
                if data.get('summary'):
                    return data['summary']
                if data.get('extract'):
                    return data['extract']
                if isinstance(data.get('results'), list) and data['results']:
                    first = data['results'][0]
                    if isinstance(first, dict):
                        return first.get('summary') or first.get('extract') or first.get('title')
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    return first.get('summary') or first.get('extract') or first.get('title')
    except requests.RequestException:
        pass

    # Grokepedia is currently a coming-soon site, so also try a direct page lookup.
    try:
        page_url = f"https://grokepedia.org/wiki/{urllib.parse.quote(term.replace(' ', '_'))}"
        resp = requests.get(page_url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            text = resp.text
            if 'Coming Soon' in text or 'grokepedia.org - Coming Soon' in text:
                return None
            match = re.search(r'<p>(.*?)</p>', text, re.S | re.I)
            if match:
                snippet = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                return snippet
    except requests.RequestException:
        pass

    return None


def wikipedia_page_url(title):
    return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


def get_wikipedia_extract(title):
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts|info",
        "inprop": "url",
        "exintro": True,
        "explaintext": True,
        "redirects": 1,
        "titles": title,
    }
    resp = requests.get(WIKIPEDIA_API, params=params, timeout=8, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if page.get("missing") or page.get("invalid"):
            continue
        title = page.get("title")
        extract = page.get("extract")
        if title and extract:
            return title, extract.strip().replace("\n", " ")
        if title:
            return title, None
    return None, None


def search_wikipedia(term):
    try:
        title, extract = get_wikipedia_extract(term)
        if title and extract:
            return f"[Wikipedia] {title}: {extract}"
        if title:
            return f"[Wikipedia] {title}: {wikipedia_page_url(title)}"

        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": term,
            "srlimit": 1,
            "srprop": "snippet",
        }
        resp = requests.get(WIKIPEDIA_API, params=search_params, timeout=8, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("query", {}).get("search", [])
        if hits:
            title = hits[0].get("title")
            if title:
                title, extract = get_wikipedia_extract(title)
                if title and extract:
                    return f"[Wikipedia] {title}: {extract}"
                return f"[Wikipedia] {title}: {wikipedia_page_url(title)}"
    except requests.RequestException:
        pass
    return None
