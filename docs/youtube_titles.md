# 🎬 YouTube Titles (youtube_titles)

No commands — fully automatic. The bot detects any YouTube URL posted in chat and replies with the video title and channel/author name.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/youtube_titles.py
```

**No API key required.** Uses the public YouTube oEmbed endpoint (`youtube.com/oembed`) to fetch metadata — no quotas, no authentication.

---

## Triggers

| Trigger | Description |
|---------|-------------|
| Any YouTube URL in chat | Bot replies with video title and author |

### Supported URL Formats

| Format | Example |
|--------|--------|
| Standard watch URL | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` |
| Short URL | `https://youtu.be/dQw4w9WgXcQ` |
| Embed URL | `https://www.youtube.com/embed/dQw4w9WgXcQ` |
| With subdomain | `https://m.youtube.com/watch?v=dQw4w9WgXcQ` |
| With extra params | `https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120` |

### Output Format

```
YouTube: Video Title — Channel Name
```

If the channel/author name is unavailable, only the title is shown:

```
YouTube: Video Title
```

> **Fail-silent:** If the oEmbed API call fails or the video is private/deleted, the bot simply doesn't respond — no error message is shown.
>
> **No cooldown.** Every YouTube link gets a response.

---

## Examples

**Standard YouTube link:**
```
<User> check this out https://www.youtube.com/watch?v=dQw4w9WgXcQ
<Glitchy> YouTube: Rick Astley - Never Gonna Give You Up — Rick Astley
```

**Short URL:**
```
<User> https://youtu.be/dQw4w9WgXcQ
<Glitchy> YouTube: Rick Astley - Never Gonna Give You Up — Rick Astley
```

**Link embedded in a sentence:**
```
<User> this song is stuck in my head https://www.youtube.com/watch?v=dQw4w9WgXcQ lol
<Glitchy> YouTube: Rick Astley - Never Gonna Give You Up — Rick Astley
```

**Mobile link:**
```
<User> https://m.youtube.com/watch?v=dQw4w9WgXcQ
<Glitchy> YouTube: Rick Astley - Never Gonna Give You Up — Rick Astley
```

**Private/deleted video (no response):**
```
<User> https://www.youtube.com/watch?v=DELETED123
(no response — video metadata not available)
```
