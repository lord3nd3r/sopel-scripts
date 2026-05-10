# 👁️ Seen — Last Seen Tracker

Tracks the last time a user spoke in a channel and reports it on demand.

---

## Commands

| Command | Description |
|---------|-------------|
| `$seen <nick>` | Report when `<nick>` was last seen and what they said |

---

## How It Works

- Every channel message and `/me` action is recorded per nick per channel.
- `$seen` checks the current channel first, then falls back to the most recent record across all channels.
- Data is stored in `~/.sopel/seen.db` (SQLite) and survives bot restarts.

---

## Examples

```
<End3r> $seen based
<devbox> based was last seen in #linux 2h 14m ago: hey whats up

<End3r> $seen glitchy
<devbox> glitchy was last seen in #linux 0s ago: * glitchy sets mode +v based
```

---

## Notes

- Asking about yourself or the bot returns a witty reply instead.
- Messages longer than 200 characters are truncated.
- `/me` actions are tracked and displayed as `* nick action`.
