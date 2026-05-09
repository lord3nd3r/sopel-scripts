# 📬 Tell — Offline Messages

Leave messages for users who aren't currently active. When they next speak in any channel the bot is in, they receive a `NOTICE` for each pending message.

---

## Commands

| Command | Description |
|---------|-------------|
| `.tell <nick> <message>` | Leave a message for `<nick>` |
| `.showtells` | Retrieve your pending messages immediately (via NOTICE) |

> The command prefix is `.` (dot), not `$`.

---

## How It Works

1. Use `.tell <nick> <message>` in any channel.
2. The bot confirms: `I will tell <nick> that when they next speak.`
3. When `<nick>` next says anything in any channel, the bot sends them a `NOTICE`:
   ```
   [Tell from End3r in #linux on 2026-05-09 15:43 UTC]: hey, call me back!
   ```
4. Each message is delivered once and not repeated.

---

## Examples

**Leaving a message:**
```
<End3r> .tell based hey, you around later?
<devbox> End3r: I will tell based that when they next speak.
```

**Delivery when the target speaks:**
```
-devbox- [Tell from End3r in #linux on 2026-05-09 15:43 UTC]: hey, you around later?
```

**Checking your own pending messages:**
```
<based> .showtells
-devbox- [Tell from End3r in #linux on 2026-05-09 15:43 UTC]: hey, you around later?
-devbox- 1 message(s) delivered above.
```

---

## Notes

- You cannot leave a message for yourself or for the bot.
- Messages are stored in `~/.sopel/tell.db` (SQLite) and survive bot restarts.
- Delivery uses `NOTICE` so it doesn't clutter the channel.
