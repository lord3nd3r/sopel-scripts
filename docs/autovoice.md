# 🎙️ Auto Voice (autovoice)

Activity-based auto-voicer. Tracks chat activity per user and automatically grants `+v` to active chatters. Removes voice from users who go idle. **Off by default** — must be enabled per-channel.

---

## Setup

**1. Place the script:**
```
~/.sopel/scripts/autovoice.py
```

**2. The bot needs halfop (`%`) or higher** in each channel where autovoice is enabled.

**No config file section needed.** All data is stored in `~/.sopel/autovoice_data.json`, created automatically on first use.

---

## How It Works

1. Every channel message is counted per user per channel (only in enabled channels).
2. Once a user reaches **50 messages**, they automatically receive `+v`.
3. A background thread sweeps every **15 minutes** to:
   - Voice any users who crossed the threshold since the last check.
   - **Devoice** users who haven't spoken in **7 days**.
   - Clean up stale data entries (users idle for 14+ days are pruned from the data file).
4. Users who **already have a mode** (`+v`, `+h`, `+o`, `+a`, `+q`) are **completely ignored** — the plugin never touches them.
5. If the bot loses halfop, it simply stops making changes until it gets the privilege back.

---

## Commands

| Command | Description |
|---------|-------------|
| `$autovoice on` | Enable autovoice for this channel |
| `$autovoice off` | Disable autovoice for this channel |
| `$autovoice status` | Show on/off state, tracked user count, and threshold info |
| `$autovoice reset <nick>` | Clear a specific user's message count and activity data |
| `$autovoice threshold` | Display current message threshold and idle timeout |

> **Permission:** All commands require **halfop+** or **bot admin**.

---

## Examples

**Enable in a channel:**
```
<%Admin> $autovoice on
<Glitchy> Autovoice enabled for this channel.
```

**Check status:**
```
<User> $autovoice status
<Glitchy> Autovoice is ON | Tracking 23 users | Threshold: 50 msgs | Idle timeout: 7d
```

**Reset a user's data:**
```
<%Admin> $autovoice reset someuser
<Glitchy> Reset activity data for someuser.
```

---

## Tunables

These constants are at the top of `autovoice.py` and can be adjusted:

| Constant | Default | Description |
|----------|---------|-------------|
| `MSG_THRESHOLD` | `50` | Messages needed to earn `+v` |
| `IDLE_SECONDS` | `604800` (7 days) | Idle time before voice is removed |
| `SWEEP_INTERVAL` | `900` (15 min) | How often the background sweep runs |

---

## Ignored Users

The plugin **never** changes modes for users who already have any privilege:
- `+v` (voice) — already voiced, nothing to do
- `+h` (halfop) — higher than voice, left alone
- `+o` (op) — left alone
- `+a` (admin) — left alone
- `+q` (owner) — left alone

This means ChanServ-assigned modes, access list modes, and manually-set modes are always respected.

---

## Data File

`~/.sopel/autovoice_data.json` stores:
- **Per-channel enabled/disabled state**
- **Per-user per-channel message counts and last-seen timestamps**

The file is updated periodically and on plugin shutdown. Stale entries are automatically pruned.
