# 🧩 Trivia (trivia)

Multi-player trivia with categories, progressive hints, streaks, and stats.

---

## Setup

**1. Place all required files in the scripts directory:**
```
~/.sopel/scripts/trivia.py
~/.sopel/scripts/trivia_game.py      # game engine
~/.sopel/scripts/trivia_db.py        # database layer
~/.sopel/scripts/questions.json      # question bank
```

**No config section needed.** The trivia database (`trivia_stats.db`) is created automatically in the scripts directory on first use. Questions are loaded from `questions.json`.

---

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$trivia [N]` | — | Start a game with N questions (default 100) |
| `$strivia` | — | Stop the current game |
| `$triviastats [nick]` | `$tstats` | View stats for yourself or another player |
| `$triviatop` | `$ttop` | Top 10 in this channel |
| `$triviatopserver` | `$ttopserver` | Top 10 across the server |

---

## Examples

**Start a trivia game:**
```
<User> $trivia
<Glitchy> 🧩 Trivia started! 100 questions. Type your answer in chat!
<Glitchy> 🧩 [1/100] Category: Science — What planet is known as the Red Planet?
<User> mars
<Glitchy> ✅ User got it! The answer was Mars. 🔥 Streak: 1
```

**Start a short game:**
```
<User> $trivia 10
<Glitchy> 🧩 Trivia started! 10 questions. Type your answer in chat!
```

**Stop a game:**
```
<User> $strivia
<Glitchy> 🧩 Trivia stopped! Final scores: User (8) | Friend (6) | Player (3)
```

**Check your stats:**
```
<User> $triviastats
<Glitchy> 🧩 User — Correct: 142 | Games: 12 | Best Streak: 8 | Accuracy: 68%
```

**Check someone else's stats:**
```
<User> $tstats Friend
<Glitchy> 🧩 Friend — Correct: 89 | Games: 7 | Best Streak: 5 | Accuracy: 72%
```

**Channel leaderboard:**
```
<User> $triviatop
<Glitchy> 🧩 #channel Top 10: 1. Brainiac (320) 2. User (142) 3. Friend (89) ...
```

**Server leaderboard:**
```
<User> $ttopserver
<Glitchy> 🧩 Server Top 10: 1. Brainiac (580) 2. Scholar (412) 3. User (142) ...
```
