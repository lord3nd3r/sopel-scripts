# 🤖 Sopel IRC Bot Scripts

A collection of custom [Sopel](https://sopel.chat/) IRC bot plugins for fun, utility, and community engagement.

> **Quick reference:** See [commands.md](commands.md) for per-script command docs with examples.

---

## 📋 Table of Contents

- [AI & Chat](docs/ai-multi.md)
- [Bartender](docs/beer.md)
- [Weed & Trippy Commands](docs/weed.md)
- [Mug Game](docs/mug.md)
- [Bot Admin](docs/botadmin.md)
- [Oper Scanner](docs/operscan.md)
- [Moo Counter](docs/moo.md)
- [Karma](docs/karma.md)
- [Trivia](docs/trivia.md)
- [Weather](docs/weather.md)
- [Stocks](docs/stock.md)
- [Voting](docs/voting.md)
- [Channel Monitor](docs/monitor.md)
- [Verbal Morality](docs/curse.md)
- [Facepalm](docs/facepalm.md)
- [Table Flip](docs/tableflip.md)
- [PromoteMe](docs/opme.md)
- [Join](docs/join.md)
- [YouTube Titles](docs/youtube_titles.md)
- [URL Titles](docs/url_titles.md)
- [Auto Voice](docs/autovoice.md)
- [Auto Op](docs/autoop.md)
- [Antiflood](docs/antiflood.md)
- [Anti-Spam](docs/antispam.md)
- [JPQ Flood Protection](docs/jpq.md)
- [Markov Chain](docs/markov.md)
- [Wiki Search](docs/wiki.md)
- [Quotes](docs/quote.md)
- [Typo Correction (sed)](docs/fix.md)
- [Rizon Help](docs/rizonhelp.md)
- [Tell](docs/tell.md)
- [Seen](docs/seen.md)
- [Installation](#-installation)
- [Configuration](#-configuration)

---

## 🧠 ai-multi — Multi-backend AI Chatbot (v6.0)

An AI chatbot supporting **xAI Grok**, local **Ollama**, and OpenAI-compatible APIs. The bot responds when mentioned by name, handles emotes/actions, supports optional web search, and maintains per-user conversation history.

### Features
- Responds conversationally when addressed by nick
- Reacts to `/me` actions (pets, hugs, pokes, etc.) with fun emote replies
- **Full channel awareness** — sees ALL channel activity including `$` commands (`$bet`, `$mug`, `$coins`, `$top5`, etc.) and the bot's own plugin outputs (game results, payouts, mug outcomes)
- **Cross-plugin context** — the AI knows it runs other scripts and treats its own output as things it said/did, referencing game events naturally in conversation
- **Automatic web search** for news, scores, current events, and time-sensitive queries when `search_backend = grok`
- **Configurable chat backends**: Grok, Ollama, or any OpenAI-compatible API
- Per-user conversation history stored in SQLite
- **Persistent memory** — users can tell the bot to "remember" facts permanently in SQLite; facts survive restarts and are always included in AI context
- **Auto-learning** — periodically extracts facts about active users from conversation (semaphore-gated, max 2 concurrent background tasks)
- **Review mode** — summarize what has been discussed in channel (persisted to DB across restarts)
- **Time/date awareness** with per-user timezone and format preferences
- Admin commands via PM
- Heuristic intent detection to avoid responding to incidental mentions
- **Per-user rate limiting** — each user has an independent cooldown, so one user's question doesn't block another
- Context window: up to 150 lines / 6,000 char budget for background channel context
- **v6.0 Stability**: Bounded TTL caches for all ephemeral data, proper `shutdown()` lifecycle hook, dict-based worker tasks, semaphore-gated background threads, no API key leakage in logs

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `BotNick: <message>` | Talk to the bot | `Grok: what's the weather like?` |
| `<message> BotNick` | Also triggers a response | `hey what do you think Grok` |
| `/me pets BotNick` | Emote interaction — bot reacts | `/me hugs Grok` |
| `BotNick: remember <fact>` | Save a fact permanently | `Grok: remember I live in Florida` |
| `BotNick: forget <fact>` | Remove a saved fact | `Grok: forget about Florida` |
| `BotNick: forget everything` | Clear all saved facts | `Grok: forget everything` |
| `BotNick: what do you remember about me` | List saved facts | `Grok: what do you remember about me` |
| `$grokreset` | Reset your conversation history | `$grokreset` |
| `$grokreset channel` | Reset all channel history (admin/op) | `$grokreset channel` |
| `$ai <on\|off>` | Enable/disable AI for the channel (admin/op) | `$ai off` |
| `$talkback <on\|off>` | Enable/disable chime-ins (admin/op) | `$talkback off` |
| `$testemote` | Verify emote plugin is loaded | `$testemote` |
| `$scheck [nick]` | Scan last 100 messages for incoherent content (op/admin) | `$scheck SomeUser` |
| `$scheck #channel [nick]` | Same, but from PM (admin only) | `$scheck #preppers SomeUser` |
| `$skick <nick> <#channel>` | Kick a user (op/admin) | `$skick troll #chat` |
| `$skban <nick> <#channel>` | Kick-ban a user (op/admin) | `$skban troll #chat` |

### 🔍 Web Search (Automatic)

The bot **automatically** uses live web search when it detects that your question is about something time-sensitive or factual. There is no special command — just ask naturally and the bot decides whether to search.

**Trigger keywords** (any of these in your message activates search):

| Category | Keywords |
|----------|----------|
| News & Events | `news`, `latest`, `recent`, `today`, `yesterday`, `tonight`, `this week`, `this month`, `current events`, `headlines`, `breaking`, `update` |
| Sports | `score`, `results`, `standings`, `who won`, `who is winning` |
| Finance | `stock price`, `price of`, `worth`, `market`, `stock`, `stocks`, `crypto`, `bitcoin`, `btc`, `ethereum`, `eth` |
| Weather & Disasters | `weather`, `forecast`, `drought`, `flooding`, `hurricane`, `tornado`, `earthquake`, `wildfire` |
| People & Events | `who died`, `who is`, `is ___ dead`, `did ___ happen`, `election`, `poll` |
| Factual Queries | `what is`, `where is`, `when is/was/did`, `how many/much/long/far/old/tall/big/fast`, `how bad`, `how severe`, `status of`, `population`, `gdp`, `economy`, `inflation`, `interest rate` |
| Temporal | `currently`, `right now`, `at the moment` |
| General | `search`, `whats happening`, `tell me about`, `what do you know about`, `look up`, `find out` |

**Examples:**
```
Grok: what's the latest news today?
Grok: who won the NBA game last night?
Grok: what's the stock price of AAPL?
Grok: what is the price of bitcoin?
Grok: how bad is the drought in Florida?
Grok: search for the election results
Grok: what's the weather forecast for tomorrow?
Grok: tell me about the latest earthquake
```

> **Note:** If the web search API fails, the bot automatically falls back to answering from its training data.

> **Safety net:** If the model attempts to call a tool that wasn't provided (outputting raw XML), the bot automatically strips the garbage, retries the request with web search enabled, and returns a real answer. If the retry also fails, it tells the user to try again instead of outputting gibberish.

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

### 🎭 Dynamic Personalities

The bot supports **dynamic personality changes** that can be set on-the-fly during conversation. Personalities are stored in memory and persist until explicitly reset.

**Default behavior:** Personality commands apply **per-user** (only to the person who requested it) unless you explicitly specify channel-wide.

#### Per-User Personalities (Default)

By default, when you tell the bot to change personality, it only affects **you**:

**Examples:**
```
Grok: speak Russian
Grok: be angry and insulting
Grok: act like a pirate
Grok: role play as rick from rick and morty
```

In these cases, the bot will use that personality only when responding to you. Other users see the default personality.

#### Channel-Wide Personalities

To make a personality affect **everyone** in the channel, explicitly say "in this channel" or similar:

**Trigger phrases:** Add any of these to your command:
- `in this channel`
- `in the channel`
- `for everyone`
- `for the whole channel`
- `channel-wide`

**Examples:**
```
Grok: role play as rick in this channel
Grok: act like a pirate for everyone
Grok: be a drill sergeant in the channel
```

#### Targeting Another User

Set a personality for how the bot talks to a **specific other user**:

**Syntax:** `speak to <nick> like <description>`

**Examples:**
```
Grok: speak to burnout like you're from alberta
Grok: talk to End3r like a drill sergeant
Grok: reply to SoulCareer like a philosopher
```

**Priority:** User-specific targets > Per-user settings > Channel-wide settings > Config default

#### Resetting Personalities

Clear both channel and user personalities:

**Trigger phrases:**
- `stop roleplaying`, `stop roleplay`
- `reset personality`
- `be normal again`
- `go back to normal`
- `clear personality`

**Example:**
```
Grok: stop roleplaying
```

> **Note:** Anyone in the channel can set or reset personalities, not just admins. Personalities are stored in memory and cleared on bot restart.

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
[ai_multi]
api_key = your-xai-api-key
chat_backend = grok
search_backend = grok
model = grok-4.3
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

A virtual bartender with a tipping economy integrated with the **mug** game's coin system.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$beer [nick]` | Serve a random beer (5 🪙) | `$beer m0n` |
| `$shot [nick]` | Serve a random shot (7 🪙) | `$shot` |
| `$whiskey [nick]` / `$whisky` | Serve a fine whiskey (12 🪙) | `$whiskey JohnDoe` |
| `$vodka [nick]` | Serve a premium vodka (10 🪙) | `$vodka` |
| `$rum [nick]` | Serve a spiced rum (10 🪙) | `$rum` |
| `$tequila [nick]` | Serve a fine tequila (10 🪙) | `$tequila` |
| `$gin [nick]` | Serve a botanical gin (10 🪙) | `$gin` |
| `$brandy [nick]` / `$cognac` | Serve brandy / cognac (12 🪙) | `$brandy` |
| `$margarita [nick]` / `$marg` | Serve a margarita (9 🪙) | `$margarita` |
| `$sake [nick]` | Serve sake (9 🪙) | `$sake` |
| `$liqueur [nick]` / `$cordial` | Serve a liqueur (8 🪙) | `$liqueur` |
| `$wine [nick]` | Serve a glass of wine (8 🪙) | `$wine` |
| `$cava [nick]` / `$prosecco` | Serve a sparkling Cava (8 🪙) | `$cava` |
| `$mead [nick]` | Serve a horn of mead (7 🪙) | `$mead` |
| `$magners [nick]` | Serve a Magners cider (6 🪙) | `$magners` |
| `$drink [nick]` | Serve a mixed drink (10 🪙) | `$drink` |
| `$mocktail [nick]` / `$virgin` | Serve a mocktail (4 🪙) | `$mocktail` |
| `$coffee [nick]` / `$caffeine` | Serve coffee (3 🪙) | `$coffee` |
| `$decaf [nick]` / `$decaffeinated` | Serve decaf coffee (3 🪙) | `$decaf` |
| `$tea [nick]` / `$cuppa` | Serve tea (3 🪙) | `$tea` |
| `$water [nick]` / `$hydrate` | Serve water (free!) | `$water` |
| `$pizza [nick]` | Serve a pizza (15 🪙) | `$pizza` |
| `$appetizer [nick]` / `$snack` / `$food` | Serve an appetizer (8 🪙) | `$appetizer` |
| `$surprise [nick]` / `$random` | Random item from the menu (Varies) | `$surprise` |
| `$tip <nick> <amount>` | Tip another user (deducts from your coins) | `$tip m0n 50` |
| `$barcash` / `$balance` | Check your coin balance | `$barcash` |
| `$toptip` | Top 5 most tipped bartenders | `$toptip` |
| `$barhelp` | Full help menu (sent via PM) | `$barhelp` |

### Admin Commands (PM only)

| Command | Description | Example |
|---------|-------------|---------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's coin balance | `$adjbal m0n +100` |
| `$barreset <nick>` | Reset a user's balance to 1,000 coins | `$barreset m0n` |
| `$barreset all confirm` | Reset ALL balances and clear tips | `$barreset all confirm` |

### Economy
- Coins are shared with the **mug** game's unified coin economy.
- New users receive **1,000 starting coins** on their first order.
- Every user receives a **100 coin daily bonus** once per 24 hours (applied when checking tab or ordering).

---

## 🌿 weed — Smoking & Psychedelic Sessions

Share lighthearted party messages with themed countdowns, gifts, and action messages. Features 15 substances, each with unique theming, emojis, and color schemes.

### Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed [nick]` | — | Share a weed-themed gift or session 🌿 |
| `$bong [nick]` | — | Bong rip session with water/ice countdown 🫧 |
| `$joint [nick]` | — | Roll up and spark a joint 📜 |
| `$keef [nick]` | `$kief` | Sprinkle some keef ✨ |
| `$toke [nick]` | — | Take a bowl/pipe toke 🌬️ |
| `$edible [nick]` | `$edibles` | Share an edible 🍪 |
| `$dab [nick]` | `$dabs` | Take a dab 💎🔥 |
| `$blunt [nick]` | — | Spark a blunt 🍂 |
| `$vape [nick]` | — | Discreet vapor hit 🔌☁️ |
| `$hash [nick]` | — | Old-world hash 🟤 |
| `$munchies [nick]` | — | Share snacks 🍕🍿 |
| `$trip [nick]` | — | DMT breakthrough experience 👽🌀 |
| `$shrooms [nick]` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid [nick]` | `$lsd` | Acid trip with fractal visuals 🌈 |
| `$peyote [nick]` | `$mescaline` | Peyote desert vision quest 🌵 |
| `$pass <nick>` | — | Take a hit and pass rotation (requires target in channel) |
| `$weedhelp` | — | PM a complete command reference card |

### Behavior
- **With a target:** Sends an action message gifting the target a random item (target must be in the channel)
  ```
  * Bot hands m0n a fat bong rip 🌊
  ```
- **Without a target:** Performs a themed 3-step countdown (6s between each), then posts a random colorful final message.
- **Mid-sentence triggers:** Commands work anywhere in a message, not just at the start (e.g. `I feel the need for $weed`).

### Cooldowns
- **Channel cooldown:** 20 minutes between countdown sessions (shared per channel).
- **Per-user cooldown:** 30 seconds between gift/pass commands (prevent spam).
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
| `$bet <amount>` | Gamble your coins (max 1B per bet) | `$bet 500` |
| `$roll <amount> [type]` | Dice casino — 6 bet types with varying payouts | `$roll 500 lucky7` |
| `$penny` | Penny slot machine — 1 coin per pull, win up to 5,000! | `$penny` |
| `$dollar` | Dollar slot machine — 100 coins per pull, win up to 50,000! | `$dollar` |
| `$roulette <amount> <bet>` | Roulette — red/black/odd/even/high/low/1st/2nd/3rd/0-36 | `$roulette 500 red` |
| `$bj <amount>` | Blackjack vs dealer (then $hit/$stand/$dd) | `$bj 500` |
| `$holdem <amount>` | Texas Hold’em heads-up vs dealer | `$holdem 500` |

**Dice Casino Types (`$roll`):**

| Type | How to Win | Payout |
|------|-----------|--------|
| `high` (default) | Roll 2d6, total 7+ wins | 2x |
| `lucky7` | Roll exactly 7 | 4x |
| `snake` | Snake eyes (1+1) | 30x |
| `field` | Roll 2,3,4,9,10,11,12 | 2x (3x on 2 or 12) |
| `hardway` | Doubles (except snake eyes) | 8x |
| `yolo` | Roll 2 or 12 | 15x |

**Roulette Bets (`$roulette`):**

| Bet | Description | Payout |
|-----|-----------|--------|
| `red` / `black` | Color bet | 2x |
| `odd` / `even` | Parity bet | 2x |
| `high` / `low` | 19-36 / 1-18 | 2x |
| `1st` / `2nd` / `3rd` | Dozens (1-12, 13-24, 25-36) | 3x |
| `0`–`36` | Straight number | 36x |

**Blackjack (`$bj`):**

| Command | Description |
|---------|-------------|
| `$hit` | Draw another card |
| `$stand` | Keep your hand, dealer plays |
| `$dd` | Double down — double bet, one card, auto-stand |

> Natural blackjack pays 2.5x. Regular win pays 2x.

**Texas Hold’em Payouts (`$holdem`):**

| Hand | Payout |
|------|--------|
| Royal Flush | 50x |
| Straight Flush | 25x |
| Four of a Kind | 12x |
| Full House | 6x |
| Flush | 4x |
| Straight | 3x |
| Three/Two/One Pair, High Card | 2x |

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
| `$highscore` | All-time highest balance ever achieved and who held it |

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
| `$uncooldown <nick>` | Clear a user's 30-min flood lockout (admin, PM) |

> **Auto-Voice:** Users with ≥500 coins automatically get +v in configured channels. Dropping below 500 = devoiced. Ops/hops/owners are exempt.

> **High Score Topic:** When the all-time high score is beaten, the bot auto-updates the channel topic in `#mug` with the new record. Self-heals if the marker is removed.

### Bot Player (glitchy)
- The bot participates in the mug game with its own wallet (seeded at 500k coins)
- **Retaliation:** 60% chance to counter-mug you 5–15 seconds after you mug it
- **Proactive:** Randomly mugs top 5 richest players every 30–90 minutes in `#mug`
- Normal odds (50% success, 5–15% steal, 10–25% fail loss) — no god mode

### Channel Rules
- Mug game is **disabled by default** per channel — an admin must `$mugtoggle on`
- Home channel: `#mug` — disabled messages direct players there
- **Admins are exempt from all cooldown timers**
- **Spam protection:** More than 15 commands in 60 seconds triggers a 30-minute casino lockout. Admins can clear it with `$uncooldown <nick>`

### Features
- Wealth-scaled coin collection
- Jail system with bail items
- Passive items (work automatically from inventory) vs. consumable items
- Active item effects (attack bonuses, defense)
- Anti-cheat: NickServ verification, daily give caps, command throttling
- Titles based on wealth level
- Bot player with retaliation and proactive mugging AI
- Comma support in all amount inputs

### Economy Balancing
- **Minimum balance to mug:** Attacker must have ≥ 1% of the victim's wallet (skip for tiny wallets ≤ 100 coins)
- **Scaled mug fee:** 0.1% of attacker balance (min 2 coins) — whales pay more to mug
- **Scaled fail/crit loss caps:** Normal fail cap = max(100k, 5% of your money); Crit fail cap = max(250k, 10% of your money)
- **Bet cap:** Max bet is 1,000,000,000 (1B) to prevent hyperinflation
- **Whale protection:** If victim has > 10k coins, max steal is 25% per mug

---

## 🛠️ botadmin — Bot Admin

Owner and admin-only bot management commands.

### Owner Commands

| Command | Description |
|---------|-------------|
| `$restart` | Restart the bot |
| `$breload <module\|all>` | Reload a plugin or all plugins |
| `$botquit [msg]` | Shut down the bot |
| `$raw <irc line>` | Send a raw IRC command |
| `$botnick <nick>` | Change the bot's nick |

### Admin Commands

| Command | Description |
|---------|-------------|
| `$say <target> <msg>` | Make bot say something |
| `$act <target> <action>` | Make bot do a /me action |
| `$bjoin #channel [key]` | Join a channel |
| `$bpart #channel [msg]` | Leave a channel |
| `$bmode #channel <mode> [nick]` | Set a channel mode |
| `$bothelp` | List all admin commands |

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
| `$karmaflood` | Show flood protection status (halfop+) | `$karmaflood` |
| `$karmaflood <on\|off>` | Enable/disable flood protection (halfop+) | `$karmaflood off` |
| `$karmaflood set <param> <val>` | Tune parameters (`window`, `threshold`, `ban_duration`) | `$karmaflood set threshold 2` |

### Cooldowns
- **10-minute cooldown** per user per channel between karma changes
- Fun themed response messages with emojis

### Arrow Protection
- Arrow-like patterns (`<--`, `-->`, `<++`) are **not treated** as karma changes
- The `++` / `--` operator must immediately follow a word character (letter, digit, or underscore)

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

## 🤦 facepalm — Facepalm Reactions & Shrug

When someone does `/me facepalms` in chat, the bot replies with a random facepalm reaction. When someone does `/me shrugs`, the bot replies with ¯\\_(ツ)_/¯. Also includes `$shrug`.

### Triggers
```
/me facepalms      → random facepalm reaction
/me facepalmed     → random facepalm reaction
/me shrugs         → ¯\_(ツ)_/¯
/me shrugged       → ¯\_(ツ)_/¯
```

### Commands

| Command | Description |
|---------|-------------|
| `$shrug` | Output ¯\\_(ツ)_/¯ |
| `$shrug <nick>` | Direct the shrug at someone |

### Example Output
```
m0n facepalms so hard the desk breaks (－‸ლ)
m0n buries face into hands (ಠ_ಠ) 🤦
m0n facepalms with the force of a thousand suns ☀️ (－‸ლ) ☀️
```

### Cooldown
- **15 seconds** per channel (shared across all triggers)

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

Automatically fetches and displays the title and author of YouTube links posted in chat. Can be toggled on/off per channel.

### Trigger
Any YouTube URL posted in chat is automatically detected.

### Commands
Requires **channel operator** or **bot owner** status.

| Command | Arguments | Description | Example |
|---------|-----------|-------------|---------|
| `$yt` | — | Display current status in channel | `$yt` |
| `$yt` | `on` / `off` | Enable/disable fetching in current channel | `$yt off` |

---

## 🎙️ autovoice — Activity-Based Auto Voice

Automatically voices active users in a channel. Off by default — enable per-channel with `$autovoice on`. Requires the bot to have halfop (`%`) or higher.

### How It Works
- Tracks message counts per user per channel
- After **50 messages**, a user earns `+v` automatically
- **Auto-revoice on rejoin** — users who already earned `+v` are re-voiced within seconds of rejoining
- If a voiced user goes **7 days** without talking, the voice is removed
- Users who already have `+v`, `+h`, `+o`, `+a`, or `+q` are completely ignored
- Background sweep runs every 15 minutes to sync modes

### Commands

| Command | Description |
|---------|-------------|
| `$autovoice on` | Enable autovoice for this channel |
| `$autovoice off` | Disable autovoice for this channel |
| `$autovoice status` | Show state, tracked users, and thresholds |
| `$autovoice reset <nick>` | Clear a user's activity data |
| `$autovoice threshold` | Show current threshold and idle settings |
| `$autovoice check [nick]` | Check progress toward +v |
| `$vcheck` | Check your own autovoice progress |
| `$vcheck <nick>` | Check another user's progress |
| `$vcheck #channel [nick]` | Check progress from PM |

> **Requires:** halfop+ or bot admin to manage. `$vcheck` and `$autovoice check` are available to anyone.

### Data Storage
Activity data is stored in `~/.sopel/autovoice_data.json`.

---

## 🤖 autoop — Auto Op & Modes

Automatically grants `+o`, `+h`, or `+v` to specific users when they join the channel. Modes are managed by authorized admins and saved persistently.

### Commands (Admin Only)

| Command | Description |
|---------|-------------|
| `$aop <nick>` | Add a user to the auto-op (`+o`) list |
| `$dop <nick>` | Remove a user from the auto-op list |
| `$ahop <nick>` | Add a user to the auto-halfop (`+h`) list |
| `$dhop <nick>` | Remove a user from the auto-halfop list |
| `$avoice <nick>` | Add a user to the auto-voice (`+v`) list |
| `$dvoice <nick>` | Remove a user from the auto-voice list |
| `$alist` | List all auto-modes configured for the current channel |

📖 **Full docs:** [docs/autoop.md](docs/autoop.md)

---

## 🛡️ antiflood — Join/Part Flood Protection

Join/part flood protection. Detects and bans users who cycle joins or quits too rapidly in a short window. Off by default per-channel.

### Commands (Admin Only)
- `$flood` — Show status in channel
- `$flood <on|off>` — Enable/disable per-channel
- `$flood set <param> <val>` — Tune parameters (`window`, `threshold`, `duration`, `banmask`)
- `$flood whitelist <add|del|list> [user@host]` — Manage whitelist
- `$flood stats` — Show recent flood actions
- `$flood top` — Show top 5 kicked users
- `$floodtop` — Shortcut for stats top

📖 **Full docs:** [docs/antiflood.md](docs/antiflood.md)

---

## 🛡️ antispam — Anti-Spam Protection

Multi-mode anti-spam kick protection. Detects rate-based spam, unicode art, trigger word matches, copypasta shingles, and includes Grok AI text classification. Off by default.

### Commands (Admin Only)
- `$spam` — Show status in channel
- `$spam <on|off>` — Enable/disable per-channel
- `$spam set <param> <val>` — Tune parameters
- `$spam trigger <add|del|list> <phrase>` — Manage trigger phrases
- `$spam exempt <add|del|list> [nick]` — Manage user exemptions (e.g., game bots)
- `$spam cmdexempt <add|del|list> [prefix]` — Manage command prefix exemptions (e.g., `!bang` for duckhunt)
- `$spam copypasta <status|clear>` — View or clear shingles DB

📖 **Full docs:** [docs/antispam.md](docs/antispam.md)

---

## 🛡️ jpq — JPQ Flood Protection

Join/Part/Quit cycle protection. Detects users who rapidly cycle joins, parts, or quits. Enabled by default.

### Commands (Admin Only)
- `$jpq` — Show status in channel
- `$jpq <on|off>` — Enable/disable per-channel
- `$jpq set <param> <val>` — Tune parameters
- `$jpq whitelist <add|del|list> [user@host]` — Manage whitelist
- `$jpq stats` — Show recent actions

📖 **Full docs:** [docs/jpq.md](docs/jpq.md)

---

## 🔍 operscan — IRC Operator Scanner

PM-only scanner to identify network/server IRC operators in a channel.

### Commands
- `/msg BotNick $operscan #channel` — Scan channel for IRC operators

📖 **Full docs:** [docs/operscan.md](docs/operscan.md)

---

## 🔗 url_titles — URL Title Fetcher

Automatically fetches and displays the HTML `<title>` tag of URLs posted in chat. Skips YouTube domains.

📖 **Full docs:** [docs/url_titles.md](docs/url_titles.md)

---

## 🔧 fix — Typo Correction

Sed-style typo correction plugin (`s/find/replace/`) that records message history and allows users to correct typos in their own or others' messages.

### Usage
- `s/find/replace/` — Correct your own last message
- `Nick: s/find/replace/` — Correct another user's last message

📖 **Full docs:** [docs/fix.md](docs/fix.md)

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

## � markov — Markov Chain Chatbot

Markov chain chatbot that learns from channel messages and generates random sentences by chaining word trigrams with weighted probabilities. Originally by **ComputerTech**, updated by **End3r**.

### Features
- Learns silently from all channel messages, building a per-channel "brain"
- Generates sentences by walking trigram chains weighted by frequency
- Auto-trigger mode — bot randomly speaks based on a configurable percentage
- Seed word support — start generation from a specific word
- Cross-channel generation — use one channel's brain in another
- Bulk log import to bootstrap the brain
- Output capped at 440 characters for IRC safety
- URLs and very short messages are automatically filtered from learning

### Admin Commands (Channel Op)

| Command | Description |
|---------|-------------|
| `$markovon` | Enable Markov learning in the channel |
| `$markovon <0-100>` | Enable + set auto-trigger chance |
| `$markovoff` | Disable Markov entirely |
| `$markovchance <0-100>` | Set auto-trigger percentage |
| `$clearmarkov` | Wipe the brain for this channel (owner only) |
| `$markovlog <url>` | Import a text log to seed the brain |

### User Commands

| Command | Description |
|---------|-------------|
| `$markov` | Generate a random sentence |
| `$markov <word>` | Generate starting from a seed word |
| `$markovfor <#channel>` | Generate using another channel's brain |
| `$markovfor <#channel> <word>` | Same, with a seed word |

📖 **Full docs:** [docs/markov.md](docs/markov.md)

---

## 🔍 wiki — Wiki Search

Search Grokepedia and Wikipedia directly from IRC.

| Command | Description |
|---------|-------------|
| `$wiki <term>` | Search for a term |

📖 **Full docs:** [docs/wiki.md](docs/wiki.md)

---

## 💬 quote — Channel Quote Database

Save and search funny or memorable things said in the channel.

| Command | Description |
|---------|-------------|
| `$quote add <nick> <text>` | Add a new quote |
| `$quote search <term>` | Search for a quote |
| `$quote` | Get a random quote |

📖 **Full docs:** [docs/quote.md](docs/quote.md)

---

## 🆘 rizonhelp — Rizon Network Help

Quick access to Rizon IRC network help topics and FAQ.

| Command | Description |
|---------|-------------|
| `$rhelp` | List topics |
| `$rhelp <topic>` | Get detailed help |

📖 **Full docs:** [docs/rizonhelp.md](docs/rizonhelp.md)

---

## 📬 tell — Offline Messages

Leave messages for users who aren't online. Delivered via PM when they next speak.

| Command | Description |
|---------|-------------|
| `$tell <nick> <message>` | Leave a message for `<nick>` |
| `$showtells` | Retrieve your own pending messages immediately |

📖 **Full docs:** [docs/tell.md](docs/tell.md)

---

## 👁️ seen — Last Seen Tracker

Tracks and reports the last time a user was seen speaking in a channel.

| Command | Description |
|---------|-------------|
| `$seen <nick>` | Report when `<nick>` was last seen and what they said |

📖 **Full docs:** [docs/seen.md](docs/seen.md)

---


## �📦 Installation

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
| `ai-multi.py` | `[ai_multi]` | `api_key` for Grok, or configure Ollama/OpenAI-compatible backend |
| `weather.py` | — | API key is hardcoded (PirateWeather) |
| `opme.py` | `[promoteme]` | Various options (see script section) |
| `mug.py` | `[mug_game]` | `enabled = true` |
| `markov.py` | — | No config needed — uses `bot.db` |
| `moo.py` | `[moo]` | Optional tuning params |
| `monitor.py` | `[channelstats]` | `channels`, `db_path` |
| `voting.py` | `[voting]` | `db_path` (optional) |

---

## 📝 License

These scripts are provided as-is for personal use.

---

*Made with ❤️ for the IRC community*
