# 🌿 Weed & Trippy (weed)

Themed smoke/trip messages with two modes: **solo countdown animations** (3-step sequence with delays) and **gift messages** (give to a target user). 8 substance types with unique message pools.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/weed.py
```

**No data storage** — all cooldowns are tracked in memory only.

---

## Commands

### Smoke Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed [nick]` | — | Weed session 🌿 |
| `$bong [nick]` | — | Bong rip with countdown 🫧 |
| `$joint [nick]` | — | Spark a joint 📜 |
| `$keef [nick]` | `$kief` | Sprinkle some keef ✨ |

### Trip Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$trip [nick]` | — | DMT breakthrough 👽🌀 |
| `$shrooms [nick]` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid [nick]` | `$lsd` | Acid trip 🌈 |
| `$peyote [nick]` | `$mescaline` | Peyote vision quest 🌵 |

---

## Two Modes

### Mode 1: Solo Countdown (no target)

When you use a command **without a target** (or the target isn't in the channel), you get a **3-step animated countdown** with 6-second delays between each message, followed by a random finale.

**How it works:**
1. Message 1 (preparation) — colored with IRC formatting
2. *6-second pause*
3. Message 2 (action) — colored with IRC formatting
4. *6-second pause*
5. Message 3 (finale) — colored with IRC formatting + random final message

The countdown runs in a background thread so the bot isn't blocked.

### Mode 2: Gift (with a valid target)

When you specify a user who is **actually in the channel**, the bot sends a single `/me` action message gifting them a random item from that substance's pool.

---

## Cooldowns

| Type | Duration | Scope |
|------|----------|-------|
| **Countdown mode** | 20 minutes | Per-channel (shared by all users and all commands) |
| **Gift mode** | 30 seconds | Per-user (shared across all command variants) |

> Cooldown identity is based on your **NickServ account** when available, falling back to nick. This prevents switching nicks to bypass cooldowns.

---

## Inline Trigger

You don't have to use the command at the start of a message. Commands can appear **mid-sentence**:

```
<User> Hey dude I really need a $weed right now
<Glitchy> 🌿 3... Get ready...
<Glitchy> 🌿 2... Sparking up...
<Glitchy> 🌿 1... 💨 Puff puff pass — light it up and keep it lit! 🌿🔥
```

This works for all command variants (`$bong`, `$trip`, `$shrooms`, etc.).

---

## Message Pools

Each substance has its own curated pool of **gift items**, **countdown messages**, **action templates**, and **finale messages**:

| Substance | Gift Pool Size | Sample Gifts |
|-----------|---------------|-------------|
| Weed | 30 | Joint, bong, edible, vape, dab, blunt, moon rock, etc. |
| Bong | 10 | Ice-catch bong, gravity bong, percolator, beaker, etc. |
| Joint | 11 | Cross joint, spliff, cone, pinner, kief-dusted, etc. |
| Keef | 8 | Topped bowl, pressed puck, sprinkle, moon rock, etc. |
| DMT (trip) | 14 | Glass vapor genie, breakthrough, vape cart, changa, ayahuasca, etc. |
| Shrooms | 14 | Golden teacher, penis envy, blue meanies, liberty caps, heroic dose, etc. |
| Acid | 14 | White-on-white, gel tab, blotter art, sugar cube, liquid, dancing bears, etc. |
| Peyote | 10 | Dried button, tea, fresh slice, extract, mescaline sulfate, etc. |

---

## Examples

### Smoke Commands

**Solo bong rip (3-step countdown):**
```
<User> $bong
<Glitchy> 🫧 3... Packing the bowl...
<Glitchy> 🫧 2... Lighting up and pulling...
<Glitchy> 🫧 1... RIIIIIP! 💨 User clears the bong! Smooth as glass.
```

**Gift a joint to someone:**
```
<User> $joint Friend
* Glitchy passes a fat cross joint to Friend. Puff puff pass! 💨
```

**Solo weed session:**
```
<User> $weed
<Glitchy> 🌿 3... Rolling one up...
<Glitchy> 🌿 2... Sparking the lighter...
<Glitchy> 🌿 1... 💨 Puff puff pass — light it up and keep it lit! 🌿🔥
```

**Gift weed:**
```
<User> $weed Friend
* Glitchy hands Friend a fat blunt — enjoy! 🌿💨
```

**Keef:**
```
<User> $keef
<Glitchy> ✨ 3... Scooping the keef...
<Glitchy> ✨ 2... Topping the bowl...
<Glitchy> ✨ 1... 💨 Keef hit activated! Sparkle city. ✨🔥
```

### Trip Commands

**Solo shroom trip:**
```
<User> $shrooms
<Glitchy> 🍄 3... Eating a handful of golden teachers...
<Glitchy> 🍄 2... The walls are breathing...
<Glitchy> 🍄 1... 🌊 The carpet is alive and the ceiling is a fractal 🍄🧘
```

**Gift acid:**
```
<User> $acid Friend
* Glitchy drops a gel tab on Friend's tongue. See you in 12 hours! 🌈✨
```

**DMT breakthrough:**
```
<User> $trip
<Glitchy> 👽 3... Loading the vapor genie...
<Glitchy> 👽 2... Holding... holding...
<Glitchy> 👽 1... 🌀 B R E A K T H R O U G H — the chrysanthemum opens 🌸🌀👽
```

**Peyote vision quest:**
```
<User> $peyote
<Glitchy> 🌵 3... Chewing the peyote button...
<Glitchy> 🌵 2... The desert spirits begin to speak...
<Glitchy> 🌵 1... 🦅 User has received a vision from the ancestors. 🌵🌌
```

**Gift shrooms:**
```
<User> $mushrooms Friend
* Glitchy offers Friend a bag of liberty caps — happy trails! 🍄✨
```

### Cooldown Examples

**Countdown on cooldown:**
```
<User> $bong
-Glitchy- The bong countdown is on cooldown for 14m32s in #channel.
```

**Gift on cooldown:**
```
<User> $weed Friend
-Glitchy- You must wait 22s before giving weed again in #channel.
```

### Inline Trigger

**Mid-sentence trigger:**
```
<User> man I could really use a $bong right about now
<Glitchy> 🫧 3... Packing the bowl...
<Glitchy> 🫧 2... Lighting up and pulling...
<Glitchy> 🫧 1... RIIIIIP! 💨 Smooth as glass.
```

**Target not in channel (falls back to countdown):**
```
<User> $joint OfflineUser
<Glitchy> 📜 3... Rolling the joint...
<Glitchy> 📜 2... Licking the paper...
<Glitchy> 📜 1... 💨 Sparked! Pass it around. 📜🔥
```
