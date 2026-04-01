# 🚔 Verbal Morality (curse)

Demolition Man-style Verbal Morality Statute. Disabled by default. When enabled, the bot issues fines for profanity with a randomized §X.X citation from the VMS.

---

## Setup

**No config needed.** Just drop the script in place. Fining is **off by default** per channel — use `$curse on` in a channel to enable it.

**1. Place the script:**
```
~/.sopel/scripts/curse.py
```

---

## Commands

| Command | Who | Description |
|---------|-----|-------------|
| `$curse on` | Halfop+ / Admin | Enable fining in this channel |
| `$curse off` | Halfop+ / Admin | Disable fining in this channel |
| `$curse` | Anyone | Check whether fining is enabled |

> The bot auto-monitors all messages when enabled; no command is needed to trigger a fine.

---

## Examples

**Enable verbal morality:**
```
<%Admin> $curse on
<Glitchy> 🚔 Verbal Morality Statute is now ACTIVE in #channel.
```

**Someone swears:**
```
<User> What the f***!
<Glitchy> 🚔 User, you have been fined 1 credit for violation of the Verbal Morality Statute §4.7.
```

**Check status:**
```
<User> $curse
<Glitchy> 🚔 Verbal Morality Statute is currently ACTIVE in #channel.
```

**Disable:**
```
<%Admin> $curse off
<Glitchy> 🚔 Verbal Morality Statute has been DEACTIVATED in #channel.
```
