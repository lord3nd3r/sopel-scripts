# 🤖 Sopel IRC Bot Scripts

A collection of custom [Sopel](https://sopel.chat/) IRC bot plugins for fun, utility, and community engagement.

> **Quick reference:** See [commands.md](commands.md) for a concise list of every command across all scripts.

---

## 📋 Table of Contents

- [AI & Chat](#-ai-grok---ai-chatbot)
- [Bartender](#-beer---virtual-bartender)
- [Weed & Trippy Commands](#-weed---smoking--psychedelic-sessions)
- [Mug Game](#-mug---coin-mugging--gambling-game)
- [Moo Counter](#-moo---moo-counter)
- [Karma](#-karma---karma-system)
- [Trivia](#-trivia---trivia-game)
- [Weather](#-weather---weather-forecasts)
- [Stocks](#-stock---stock-lookup)
- [Voting](#-voting---channel-polls)
- [Channel Monitor](#-monitor---channel-statistics)
- [Verbal Morality](#-curse---verbal-morality-statute)
- [Facepalm](#-facepalm---facepalm-reactions)
- [Table Flip](#-tableflip---table-flip-animation)
- [PromoteMe](#-opme---self-promotion)
- [Join](#-join---bot-channel-join)
- [YouTube Titles](#-youtube_titles---youtube-link-titles)
- [CLI Trivia & Demos](#-cli--demo-scripts)
- [Installation](#-installation)
- [Configuration](#-configuration)

---

## 🧠 ai-grok — AI Chatbot

An AI chatbot powered by the **xAI Grok API**. The bot responds when mentioned by name, handles emotes/actions, supports web search for current events, and maintains per-user conversation history.

### Features
- Responds conversationally when addressed by nick
- Reacts to `/me` actions (pets, hugs, pokes, etc.) with fun emote replies
- **Automatic web search** for news, scores, current events, and time-sensitive queries
- Per-user conversation history stored in SQLite
- **Review mode** — summarize what has been discussed in channel (persisted to DB across restarts)
- **Time/date awareness** with per-user timezone and format preferences
- Admin commands via PM
- Heuristic intent detection to avoid responding to incidental mentions
- Per-channel busy flag to prevent response spam
- Context truncation (3,200 char budget) to keep API calls efficient

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `BotNick: <message>` | Talk to the bot | `Grok: what's the weather like?` |
| `<message> BotNick` | Also triggers a response | `hey what do you think Grok` |
| `/me pets BotNick` | Emote interaction — bot reacts | `/me hugs Grok` |
| `$grokreset` | Reset your conversation history | `$grokreset` |
| `$grokreset channel` | Reset all channel history (admin/op) | `$grokreset channel` |
| `$testemote` | Verify emote plugin is loaded | `$testemote` |

### 🔍 Web Search (Automatic)

The bot **automatically** uses live web search when it detects that your question is about something time-sensitive or factual. There is no special command — just ask naturally and the bot decides whether to search.

**Trigger keywords** (any of these in your message activates search):

| Category | Keywords |
|----------|----------|
| News & Events | `news`, `latest`, `recent`, `today`, `yesterday`, `tonight`, `this week`, `this month`, `current events`, `headlines`, `breaking`, `update` |
| Sports | `score`, `results`, `standings`, `who won`, `who is winning` |
| Finance | `stock price` |
| Weather | `weather`, `forecast` |
| People & Events | `who died`, `is ___ dead`, `did ___ happen`, `election`, `poll` |
| General | `search`, `whats happening` |

**Examples:**
```
Grok: what's the latest news today?
Grok: who won the NBA game last night?
Grok: what's the stock price of AAPL?
Grok: search for the election results
Grok: what's the weather forecast for tomorrow?
```

> **Note:** If the web search API fails, the bot automatically falls back to answering from its training data.

### 🕐 Time & Date Queries

Ask the bot about the current time or date and it responds instantly. Time queries **bypass rate-limiting** so you can always get a fresh answer.

**Trigger phrases:**
- `what time is it`, `what's the time`, `current time`
- `what's the date`, `what day is it`, `today's date`

**Examples:**
```
Grok: what time is it?
Grok: what's today's date?
Grok: what day is it?
```

#### Setting Your Timezone

Tell the bot your timezone and it will remember it for all future time queries:

| Method | Example |
|--------|---------|
| Tell the bot | `Grok: I'm in EST` |
| Explicit set | `Grok: set my timezone to CST` |
| Natural phrasing | `Grok: I live in Pacific` |

**Supported timezone abbreviations:**
`EST` / `EDT` / `ET` / `Eastern`, `CST` / `CDT` / `CT` / `Central`, `MST` / `MDT` / `MT` / `Mountain`, `PST` / `PDT` / `PT` / `Pacific`, `UTC` / `GMT`

#### Setting Your Time Format

Prefer 12-hour or 24-hour time? Tell the bot:

```
Grok: I prefer 12hr
Grok: use 24 hour
```

Preferences are saved in the database and persist across restarts.

### 💬 Review Mode

Ask the bot to summarize or give its opinion on what has been discussed in the channel. Review mode collects recent messages from **all users** in the channel and generates a brief, opinionated summary. Channel messages are **persisted to the database** so review mode survives bot restarts.

**Trigger phrases:**
- `thoughts`, `opinion`, `what do you think`
- `summarize`, `give me your take`, `opine`
- `what's being discussed`, `what's happening`, `what's going on`
- `catch me up`, `fill me in`, `what did I miss`
- `recap`, `tldr`, `tl;dr`, `what happened`
- `^^` (shorthand)

**Examples:**
```
Grok: what do you think?
Grok: give me your opinion on what's being discussed
Grok: catch me up, what did I miss?
Grok: tldr
```

> **Cooldown:** Review mode has a 30-second cooldown per channel to prevent spam.

### 🤗 Emote Interactions

The bot reacts to `/me` actions and emote-style messages directed at it. Responses are **generated dynamically by the AI** and vary each time — the examples below are illustrative only.

| Action | Example Reply |
|--------|---------------|
| pet / pat | *nuzzles lovingly 🥰* |
| hug / cuddle / snuggle | *wraps you in a cozy hug 🤗* |
| poke / boop | *boops playfully 👋* |
| kiss | *sends a sweet smooch 😘* |
| nuzzle | *nuzzles warmly 🫶* |
| bonk | *bonks gently with a plush hammer 🫠* |
| slap / smack | *gives a surprised gasp and a tut 😳* |
| highfive | *gives a triumphant high five ✋* |
| wave / wink / dance / twirl | Various fun reactions |

**Trigger formats:**
```
/me pets Grok
/me hugs Grok
* End3r pets Grok
```

### Admin PM Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$join #channel [key]` | Make bot join a channel | `$join #mychannel` |
| `$part #channel` | Make bot leave a channel | `$part #mychannel` |
| `$ignore <nick>` | Ignore a user (persisted to DB) | `$ignore spammer` |
| `$unignore <nick>` | Unignore a user | `$unignore spammer` |

### Configuration (`default.cfg`)
```ini
[grok]
api_key = your-xai-api-key
model = grok-4-1-fast-reasoning
system_prompt = You are a friendly IRC bot.
blocked_channels = #somechannel
banned_nicks = baduser1,baduser2
ignored_nicks = bot1,bot2
intent_check = heuristic
```

### Dependencies
- `requests`
- Stores data in `grok_data/grok.sqlite3`

---

## 🍺 beer — Virtual Bartender

A full-featured virtual bartender with a tip-based economy! Order drinks, food, and tip other users.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$beer [nick]` | Serve a random beer (🍺 $5) | `$beer m0n` |
| `$shot [nick]` | Serve a random shot (🥃 $7) | `$shot` |
| `$whiskey [nick]` / `$whisky` | Serve a fine whiskey (🥃 $12) | `$whiskey JohnDoe` |
| `$wine [nick]` | Serve a glass of wine (🍷 $8) | `$wine` |
| `$magners [nick]` | Serve a Magners cider (🍎 $6) | `$magners` |
| `$drink [nick]` | Serve a mixed drink (🍹 $10) | `$drink` |
| `$mocktail [nick]` / `$virgin` | Serve a mocktail (🍹 $4) | `$mocktail` |
| `$coffee [nick]` / `$caffeine` | Serve coffee (☕ $3) | `$coffee` |
| `$tea [nick]` / `$cuppa` | Serve tea (🍵 $3) | `$tea` |
| `$water [nick]` / `$hydrate` | Serve water (💧 free!) | `$water` |
| `$pizza [nick]` | Serve a pizza (🍕 $15) | `$pizza` |
| `$appetizer [nick]` / `$snack` / `$food` | Serve an appetizer (🍽️ $8) | `$appetizer` |
| `$surprise [nick]` / `$random` | Random item from the menu (🎉) | `$surprise` |
| `$tip <nick> <amount>` | Tip another user | `$tip m0n 20` |
| `$barcash` | Check your current balance | `$barcash` |
| `$toptip` | Top 5 most tipped bartenders | `$toptip` |
| `$barhelp` | Full help menu (sent via PM) | `$barhelp` |

### Admin Commands (PM only)

| Command | Description | Example |
|---------|-------------|---------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's balance | `$adjbal m0n +100` |
| `$barreset <nick>` | Reset a user's balance to $100 | `$barreset m0n` |
| `$barreset all confirm` | Reset ALL balances | `$barreset all confirm` |

> **Note:** All beer commands use the `$` prefix (e.g. `$beer`, not `!beer`).

### Economy
- Every user receives a **daily $100 credit**
- Items cost between $0 (water) and $15 (pizza)
- Tip data is stored in `~/.sopel/bartender_tips.json`

---

## 🌿 weed — Smoking & Psychedelic Sessions

Share lighthearted party messages with themed countdowns, gifts, and action messages. Features multiple substances, each with unique theming, emojis, and color schemes.

### Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed [nick]` | — | Share a weed-themed gift or session 🌿 |
| `$bong [nick]` | — | Bong rip session with water/ice countdown 🫧 |
| `$joint [nick]` | — | Roll up and spark a joint 📜 |
| `$keef [nick]` | `$kief` | Sprinkle some keef ✨ |
| `$trip [nick]` | — | DMT breakthrough experience 👽🌀 |
| `$shrooms [nick]` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid [nick]` | `$lsd` | Acid trip with fractal visuals 🌈 |
| `$peyote [nick]` | `$mescaline` | Peyote desert vision quest 🌵 |

### Behavior
- **With a target:** Sends an action message gifting the target a random item (target must be in the channel)
  ```
  * Bot hands m0n a fat bong rip 🌊
  ```
- **Without a target:** Performs a themed 3-step countdown (6s between each), then posts a random colorful final message
  ```
  🫧 3... Filling the water...
  🧊 2... Adding ice...
  🔥 1... Lighting the bowl...
  Bong rip incoming — lean back and ride the clouds 🌊💨
  ```
- **Mid-sentence triggers:** Commands work anywhere in a message, not just at the start
  ```
  I feel the need for $weed
  someone pass me a $bong please
  ```

### Cooldowns
- **Channel cooldown:** 20 minutes between countdown sessions (does not apply to gift actions)
- **Per-user cooldown:** 30 seconds between gift commands (does not apply to countdowns)
- Mid-sentence triggers respect the same cooldowns and show a notice if on cooldown

---

## 💰 mug — Coin, Mugging & Gambling Game

Based on TAYbot by ANNA on Rizon - https://github.com/Annaslut/TAY/

A full IRC economy game with coins, mugging, betting, bounties, a shop, and an item system. Includes anti-cheat measures and NickServ identity verification.

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$coins` | Collect your coins (scaled by wealth) | `$coins` |
| `$balance [nick]` | Check your (or someone's) balance | `$balance m0n` |
| `$give <nick> <amount>` | Give coins to another user | `$give m0n 500` |

> **Tip:** Amounts accept commas — `$bet 1,000,000` works everywhere.

### Combat & Crime

| Command | Description | Example |
|---------|-------------|---------|
| `$mug <nick>` | Attempt to rob another user | `$mug richguy` |
| `$rob <nick>` | Same as `$mug` | `$rob richguy` |
| `$bounty <nick> <amount>` | Place a bounty on someone | `$bounty m0n 1000` |
| `$bounties` | List top active bounties | `$bounties` |
| `$jail` | Check your jail status | `$jail` |

### Gambling

| Command | Description | Example |
|---------|-------------|---------|
| `$bet <amount>` | Gamble your coins (chance-based) | `$bet 500` |

### Shop & Items

| Command | Description | Example |
|---------|-------------|---------|
| `$shop` | View the item shop | `$shop` |
| `$buy <item>` | Purchase an item (PM) | `$buy bail` |
| `$inv` | View your inventory (PM) | `$inv` |
| `$use <item>` | Use a consumable item (PM) — passive items work automatically | `$use bail` |

### Leaderboards

| Command | Description |
|---------|-------------|
| `$top5` | Top 5 richest users (10-min per-user cooldown, admins exempt) |
| `$top10` | Top 10 richest users (10-min per-user cooldown, admins exempt) |

### Help & Admin

| Command | Description |
|---------|-------------|
| `$mughelp` | Full help guide (PM) |
| `$mugadd <nick> <amount>` | Add coins to a user (admin, PM) |
| `$mugset <nick> <amount>` | Set a user's balance (admin, PM) |
| `$mugtake <nick> <amount>` | Remove coins from a user (admin, PM) |
| `$mugreset` | Reset all data (admin, PM) |
| `$mugcleardb confirm` | Delete all records from DB (admin, PM) |
| `$mugmerge <nick>` | Merge duplicate records (admin, PM) |
| `$mugdup <nick>` | List duplicate records (admin, PM) |
| `$mugclearbounty <nick>` | Clear all bounties on a nick (admin, PM) |
| `$mugtoggle [on\|off]` | Enable/disable per-channel (admin) |
| `$mugstats` | Economy overview: user count, top 5, total coins (admin, PM) |
| `$godmode [on\|off] [nick]` | Toggle 99% luck for yourself or a player (admin, PM) |

### Bot Player (glitchy)
- The bot participates in the mug game with its own wallet (seeded at 500k coins)
- **Retaliation:** 60% chance to counter-mug you 5–15 seconds after you mug it
- **Proactive:** Randomly mugs top 5 richest players every 30–90 minutes in `#mug`
- Normal odds (50% success, 5–15% steal, 10–25% fail loss) — no god mode

### Channel Rules
- Mug game is **disabled by default** per channel — an admin must `$mugtoggle on`
- Home channel: `#mug` — disabled messages direct players there
- **Admins are exempt from all cooldown timers**

### Features
- Wealth-scaled coin collection
- Jail system with bail items
- Passive items (work automatically from inventory) vs. consumable items
- Active item effects (attack bonuses, defense)
- Anti-cheat: NickServ verification, daily give caps, command throttling
- Titles based on wealth level
- Bot player with retaliation and proactive mugging AI
- Comma support in all amount inputs

---

## 🐄 moo — Moo Counter

Track and count "moos" across the network! Say "moo" in chat and watch the counter climb. Includes legendary moos, sudo moo, and leaderboards.

### Triggers

| Trigger | Description |
|---------|-------------|
| `moo` (in text) | Increments your moo counter (+1) |
| `/me moos` | Action-based moo (no cooldown) |
| `sudo moo` | Power moo: +10 (1/hour per user per channel) |

### Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$moocount` | `$mymoo` | Check your moo count |
| `$mootop` | `$topmoo` | Global moo leaderboard |
| `$mootopchan` | `$chanmootop`, `$topmoochan` | Per-channel leaderboard |
| `$totalmoo` | `$moostats` | Global and channel moo totals |
| `$mooreset` | — | Reset a user's moo count (admin only) |
| `$moohelp` | `$aboutmoo` | Help info sent via PM |

### Special Events
- **Legendary Moo** (2% chance): ✨ Extra moo bonus with special message!
- **Sudo Moo Big Loss** (0.5% chance): Lose 100 moos — devastating!
- Per-user, per-channel cooldowns prevent spam

---

## ⭐ karma — Karma System

Give and receive karma with `++` and `--`. Features per-channel and global tracking, cooldowns, and leaderboards.

### Usage

| Syntax | Description | Example |
|--------|-------------|---------|
| `<nick>++` | Give karma (+1) | `m0n++` |
| `<nick>--` | Remove karma (-1) | `troll--` |
| `<nick>==` | Check someone's karma inline | `m0n==` |

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$karma <nick>` | Show channel + global karma for a user | `$karma m0n` |
| `$karma` | Show full command list (PM) | `$karma` |
| `$karmatop [N]` / `$ktop` | Top N users by karma (default 5) | `$karmatop 10` |
| `$karmabottom [N]` / `$kbottom` | Bottom N users by karma | `$karmabottom 5` |
| `$channeltop [N]` / `$ctop` | Channel-specific top karma (default 10) | `$channeltop` |
| `$channelbottom [N]` / `$cbottom` | Channel-specific bottom karma | `$channelbottom` |
| `$setkarma <nick> <value>` | Set karma (channel ops only) | `$setkarma m0n 100` |

### Cooldowns
- **10-minute cooldown** per user per channel between karma changes
- Fun themed response messages with emojis

---

## 🧩 trivia — Trivia Game

A full-featured multi-player trivia game with categories, progressive hints, scoring, streaks, and persistent statistics.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$trivia [N]` | Start a trivia game with N questions (default 100) | `$trivia 20` |
| `$strivia` | Stop the current trivia game | `$strivia` |
| `$triviastats [nick]` / `$tstats` | View trivia stats for yourself or another player | `$triviastats m0n` |
| `$triviatop` / `$ttop` | Top 10 players in this channel | `$triviatop` |
| `$triviatopserver` / `$ttopserver` | Top 10 players across the entire server | `$triviatopserver` |

### How It Works
1. Bot asks a question with optional category
2. Progressive hints are revealed over time (letters gradually unmasked)
3. Type the answer in chat — first correct answer wins!
4. Points awarded with streak bonuses for consecutive correct answers
5. After N questions or inactivity, final scoreboard is displayed

### Supporting Files
- `questions.json` — Question bank with categories
- `trivia_game.py` — Core game logic and hint generation engine
- `trivia_db.py` — SQLite persistence for stats and game history

---

## 🌤️ weather — Weather Forecasts

Full weather system powered by [PirateWeather API](https://pirateweather.net). Register your location for quick lookups, get forecasts, alerts, and even space weather!

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$w <location>` | Current weather for a location | `$w New York` |
| `$w` | Current weather for your registered location | `$w` |
| `$w -n <user>` | Current weather for another user's location | `$w -n m0n` |
| `$f <location>` | 3-day forecast | `$f Chicago` |
| `$ef <location>` | Extended 8-day forecast (sent via PM) | `$ef London` |
| `$wa` | Weather alerts for your registered location (PM) | `$wa` |
| `$wa -n <user>` | Weather alerts for another user's location | `$wa -n m0n` |
| `$space` / `$spaceweather` | Space weather report (solar storms, etc.) | `$space` |
| `$register_location <location>` | Register your default location | `$register_location Dallas, TX` |
| `$change_location <location>` | Change your registered location | `$change_location Austin, TX` |
| `$unregister_location` | Unregister your location | `$unregister_location` |
| `$helpweather` | Weather help (sent via PM) | `$helpweather` |

### Features
- Color-coded temperatures (blue → red based on °C)
- Wind direction with compass bearings
- UV index, humidity, visibility
- Active weather alerts sent via PM to avoid channel spam
- Space weather: solar wind, geomagnetic storms, aurora forecast
- Graceful error reporting if the PirateWeather API is unreachable

---

## 📈 stock — Stock Lookup

Look up stocks by ticker symbol or company name with price and historical performance.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$stock <symbol or name>` | Look up a stock | `$stock AAPL` |
| `$stock <company name>` | Search by company name | `$stock Apple` |

### Example Output
```
📈 Apple Inc. (AAPL)  💵 $189.84  🟢 24h: +1.23%  🟢 7d: +2.45%  🔴 30d: -0.87%  🟢 6m: +15.32%  🟢 1y: +28.91%
```

### Dependencies
- `yfinance`

---

## 🗳️ voting — Channel Polls

Create timed polls with multiple options. Requires halfop (`%`) or above to create polls.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$vote Q:<question> A1:<opt1> A2:<opt2> [A3:...] T:<duration>` | Create a poll | `$vote Q:Best OS? A1:Linux A2:Windows A3:macOS T:24h` |
| `$v <number>` / `$castvote` | Cast your vote | `$v 1` |
| `$votestats` / `$vstats` / `$voteresults` | Show current poll statistics | `$votestats` |
| `$endvote` | End the poll early (creator or halfop+) | `$endvote` |
| `$votehelp` | Full help guide (PM) | `$votehelp` |

### Duration Formats
- `30m` — 30 minutes
- `24h` — 24 hours
- `2d` — 2 days

### Features
- Visual progress bars in results
- Emoji numbered options
- Automatic timer-based poll ending
- Vote change prevention
- Results stored in SQLite

---

## 📊 monitor — Channel Statistics

Track detailed activity per user per channel with leaderboards and per-stat rankings. Automatically tracks lines, words, actions, kicks, bans, joins, parts, quits, splits, and nick changes.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$stats [nick] [#channel]` | Show stats for a user | `$stats m0n` |
| `$rank [field] [#channel]` | Top 10 users for a specific stat (default: lines) | `$rank words` |
| `$chanstats [#channel]` | Total aggregate stats for the whole channel | `$chanstats` |
| `$chanrank` | Top 10 channels by total activity | `$chanrank` |
| `$statshelp` | Full command reference (PM) | `$statshelp` |

### Admin Commands

| Command | Privilege | Description | Example |
|---------|-----------|-------------|---------|
| `$zapstats [#channel]` | Owner only | Wipe all stats for a channel | `$zapstats #chat` |
| `$zapnick <nick> [#channel]` | Op+ | Remove a single nick's stats | `$zapnick spammer` |

### Tracked Stats
- 💬 Lines, 📝 Words, 🎭 Actions
- 🦵 Kicks, 🔨 Bans
- 🚪 Joins, 👋 Parts, 💥 Splits, 🚫 Quits, 🔄 Nick changes
- 🥇🥈🥉 Medal emojis on top-3 leaderboard positions
- Stats auto-save on an interval and on bot shutdown

---

## 🚔 curse — Verbal Morality Statute

*"You are fined one credit for a violation of the Verbal Morality Statute."* — Demolition Man

An automatic profanity fine system inspired by the Demolition Man Verbal Morality Statute. When enabled in a channel, the bot monitors all messages for banned words and issues a randomized §X.X fine citation with a colourful message.

### Features
- **Disabled by default** — must be explicitly enabled per channel
- 50 unique fine messages across 6 flavour categories (classic booth, authority, cheerful, bureaucratic, dramatic, robotic, pop-culture)
- All messages reference a specific Verbal Morality Statute section code
- Two-tier word matching: short ambiguous words (`ass`, `hell`, etc.) require a word boundary; explicit profanity matches anywhere inside compound words (e.g. `sheepfucker` → `fuck`)
- Per-channel toggle stored in the bot database — survives restarts

### Commands

| Command | Who | Description |
|---------|-----|-------------|
| `$curse on` | Halfop+ / Admin | Enable fining in this channel |
| `$curse off` | Halfop+ / Admin | Disable fining in this channel |
| `$curse` | Anyone | Check whether fining is currently enabled |

### Permissions
- Requires **halfop or above** (`%`, `@`, `&`, `~`) in the channel, **or** bot admin/owner status
- The bot issues fines automatically when enabled — no trigger command needed

### Example Fine Messages
```
[VMS § 2.1] You are hereby fined one credit for a violation of the Verbal Morality Statute. Watch your language, citizen!
[VMS § 4.7] A fine has been issued for use of language prohibited under Statute § 4.7. Your record has been noted. 📋
[VMS § 3.14] 🚨 VERBAL MORALITY VIOLATION DETECTED 🚨 Infraction logged under § 3.14. Have a scenic day! ☀️
```

---

## 🤦 facepalm — Facepalm Reactions

When someone does `/me facepalms` in chat, the bot replies with a random facepalm reaction.

### Trigger
```
/me facepalms
/me facepalmed
```

### Example Output
```
m0n facepalms so hard the desk breaks (－‸ლ)
m0n buries face into hands (ಠ_ಠ) 🤦
m0n facepalms with the force of a thousand suns ☀️ (－‸ლ) ☀️
```

### Cooldown
- **15 seconds** per channel

---

## (╯°□°）╯︵ ┻━┻ tableflip — Table Flip Animation

Plays a dramatic table flip animation sequence in chat.

### Commands

| Command | Description |
|---------|-------------|
| `$flip` | Play a 4-step table flip animation |

### Output Sequence
```
╭∩╮( º.º )╭∩╮
┬─┬ノ( º _ ºノ)
o(*≧▽≦)ツ┏━┓
(╯°□°）╯︵ ┻━┻
```

### Cooldown
- **60 seconds** per user per channel

---

## 🔑 opme — Self-Promotion

Allows authorized users to promote themselves (or others) to channel operator.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$promoteme [nick]` | Promote yourself or a target user | `$promoteme` |

### Configuration (`default.cfg`)
```ini
[promoteme]
require_admin = true
require_bot_op = true
modes = +o
allow_in_all_channels = true
cooldown_seconds = 60
temporary_promotion = false
promotion_duration = 300
```

### Features
- Admin-only restriction (configurable)
- Per-user and per-channel cooldowns
- Optional temporary promotions (auto-reverts after duration)
- Customizable mode string (`+o`, `+v`, etc.)

---

## 🚪 join — Bot Channel Join

Owner-only command to make the bot join a channel.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$join #channel [key]` | Make the bot join a channel | `$join #newchannel` |
| `$join #channel secretkey` | Join a key-protected channel | `$join #private mykey` |

---

## 🎬 youtube_titles — YouTube Link Titles

Automatically fetches and displays the title and author of YouTube links posted in chat.

### Trigger
Any YouTube URL posted in chat is automatically detected.

### Example
```
User: check this out https://www.youtube.com/watch?v=dQw4w9WgXcQ
Bot:  YouTube: Rick Astley - Never Gonna Give You Up — Rick Astley
```

---

## 🖥️ CLI & Demo Scripts

### `cli_trivia.py`
Command-line trivia runner for testing outside of IRC.

```bash
python3 cli_trivia.py -i --num 10 --shuffle
python3 cli_trivia.py -f questions.json --category Geography
```

### `demo_trivia.py`
Demonstrates hint generation, category listing, and sample questions.

```bash
python3 demo_trivia.py
```

---

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lord3nd3r/sopel-scripts.git
   ```

2. **Copy scripts to your Sopel plugins directory:**
   ```bash
   cp sopel-scripts/*.py ~/.sopel/scripts/
   cp sopel-scripts/questions.json ~/.sopel/scripts/
   ```

3. **Install Python dependencies:**
   ```bash
   pip install sopel requests yfinance
   ```

4. **Configure your bot** — see the [Configuration](#-configuration) section and individual script sections above.

5. **Restart Sopel:**
   ```bash
   sopel restart
   ```

---

## ⚙️ Configuration

Most scripts work out of the box. Scripts with required configuration:

| Script | Config Section | Required Settings |
|--------|---------------|-------------------|
| `ai-grok.py` | `[grok]` | `api_key` (xAI API key) |
| `weather.py` | — | API key is hardcoded (PirateWeather) |
| `opme.py` | `[promoteme]` | Various options (see script section) |
| `mug.py` | `[mug_game]` | `enabled = true` |
| `moo.py` | `[moo]` | Optional tuning params |
| `monitor.py` | `[channelstats]` | `channels`, `db_path` |
| `voting.py` | `[voting]` | `db_path` (optional) |

---

## 📝 License

These scripts are provided as-is for personal use.

---

*Made with ❤️ for the IRC community*
