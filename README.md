# 🤖 Sopel IRC Bot Scripts

A collection of custom [Sopel](https://sopel.chat/) IRC bot plugins for fun, utility, and community engagement.

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
- **Review mode** — summarize what's been discussed in channel
- **Time/date awareness** with per-user timezone and format preferences
- Admin commands via PM
- Heuristic intent detection to avoid responding to incidental mentions

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `BotNick: <message>` | Talk to the bot | `Grok: what's the weather like?` |
| `<message> BotNick` | Also triggers a response | `hey what do you think Grok` |
| `/me pets BotNick` | Emote interaction — bot reacts | `/me hugs Grok` |
| `!grokreset` | Reset your conversation history | `!grokreset` |
| `!grokreset channel` | Reset all channel history (admin/op) | `!grokreset all` |
| `!testemote` | Verify emote plugin is loaded | `!testemote` |

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

Ask the bot to summarize or give its opinion on what's been discussed in the channel. Review mode collects recent messages from **all users** in the channel and generates a brief, opinionated summary.

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

The bot reacts to `/me` actions and emote-style messages directed at it. Responses vary and avoid repetition.

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
| `!beer [nick]` | Serve a random beer (🍺 $5) | `!beer m0n` |
| `!shot [nick]` | Serve a random shot (🥃 $7) | `!shot` |
| `!whiskey [nick]` | Serve a fine whiskey (🥃 $12) | `!whiskey JohnDoe` |
| `!wine [nick]` | Serve a glass of wine (🍷 $8) | `!wine` |
| `!magners [nick]` | Serve a Magners cider (🍎 $6) | `!magners` |
| `!drink [nick]` | Serve a mixed drink (🍹 $10) | `!drink` |
| `!mocktail [nick]` | Serve a mocktail (🍹 $4) | `!mocktail` |
| `!coffee [nick]` | Serve coffee (☕ $3) | `!coffee` |
| `!tea [nick]` | Serve tea (🍵 $3) | `!tea` |
| `!water [nick]` | Serve water (💧 free!) | `!water` |
| `!pizza [nick]` | Serve a pizza (🍕 $15) | `!pizza` |
| `!appetizer [nick]` | Serve an appetizer (🍽️ $8) | `!appetizer` |
| `!surprise [nick]` | Random item from the menu (🎉) | `!surprise` |
| `!tip <nick> <amount>` | Tip another user | `!tip m0n 20` |
| `!barcash` | Check your current balance | `!barcash` |
| `!toptip` | Top 5 most tipped bartenders | `!toptip` |
| `!barhelp` | Full help menu (sent via PM) | `!barhelp` |

### Admin Commands (PM only)

| Command | Description | Example |
|---------|-------------|---------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's balance | `$adjbal m0n +100` |
| `$barreset <nick>` | Reset a user's balance to $100 | `$barreset m0n` |
| `$barreset all confirm` | Reset ALL balances | `$barreset all confirm` |

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
| `!weed [nick]` | — | Share a weed-themed gift or session 🌿 |
| `!bong [nick]` | — | Bong rip session with water/ice countdown 🫧 |
| `!joint [nick]` | — | Roll up and spark a joint 📜 |
| `!keef [nick]` | `!kief` | Sprinkle some keef ✨ |
| `!trip [nick]` | — | DMT breakthrough experience 👽🌀 |
| `!shrooms [nick]` | `!mushrooms` | Mushroom trip 🍄 |
| `!acid [nick]` | `!lsd` | Acid trip with fractal visuals 🌈 |
| `!peyote [nick]` | `!mescaline` | Peyote desert vision quest 🌵 |

### Behavior
- **With a target:** Sends an action message gifting the target a random item
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

### Cooldowns
- **Channel cooldown:** 20 minutes between countdown sessions (does not apply to gift actions)
- **Per-user cooldown:** 30 seconds between gift commands (does not apply to countdowns)

---

## 💰 mug — Coin, Mugging & Gambling Game

A full IRC economy game with coins, mugging, betting, bounties, a shop, and an item system. Includes anti-cheat measures and NickServ identity verification.

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$coins` | Collect your coins (scaled by wealth) | `$coins` |
| `$balance [nick]` | Check your (or someone's) balance | `$balance m0n` |
| `$give <nick> <amount>` | Give coins to another user | `$give m0n 500` |

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
| `$use <item>` | Use an item from inventory (PM) | `$use bail` |

### Leaderboards

| Command | Description |
|---------|-------------|
| `$top5` | Top 5 richest users |
| `$top10` | Top 10 richest users |

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
| `$mugtoggle [on\|off]` | Enable/disable per-channel (admin) |

### Features
- Wealth-scaled coin collection
- Jail system with bail items
- Active item effects (attack bonuses, defense)
- Anti-cheat: NickServ verification, daily give caps, command throttling
- Titles based on wealth level

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
| `.moocount` | `.mymoo`, `.moos` | Check your moo count |
| `.mootop` | `.topmoo` | Global moo leaderboard |
| `.mootopchan` | `.chanmootop`, `.topmoochan` | Per-channel leaderboard |
| `.totalmoo` | `.moostats` | Global and channel moo totals |
| `.mooreset` | — | Reset a user's moo count (admin only) |
| `.moohelp` | `.aboutmoo` | Help info sent via PM |

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
| `.karma <nick>` | Show channel + global karma for a user | `.karma m0n` |
| `.karma` | Show full command list (PM) | `.karma` |
| `.karmatop [N]` | Top N users by karma (default 5) | `.karmatop 10` |
| `.karmabottom [N]` | Bottom N users by karma | `.karmabottom 5` |
| `.channeltop [N]` | Channel-specific top karma (default 10) | `.channeltop` |
| `.channelbottom [N]` | Channel-specific bottom karma | `.channelbottom` |
| `.setkarma <nick> <value>` | Set karma (channel ops only) | `.setkarma m0n 100` |

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
| `$triviastats [nick]` | View trivia stats for yourself or another player | `$triviastats m0n` |
| `$triviatop` | Top 10 players in this channel | `$triviatop` |
| `$triviatopall` | Top 10 players across the entire server | `$triviatopall` |

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
| `.w <location>` | Current weather for a location | `.w New York` |
| `.w` | Current weather for your registered location | `.w` |
| `.w -n <user>` | Current weather for another user's location | `.w -n m0n` |
| `.f <location>` | 3-day forecast | `.f Chicago` |
| `.ef <location>` | Extended 8-day forecast (sent via PM) | `.ef London` |
| `.wa` | Weather alerts for your registered location (PM) | `.wa` |
| `.wa -n <user>` | Weather alerts for another user's location | `.wa -n m0n` |
| `.sw` | Space weather report (solar storms, etc.) | `.sw` |
| `.wreg <location>` | Register your default location | `.wreg Dallas, TX` |
| `.wchange <location>` | Change your registered location | `.wchange Austin, TX` |
| `.wunreg` | Unregister your location | `.wunreg` |
| `.whelp` | Weather help (sent via PM) | `.whelp` |

### Features
- Color-coded temperatures (blue → red based on °C)
- Wind direction with compass bearings
- UV index, humidity, visibility
- Active weather alerts sent via PM to avoid channel spam
- Space weather: solar wind, geomagnetic storms, aurora forecast

---

## 📈 stock — Stock Lookup

Look up stocks by ticker symbol or company name with price and historical performance.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `.stock <symbol or name>` | Look up a stock | `.stock AAPL` |
| `.stock <company name>` | Search by company name | `.stock Apple` |

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
| `.vote Q:<question> A1:<opt1> A2:<opt2> [A3:...] T:<duration>` | Create a poll | `.vote Q:Best OS? A1:Linux A2:Windows A3:macOS T:24h` |
| `.v <number>` | Cast your vote | `.v 1` |
| `.votestats` | Show current poll statistics | `.votestats` |
| `.endvote` | End the poll early (creator or halfop+) | `.endvote` |
| `.votehelp` | Full help guide (PM) | `.votehelp` |

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

Track message activity per user per channel with detailed statistics and leaderboards.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `.channelstats` | Show channel activity stats and top chatters | `.channelstats` |
| `.userstats [nick]` | Show stats for a specific user | `.userstats m0n` |

### Admin Commands (PM only)

| Command | Description | Example |
|---------|-------------|---------|
| `.monitor on #channel` | Enable monitoring for a channel | `.monitor on #chat` |
| `.monitor off #channel` | Disable monitoring for a channel | `.monitor off #chat` |
| `.monitor list` | List monitored channels | `.monitor list` |

### Stats Include
- Total messages per user
- First/last seen timestamps
- Messages per hour rate
- Ranked leaderboards

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
| `!flip` | Play a 4-step table flip animation |

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
| `!promoteme [nick]` | Promote yourself or a target user | `!promoteme` |

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
| `.join #channel [key]` | Make the bot join a channel | `.join #newchannel` |
| `.join #channel secretkey` | Join a key-protected channel | `.join #private mykey` |

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
