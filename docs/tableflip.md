# (╯°□°）╯︵ ┻━┻ Table Flip (tableflip)

Play a 4-step table flip animation with timed delays between each frame.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/tableflip.py
```

**No data storage** — cooldowns are tracked in memory only.

---

## Commands

| Command | Description |
|---------|-------------|
| `$flip` | Play a 4-step table flip animation |

---

## How It Works

1. The bot sends **4 messages** with a **2 second delay** between each one.
2. Messages are sent in a background thread so the bot isn't blocked during the animation.
3. Each user has a **60-second cooldown per channel**. If triggered too soon, the bot sends a private NOTICE telling you how long to wait.

### The Animation Sequence

```
Frame 1:  ╭∩╮( º.º )╭∩╮
  (2 second pause)
Frame 2:  ┬─┬ノ( º _ ºノ)
  (2 second pause)
Frame 3:  o(*≧▽≦)ツ┏━┓
  (2 second pause)
Frame 4:  (╯°□°）╯︵ ┻━┻
```

---

## Examples

**Flip a table:**
```
<User> $flip
<Glitchy> ╭∩╮( º.º )╭∩╮
<Glitchy> ┬─┬ノ( º _ ºノ)
<Glitchy> o(*≧▽≦)ツ┏━┓
<Glitchy> (╯°□°）╯︵ ┻━┻
```

**On cooldown:**
```
<User> $flip
-Glitchy- You need to wait 45 seconds before flipping again.
```
> Cooldown notices are sent as a private NOTICE, not to the channel.
