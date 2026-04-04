# 🤦 Facepalm (facepalm)

Auto-trigger: when someone does `/me facepalms`, `/me facepalmed`, or `/me facepalm`, the bot replies with a random facepalm reaction from a pool of 15 responses.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/facepalm.py
```

**No data storage** — cooldowns are tracked in memory only.

---

## Triggers

| Trigger | Description |
|---------|-------------|
| `/me facepalm` | Triggers a random bot reaction |
| `/me facepalms` | Triggers a random bot reaction |
| `/me facepalmed` | Triggers a random bot reaction |

> Only responds to `/me` ACTION messages — typing "facepalm" in regular text does nothing.
>
> **Channel cooldown:** 15 seconds (shared across all users in the channel). If on cooldown, the bot simply stays silent.
>
> **Channel only** — does not trigger in private messages.

---

## Response Pool

The bot picks a random response from 15 templates. Each reply is sent as an ACTION message (`/me`). Some sample responses:

```
* Glitchy watches User's facepalm echo across the universe 🌌🤦
* Glitchy notes User's facepalm for the record 📋🤦
* Glitchy gives User a sympathetic facepalm 🤝🤦
* Glitchy slow-claps User's facepalm 👏🤦
* Glitchy frames User's facepalm and hangs it on the wall 🖼️🤦
```

---

## Examples

**Facepalm in action:**
```
* User facepalms
* Glitchy watches User's facepalm echo across the universe 🌌🤦
```

**Different response each time:**
```
* User facepalmed
* Glitchy slow-claps User's facepalm 👏🤦
```

**Another:**
```
* User facepalms
* Glitchy gives User a sympathetic facepalm 🤝🤦
```

**On cooldown (no response):**
```
* User facepalms
(15 seconds haven't passed since the last facepalm — bot stays silent)
```

**Regular text — no trigger:**
```
<User> I just facepalmed so hard
(no response — only /me actions trigger the bot)
```
