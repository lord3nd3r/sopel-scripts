# 🔑 PromoteMe (opme)

Promote yourself (or a target) to channel operator.

---

## Setup

**1. Place the script:**
```
~/.sopel/scripts/opme.py
```

**2. Add to your Sopel `.cfg` file (optional — all have defaults):**
```ini
[promoteme]
# Only allow admins to use the command (default: true)
require_admin = true

# Require the bot to have op before promoting (default: true)
require_bot_op = true

# IRC modes to apply (default: +o for operator)
modes = +o

# Allow in all channels or restrict to a list (default: true)
allow_in_all_channels = true

# Comma-separated list of allowed channels (only used if allow_in_all_channels = false)
allowed_channels = #channel1, #channel2

# Cooldown between uses per user in seconds (default: 60)
cooldown_seconds = 60

# Custom success message — {nick} and {channel} are replaced
success_message = Promoted {nick} to operator in {channel}.

# Make promotions temporary (default: false)
temporary_promotion = false

# Duration of temporary promotions in seconds (default: 300)
promotion_duration = 300
```

---

## Commands

| Command | Description |
|---------|-------------|
| `$promoteme [nick]` | Promote yourself (or target) to channel op |

> Requires bot to have op. Admin-only by default (configurable).

---

## Examples

**Promote yourself:**
```
<Admin> $promoteme
* Glitchy sets mode +o Admin
```

**Promote another user:**
```
<Admin> $promoteme Friend
* Glitchy sets mode +o Friend
```
