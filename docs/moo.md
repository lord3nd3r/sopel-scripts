# 🐄 Moo Counter (moo)

Say `moo` in chat to increment your counter. Full network leaderboards.

---

## Setup

**1. Install dependencies:**
```bash
pip install sqlalchemy
```
(Usually already installed with Sopel.)

**2. Place the script:**
```
~/.sopel/scripts/moo.py
```

**3. Add to your Sopel `.cfg` file (optional — all have defaults):**
```ini
[moo]
# Cooldown between moos in seconds (default: 6)
moo_cooldown = 6

# Cooldown for sudo moo in seconds (default: 3600 = 1 hour)
sudo_cooldown = 3600

# Chance of a legendary moo, 0.0 to 1.0 (default: 0.02 = 2%)
legendary_chance = 0.02

# Chance of a big loss on sudo moo, 0.0 to 1.0 (default: 0.005)
sudo_big_loss_chance = 0.005

# Enable/disable 1337-speak moo effects (default: true)
leet_moo = true
```

**Data storage:** Moo counts are stored in Sopel's built-in `bot.db` via SQLAlchemy — no extra database setup needed.

---

## Auto-Triggers

| Trigger | Effect |
|---------|--------|
| `moo` (anywhere in message) | +1 moo |
| `/me moos` | +1 moo (no cooldown) |
| `sudo moo` | +10 moos (1/hour/user/channel) |

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$moocount` | `$mymoo` | Your moo count |
| `$mootop` | `$topmoo` | Global moo leaderboard |
| `$mootopchan` | `$chanmootop`, `$topmoochan` | Per-channel leaderboard |
| `$totalmoo` | `$moostats` | Global and channel totals |
| `$moohelp` | `$aboutmoo` | Help (PM) |
| `$mooreset` | — | Reset a user's moos (admin only) |

---

## Examples

**Say moo in chat:**
```
<User> moo
<Glitchy> 🐄 User: moo #42!
```

**Emote moo:**
```
* User moos
<Glitchy> 🐄 User: moo #43!
```

**Sudo moo (10 at once, 1/hour):**
```
<User> sudo moo
<Glitchy> 🐄 User: +10 moos! Total: 53
```

**Check your count:**
```
<User> $moocount
<Glitchy> 🐄 User has mooed 53 times!
```

**Global leaderboard:**
```
<User> $mootop
<Glitchy> 🐄 Top Mooers: 1. CowFan (1,204) 2. MooLord (980) 3. User (53) ...
```

**Channel leaderboard:**
```
<User> $mootopchan
<Glitchy> 🐄 #channel Top: 1. CowFan (450) 2. MooLord (320) 3. User (53)
```

**Total stats:**
```
<User> $totalmoo
<Glitchy> 🐄 Global moos: 15,302 | #channel moos: 3,841
```

**Admin — reset a user:**
```
/msg Glitchy $mooreset SpamMooer
```
