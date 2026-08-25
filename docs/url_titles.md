# 🔗 URL Title Fetcher (url_titles)

Automatic URL title fetching plugin for Sopel/ibot. When a user posts a URL in chat, the bot automatically fetches the webpage, parses the HTML, and displays its `<title>` tag. Channel ops and bot admins can enable or disable title fetching per channel.

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

## Commands

| Command | Who | Description |
|---------|-----|-------------|
| `$urltitle on` | Halfop+ / Admin | Enable automatic URL title fetching in this channel |
| `$urltitle off` | Halfop+ / Admin | Disable automatic URL title fetching in this channel |
| `$urltitle` | Anyone | Check whether URL title fetching is currently enabled |

* **Aliases:** `$urltitles`

---

## Permissions

* Setting changes (`$urltitle on` / `$urltitle off`) require **halfop or above** (`%`, `@`, `&`, `~`) in the channel, or **bot admin/owner** status.
* Settings are saved per-channel in the bot database and persist across bot restarts.

---

## Behavior

* **Automatic Triggers**: Enabled by default in public channels (starting with `#`). The bot automatically scans messages for URLs matching HTTP/HTTPS patterns.
* **Format**: The title is displayed in bold bracket formatting:
  ```
  [ Example Webpage Title Here ]
  ```
* **Exempted Domains**: Skips domains handled by other specialized plugins. By default, it ignores YouTube links (`youtube.com` and `youtu.be`), which are managed by the `youtube_titles` plugin.
* **Performance Limits**:
  * **Size Guard**: Streams the request and reads at most **64 KB** of data to prevent downloading huge files.
  * **Timeout**: Requests time out after **8 seconds** to prevent lagging bot threads.
  * **Length Limit**: Title strings are truncated to **200 characters** with an ellipsis (`…`).
  * **Content Type**: Only parses pages with a `Content-Type` header containing `text/html`.
