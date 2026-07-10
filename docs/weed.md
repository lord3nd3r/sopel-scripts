# 🌿 Weed & Trippy Sessions (weed)

A lighthearted party/sesh module for Sopel with countdown animations (solo mode) and gift actions (with a target user). It supports 15 substance categories, inline triggers, and rotation passing.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/weed.py
```

**Data Persistence:** None (cooldowns are tracked in memory).

---

## Commands

All commands support an optional target `<nick>` argument. If the target is present in the channel, it sends a gift action. Otherwise, it triggers the channel-wide countdown animation.

### Substance Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed` | — | Weed session / gift 🌿 |
| `$bong` | — | Bong rip with water bubbling countdown 🫧 |
| `$joint` | — | Roll up and spark a joint 📜 |
| `$keef` | `$kief` | Sprinkle some keef ✨ |
| `$trip` | — | DMT breakthrough experience 👽🌀 |
| `$shrooms` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid` | `$lsd` | Acid trip with fractal visuals 🌈 |
| `$peyote` | `$mescaline` | Peyote vision quest 🌵 |
| `$toke` | — | Pack a bowl and take a toke 🌬️ |
| `$edible` | `$edibles` | Eat or gift a THC-infused snack 🍪 |
| `$dab` | `$dabs` | Heat the banger and take a dab 💎🔥 |
| `$blunt` | — | Roll and spark a slow-burning blunt 🍂 |
| `$vape` | — | Discreet vapor hits 🔌☁️ |
| `$hash` | — | Old-world hash crumble 🟤 |
| `$munchies` | — | Raiding the kitchen for snacks 🍕🍿 |

### Rotation & Help Commands

| Command | Arguments | Description | Example |
|---------|-----------|-------------|---------|
| `$pass` | `<nick>` | Take a hit and pass the rotation to someone else (requires target in channel) | `$pass Friend` |
| `$weedhelp` | — | PM a complete command reference card to the user | `$weedhelp` |

---

## Sesh Modes

### Mode 1: Solo Countdown (No Target)
When you trigger a command **without a target** (or if the target user is offline/not in the channel), it starts a **3-step countdown animation** in a background thread.
* Each step prints a themed, colored message.
* There is a **6-second delay** between each step.
* The final step posts a random colorful outcome from that substance's pool.

### Mode 2: Gift (With a Target User)
When you specify a target user who is **active in the channel**, the bot posts a single `/me` action message gifting the target a random item from the chosen substance pool.

---

## Cooldowns

* **Channel Cooldown (Countdown mode)**: **20 minutes** (shared by all users and all countdowns in the channel).
* **Per-User Cooldown (Gift & Pass mode)**: **30 seconds** (individual cooldown to prevent spamming gifts).
* Cooldowns are tracked by NickServ account (when registered) or nickname.

---

## Inline Triggering
Countdown commands can be triggered **mid-sentence**:
```
<User> man I could really use a $bong right now
<Glitchy> 🫧 3... Filling the water...
<Glitchy> 🧊 2... Adding ice...
<Glitchy> 🔥 1... Lighting the bowl...
<Glitchy> Bong rip incoming — lean back and ride the clouds 🌊💨
```
* Mid-sentence triggers respect the same 20-minute channel cooldown.
* To prevent duplicate triggers, messages starting with a command prefix (`$`) do not trigger inline rules.

---

## Substance Pools Reference

| Substance | Gift Pool Size | Sample Gifts |
|-----------|---------------|-------------|
| Weed | 30 | joint, bong rip, edible, vape hit, moon rock, rosin press |
| Bong | 10 | ice-catch bong, gravity bong, percolator, beaker |
| Joint | 11 | cross joint, spliff, cone, pinner, kief-dusted |
| Keef | 8 | bowl topped with keef, keef puck, moonrock, pure keef bowl |
| DMT (trip) | 14 | glass vapor genie, breakthrough, changa joint, ayahuasca brew |
| Shrooms | 14 | golden teachers, penis envy chocolate, blue meanies, lemon tek |
| Acid | 14 | white-on-white, gel tab, blotter art, sugar cube, ten-strip |
| Peyote | 10 | dried button, San Pedro cactus tea, mescaline capsule |
| Toke | 5 | fat bowl of OG Kush, Sour Diesel spoon pipe, Purple Haze pipe |
| Edibles | 14 | canna-brownie, space cake, 100mg gummy worms, space cookie |
| Dab | 10 | live rosin, shatter glob, terp pearl, diamond-and-sauce |
| Blunt | 10 | backwoods, grape Swisher, two-gram torpedo, gold-leaf blunt |
| Vape | 10 | live resin cart, disposable pen, volcano bag |
| Hash | 10 | Nepalese temple ball, Moroccan blonde, Afghani black chunk |
| Munchies | 12 | pepperoni pizza, nacho cheese chips, cold leftovers, ice cream |
