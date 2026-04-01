# 🚪 Join (join)

Make the bot join a channel. Owner only.

---

## Setup

**No config needed** beyond Sopel's built-in `owner` setting.

**1. Place the script:**
```
~/.sopel/scripts/join.py
```

**2. Make sure your `.cfg` has an owner defined:**
```ini
[core]
owner = YourNick
```

> Only the configured `owner` can use this command.

---

## Commands

| Command | Who | Description |
|---------|-----|-------------|
| `$join #channel [key]` | Owner only | Make the bot join a channel |

---

## Examples

**Join a channel:**
```
/msg Glitchy $join #newchannel
```

**Join a channel with a key:**
```
/msg Glitchy $join #secretchannel mypassword
```
