# 🌿 Weed & Trippy (weed)

Themed smoke/trip messages. With a target nick = gift message. Without = 3-step countdown animation.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/weed.py
```

---

## Commands

### Smoke

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed [nick]` | — | Weed session 🌿 |
| `$bong [nick]` | — | Bong rip with countdown 🫧 |
| `$joint [nick]` | — | Spark a joint 📜 |
| `$keef [nick]` | `$kief` | Sprinkle some keef ✨ |

### Trip

| Command | Aliases | Description |
|---------|---------|-------------|
| `$trip [nick]` | — | DMT breakthrough 👽🌀 |
| `$shrooms [nick]` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid [nick]` | `$lsd` | Acid trip 🌈 |
| `$peyote [nick]` | `$mescaline` | Peyote vision quest 🌵 |

---

## Cooldowns

- **Channel cooldown:** 20 minutes between countdown sessions
- **Per-user cooldown:** 30 seconds between gift commands

---

## Examples

**Solo bong rip (3-step countdown):**
```
<User> $bong
<Glitchy> 🫧 User packs the bowl...
<Glitchy> 🫧 User lights up and pulls...
<Glitchy> 🫧 RIIIIIP! User clears the bong! 💨
```

**Gift a joint to someone:**
```
<User> $joint Friend
<Glitchy> 📜 User passes a fat joint to Friend. Puff puff pass! 💨
```

**Solo weed session:**
```
<User> $weed
<Glitchy> 🌿 User rolls one up...
<Glitchy> 🌿 User sparks the lighter...
<Glitchy> 🌿 User blazes it! 💨 Chill vibes all around.
```

**Gift weed:**
```
<User> $weed Friend
<Glitchy> 🌿 User passes the blunt to Friend. Enjoy! 💨
```

**Trip:**
```
<User> $shrooms
<Glitchy> 🍄 User eats a handful of mushrooms...
<Glitchy> 🍄 The walls are breathing...
<Glitchy> 🍄 User has achieved ego death. Welcome back. 🌌
```

**Gift acid:**
```
<User> $acid Friend
<Glitchy> 🌈 User drops a tab on Friend's tongue. See you in 12 hours! ✨
```

**Peyote vision quest:**
```
<User> $peyote
<Glitchy> 🌵 User chews the peyote button...
<Glitchy> 🌵 The desert spirits begin to speak...
<Glitchy> 🌵 User has received a vision from the ancestors. 🦅
```
