# 🛡️ JPQ Flood Protection (jpq)

Join/Part/Quit Cycle Flood Protection for Sopel. It detects and bans users who cycle joins, parts, or quits in channels to flood the chat or server logs.

---

## Setup

**1. Place the script:**
```
~/.sopel/scripts/jpq.py
```

**2. Configure `sopel.cfg` (Optional):**
Default settings can be defined in the `[jpq]` section:
```ini
[jpq]
window = 30             # Time window in seconds to track cycling events (default: 30)
threshold = 5           # Number of events within the window to trigger ban (default: 5)
ban_duration = 300      # Auto-unban delay in seconds; 0 = permanent (default: 300)
banmask_style = host    # 'host' (*!*@host) or 'ident' (*!user@host) (default: host)
exempt_modes = vho      # Channel mode chars exempt from bans (v=voice, h=halfop, o=op)
enabled = true          # Global enable/disable switch (default: true)
```

**Note:** Unlike `antiflood`, JPQ is **enabled by default in all channels**. Channels must be explicitly disabled using the `$jpq off` command if desired.

---

## Commands

All commands require **bot admin** privileges.

| Command | Subcommands / Args | Description | Example |
|---------|-------------------|-------------|---------|
| `$jpq` | — | Show JPQ status & parameters for the current channel | `$jpq` |
| `$jpq` | `on` / `off` | Enable/disable JPQ in the current channel | `$jpq off` |
| `$jpq` | `set <param> <val>` | Adjust runtime parameters (`window`, `threshold`, `duration`, `banmask`) | `$jpq set duration 600` |
| `$jpq` | `whitelist list` | Show whitelisted hostmasks | `$jpq whitelist list` |
| `$jpq` | `whitelist add <user@host>` | Exempt a hostmask from JPQ detection | `$jpq whitelist add *!*@trusted-user.org` |
| `$jpq` | `whitelist del <user@host>` | Remove a hostmask exemption | `$jpq whitelist del *!*@trusted-user.org` |
| `$jpq` | `stats` | Show recent JPQ ban actions in this channel | `$jpq stats` |
| `$jpq` | `help` | Send a command reference guide via NOTICE | `$jpq help` |

---

## Behavior

* **Tracking**: The plugin tracks `JOIN`, `PART`, and `QUIT` events. Since `QUIT` is server-wide, the plugin maintains an in-memory channel membership map to determine which channels the quitting user was in.
* **Triggering**: If a user's combined event count meets or exceeds the `threshold` within the `window`, they are kicked and banned.
* **Exemptions**: Users with configured exempt channel modes (default: `+v`, `+h`, `+o`) or who are whitelisted are bypassed.
* **Grace Period**: After a bot-initiated kick, a 60-second grace period applies to the hostmask to prevent event loops.
* **Auto-Unban**: Banned users are automatically unbanned after `ban_duration` seconds (if duration > 0) via a background timer.
