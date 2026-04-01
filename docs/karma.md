# ⭐ Karma (karma)

Inline `++` / `--` karma system with per-channel and global tracking.

---

## Inline Usage

| Syntax | Effect |
|--------|--------|
| `nick++` | Give +1 karma |
| `nick--` | Give -1 karma |
| `nick==` | Check a nick's karma inline |

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$karma <nick>` | — | Channel + global karma for a user |
| `$karmatop [N]` | `$ktop` | Top N users globally (default 5) |
| `$karmabottom [N]` | `$kbottom` | Bottom N users globally |
| `$channeltop [N]` | `$ctop` | Top N in this channel (default 10) |
| `$channelbottom [N]` | `$cbottom` | Bottom N in this channel |
| `$setkarma <nick> <value>` | — | Set karma (channel ops only) |

---

## Cooldowns

- **10 minutes** per user per channel between karma changes

---

## Examples

**Give karma:**
```
<User> Friend++
<Glitchy> ⭐ Friend's karma is now 15 (#channel) / 42 (global)
```

**Remove karma:**
```
<User> Troll--
<Glitchy> ⭐ Troll's karma is now -3 (#channel) / -8 (global)
```

**Quick check with ==:**
```
<User> Friend==
<Glitchy> ⭐ Friend: 15 (#channel) / 42 (global)
```

**Detailed check:**
```
<User> $karma Friend
<Glitchy> ⭐ Friend — #channel: 15 | Global: 42
```

**Global leaderboard:**
```
<User> $karmatop
<Glitchy> ⭐ Top 5 Karma: 1. Helper (120) 2. Friend (42) 3. Guru (38) 4. Sage (25) 5. Mentor (19)
```

**Bottom karma:**
```
<User> $karmabottom 3
<Glitchy> ⭐ Bottom 3 Karma: 1. Troll (-8) 2. Grump (-5) 3. Meanie (-2)
```

**Channel leaderboard:**
```
<User> $ctop 5
<Glitchy> ⭐ #channel Top 5: 1. Helper (45) 2. Friend (15) 3. User (8) ...
```

**Set karma (ops only):**
```
<@Admin> $setkarma Troll 0
<Glitchy> ⭐ Troll's karma in #channel set to 0
```
