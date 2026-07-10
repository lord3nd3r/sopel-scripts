# 🔗 URL Title Fetcher (url_titles)

Automatic URL title fetching plugin for Sopel. When a user posts a URL in chat, the bot automatically fetches the webpage, parses the HTML, and displays its `<title>` tag.

---

## Setup

**1. Place the script:**
```
~/.sopel/scripts/url_titles.py
```

**2. Dependencies:**
* `requests`
* `beautifulsoup4` (BeautifulSoup)

---

## Behavior

* **Automatic Triggers**: There is no command prefix required. The bot automatically scans all messages in public channels (nicks/channels starting with `#`) for URLs matching the standard HTTP/HTTPS patterns.
* **Format**: The title is displayed in bold bracket formatting:
  ```
  [ Example Webpage Title Here ]
  ```
* **Exempted Domains**: Skip domains handled by other specialized plugins. By default, it ignores YouTube links (`youtube.com` and `youtu.be`), which are managed by the `youtube_titles` plugin.
* **Performance Limits**:
  * **Size Guard**: The bot streams the request and reads at most **64 KB** of data. This ensures it doesn't download huge files (like ISOs or large images).
  * **Timeout**: Requests time out after **8 seconds** to prevent lagging the bot's threads.
  * **Length Limit**: Title strings are truncated to **200 characters** with an ellipsis (`…`) if they exceed the limit.
  * **Content Type**: The bot only parses pages with a `Content-Type` header containing `text/html`.
