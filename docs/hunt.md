# 🌲 Hunting Game (hunt)

Wildlife hunting mini-game modeled after the authentic IRCHunt v5.5.0 mechanics. Features wildlife encounters, multiple rarity tiers, weapon leveling, ammo and reload management, hunting permits, loot drops, steady aim, and contract bounties.

---

## Setup

**1. Script file:**
```
~/.sopel/scripts/hunt.py
```

**2. Channel Activation (Safe by default):**
The plugin is disabled by default in all channels so it won't spam active discussions. A bot admin or channel operator must enable it per-channel:
```
$hunttoggle on
```
When enabled, the bot announces that hunting is active in the channel and directs users to `$hunthelp` to get started.

**3. Database:**
No configuration needed. The database (`hunt.db`) is automatically created in the scripts directory on first use.

---

## Commands

The command prefix matches your bot's configured prefix (default `$`).

### Help & Overview

| Command | Aliases | Description |
|---------|---------|-------------|
| `$hunthelp` | `$hunt`, `$huntinghelp` | Display the full in-depth hunting reference, commands, and guide. |

### Hunting Actions

| Command | Aliases | Description |
|---------|---------|-------------|
| `$shoot` | `$sh` | Shoot at the currently engaged or newest spawned animal in the channel. |
| `$reloadgun` | `$reload`, `$rel` | Reload your active weapon with ammunition. |
| `$bef <animal>` | `$befriend` | Attempt to befriend a creature with food instead of shooting it. |

### Stats & Equipment

| Command | Aliases | Description |
|---------|---------|-------------|
| `$hunter` | — | Display your hunter level, XP progress, permits, and active weapon stats. |
| `$gun` | — | Check your current weapon model, damage, magazine capacity, and ammo count. |
| `$stats [nick]` | — | View career hunting statistics (kills, misses, accuracy, earnings). |
| `$huntboard` | `$huntleaderboard`, `$hboard` | View top hunters by XP, level, and trophy harvests. |

### Shop & Contracts

| Command | Aliases | Description |
|---------|---------|-------------|
| `$huntshop` | `$shop` | Browse available weapons, permits, and equipment upgrades. |
| `$buy <item>` | — | Purchase weapons, permits, or gear with earned hunting currency / XP. |
| `$contract` | `$bounty` | View or accept current hunting contracts for bonus XP and rewards. |

### Admin & Channel Management

*Requires Bot Admin or Channel Operator (+o) status.*

| Command | Description |
|---------|-------------|
| `$hunttoggle [on\|off]` | Enable or disable hunting encounters in the current channel. |
| `$huntspawn [animal]` | Force spawn a specific animal or a random creature immediately. |
| `$huntrate [slow\|normal\|fast\|<min> <max>]` | View or configure spawn timer interval in minutes (default: 6 to 12 mins). |

---

## Game Mechanics

### 🎯 Steady Aim & Combat Lock
- **Engagement Lock**: Once you shoot at an animal, your weapon locks onto that target across shots and reloads until it is harvested, flees, or you switch targets.
- **Combat Timer Extension**: Every successful hit extends the animal's stay by up to 180 seconds, giving you enough time to reload and finish the hunt.
- **Steady Aim**: Each consecutive miss grants a **+9% accuracy bonus** on your next shot, simulating dialing in your sights.
- **Critical Finish**: Precision shots have a chance to inflict bonus damage or immediately harvest weakened quarry.

### 🦌 Wildlife Rarity & Permits
Animals spawn across multiple tiers with authentic rarity adjectives (`Large`, `Mature`, `Old`, `Prize`, `Massive`, `Mythic`):
- **Common / Small Game**: Squirrels, Rabbits, Ducks, Geese (Requires Waterfowl / Small Game Permit).
- **Uncommon / Big Game**: Deer, Boars, Wolves (Requires Big Game Permit).
- **Rare / Dangerous Game**: Bears, Moose, Mountain Lions (Requires Dangerous Game / Trophy Permit).
- **Legendary / Mythic**: Ancient Elk, Albino Grizzlies, Mythic Beasts.

### 🤫 Clean Channel Notices
Ammo depletion warnings (`[AMMO]`), empty chamber alerts (`[RELOAD]`), and permit clearance requirements are sent via private IRC notices (`NOTICE`) to keep channel chat clear and uncluttered.

---

## Examples

**Spawning and Hunting:**
```
<Glitchy> [UNCOMMON] A Large Deer steps out from the tree line! Deer HP 15 | 85 XP | L5 + Gun L2 + Big Game Permit
<User> $shoot
<Glitchy> [HIT] User hit Large Deer for 3 damage! HP 12/15 | +1 XP | Accuracy 78%
<User> $shoot
<Glitchy> [MISS] User missed Large Deer | Accuracy 78% | Steady Aim next shot ~87%
<User> $shoot
<Glitchy> [CRITICAL HIT] User scored a critical shot on Large Deer for 12 damage!
<Glitchy> [UNCOMMON KILL] User harvested Large Deer and earned 85 XP! | Trophy +5 (22) | Loot: Venison, Antlers
```

**Reloading:**
```
<User> $shoot
* Glitchy notices: [RELOAD] *CLICK* Out of ammo! Type $reloadgun to reload your Rifle (5/5).
<User> $reloadgun
<Glitchy> User slammed a fresh magazine into Rifle! (5/5 rounds)
```

**Admin Spawn Rate Tuning:**
```
<User> $huntrate
<Glitchy> 🌲 Hunt spawn rate for #channel: 6 to 12 minutes (preset: normal). Active animals: 0/2.
<User> $huntrate slow
<Glitchy> 🌲 Hunt spawn rate for #channel set to slow (15 to 30 minutes).
<User> $huntrate 10 20
<Glitchy> 🌲 Hunt spawn rate for #channel set to 10 to 20 minutes.
```
