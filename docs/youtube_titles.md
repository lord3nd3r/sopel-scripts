# 🎬 YouTube Titles (youtube_titles)

No commands — fully automatic. The bot detects any YouTube URL posted in chat and replies with the video title and author.

---

## Setup

**No config needed.** Just drop the script in place and it works. No API key required — it scrapes the page metadata.

**1. Place the script:**
```
~/.sopel/scripts/youtube_titles.py
```

---

## Triggers

| Trigger | Description |
|---------|-------------|
| Any YouTube URL in chat | Bot replies with video title and author |

> Supports `youtube.com/watch?v=`, `youtu.be/`, and other YouTube URL formats.

---

## Examples

**Post a YouTube link:**
```
<User> check this out https://www.youtube.com/watch?v=dQw4w9WgXcQ
<Glitchy> 🎬 Rick Astley - Never Gonna Give You Up (by Rick Astley)
```

**Short URL:**
```
<User> https://youtu.be/dQw4w9WgXcQ
<Glitchy> 🎬 Rick Astley - Never Gonna Give You Up (by Rick Astley)
```
