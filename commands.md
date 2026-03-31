# 📋 Bot Command Reference

Quick reference for all commands. The bot command prefix is **`$`** unless noted otherwise.

---

## Table of Contents

- [AI Chatbot (ai-grok)](#-ai-chatbot-ai-grok)
- [Bartender (beer)](#-bartender-beer)
- [Weed & Tripy (weed)](#-weed--trippy-weed)
- [Coins & Mugging (mug)](#-coins--mugging-mug)
- [Bot Admin (botadmin)](#-bot-admin-botadmin)
- [Moo Counter (moo)](#-moo-counter-moo)
- [Karma (karma)](#-karma-karma)
- [Trivia (trivia)](#-trivia-trivia)
- [Weather (weather)](#-weather-weather)
- [Stocks (stock)](#-stocks-stock)
- [Voting (voting)](#-voting-voting)
- [Channel Stats (monitor)](#-channel-stats-monitor)
- [Verbal Morality (curse)](#-verbal-morality-curse)
- [Facepalm (facepalm)](#-facepalm-facepalm)
- [Table Flip (tableflip)](#-table-flip-tableflip)
- [PromoteMe (opme)](#-promoteme-opme)
- [Join (join)](#-join-join)
- [YouTube Titles (youtube_titles)](#-youtube-titles-youtube_titles)

---

## 🧠 AI Chatbot (ai-grok)

Talks to you when mentioned by name. Uses xAI Grok with web search.

| Command | Who | Description |
|---------|-----|-------------|
| `BotNick: <message>` | Anyone | Talk to the bot |
| `/me pets BotNick` | Anyone | Emote interaction |
| `$grokreset` | Anyone | Reset your conversation history |
| `$grokreset channel` | Op+ / Admin | Reset all channel conversation history |
| `$testemote` | Anyone | Test that the emote plugin is loaded |

**Admin PM commands:**

| Command | Description |
|---------|-------------|
| `$join #channel [key]` | Make bot join a channel |
| `$part #channel` | Make bot leave a channel |
| `$ignore <nick>` | Add nick to ignore list |
| `$unignore <nick>` | Remove nick from ignore list |

---

## 🍺 Bartender (beer)

Virtual bartender with a tip economy. Every user gets a $100 daily credit.

| Command | Cost | Description |
|---------|------|-------------|
| `$beer [nick]` | $5 | Serve a random beer 🍺 |
| `$shot [nick]` | $7 | Serve a random shot 🥃 |
| `$whiskey [nick]` / `$whisky` | $12 | Fine whiskey 🥃 |
| `$wine [nick]` | $8 | Glass of wine 🍷 |
| `$magners [nick]` | $6 | Magners cider 🍎 |
| `$drink [nick]` | $10 | Mixed drink 🍹 |
| `$mocktail [nick]` / `$virgin` | $4 | Mocktail 🍹 |
| `$coffee [nick]` / `$caffeine` | $3 | Coffee ☕ |
| `$tea [nick]` / `$cuppa` | $3 | Tea 🍵 |
| `$water [nick]` / `$hydrate` | Free | Water 💧 |
| `$pizza [nick]` | $15 | Pizza 🍕 |
| `$appetizer [nick]` / `$snack` / `$food` | $8 | Appetizer 🍽️ |
| `$surprise [nick]` / `$random` | Varies | Random menu item 🎉 |
| `$tip <nick> <amount>` | — | Tip another user |
| `$barcash` / `$balance` | — | Check your balance |
| `$toptip` | — | Top 5 most tipped bartenders |
| `$barhelp` | — | Full help guide (PM) |

**Admin PM commands:**

| Command | Description |
|---------|-------------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's balance |
| `$barreset <nick>` | Reset a user's balance to $100 |
| `$barreset all confirm` | Reset ALL balances |

---

## 🌿 Weed & Trippy (weed)

Themed smoke/trip messages. With a target nick = gift message. Without = 3-step countdown.

| Command | Aliases | Description |
|---------|---------|-------------|
| `$weed [nick]` | — | Weed session 🌿 |
| `$bong [nick]` | — | Bong rip with countdown 🫧 |
| `$joint [nick]` | — | Spark a joint 📜 |
| `$keef [nick]` | `$kief` | Sprinkle some keef ✨ |
| `$trip [nick]` | — | DMT breakthrough 👽🌀 |
| `$shrooms [nick]` | `$mushrooms` | Mushroom trip 🍄 |
| `$acid [nick]` | `$lsd` | Acid trip 🌈 |
| `$peyote [nick]` | `$mescaline` | Peyote vision quest 🌵 |

> Channel cooldown: 20 min between countdown sessions. Per-user cooldown: 30 sec between gift commands.

---

## 💰 Coins & Mugging (mug)

IRC economy game with coins, mugging, bounties, a shop, and gambling.

**Core:**

| Command | Description |
|---------|-------------|
| `$coins` | Collect your coins |
| `$balance [nick]` / `$bal` | Check a balance |
| `$give <nick> <amount>` | Give coins to someone |

**Crime & Combat:**

| Command | Description |
|---------|-------------|
| `$mug <nick>` / `$rob` | Rob another user |
| `$bounty <nick> <amount>` | Place a bounty |
| `$bounties` | List active bounties |
| `$jail` | Check jail status |

**Gambling:**

| Command | Description |
|---------|-------------|
| `$bet <amount>` | Gamble coins (slot machine) |
| `$roll <amount> [type]` | 🎲 Dice casino (see types below) |
| `$penny` | 🎰 Penny slot machine — 1 coin per pull, win up to 5,000! |
| `$dollar` | 💵 Dollar slot machine — 100 coins per pull, win up to 50,000! |
| `$roulette <amount> <bet>` | 🎡 Roulette — red/black/odd/even/high/low/1st/2nd/3rd/0-36 |
| `$bj <amount>` | 🃏 Blackjack vs dealer (then $hit/$stand/$dd) |
| `$holdem <amount>` | 🤠 Texas Hold'em heads-up vs dealer |

**Dice Casino Types ($roll):**

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
| `$bj <amount>` | Deal a hand vs the dealer |
| `$hit` | Draw another card |
| `$stand` | Keep your hand, dealer plays |
| `$dd` | Double down — double bet, one card, auto-stand |

> Natural blackjack pays 2.5x. Regular win pays 2x.

**Texas Hold'em Payouts (`$holdem`):**

| Hand | Payout |
|------|--------|
| Royal Flush | 50x |
| Straight Flush | 25x |
| Four of a Kind | 12x |
| Full House | 6x |
| Flush | 4x |
| Straight | 3x |
| Three/Two/One Pair, High Card | 2x |

**Shop & Items:**

| Command | Description |
|---------|-------------|
| `$shop` | View the item shop |
| `$buy <item>` | Buy an item (PM) |
| `$inv` / `$inventory` | View your inventory (PM) |
| `$use <item>` | Use a consumable item (PM) |

**Leaderboards:**

| Command | Description |
|---------|-------------|
| `$top5` | Top 5 richest users |
| `$top10` | Top 10 richest users |
| `$mughelp` | Full help guide (PM) |

**Admin PM commands:**

| Command | Description |
|---------|-------------|
| `$mugadd <nick> <amount>` | Add coins to a user |
| `$mugset <nick> <amount>` | Set a user's balance |
| `$mugtake <nick> <amount>` | Remove coins from a user |
| `$mugreset` | Reset all game data |
| `$mugcleardb confirm` | Delete all DB records |
| `$mugmerge <nick>` | Merge duplicate records |
| `$mugdup <nick>` | List duplicate records |
| `$mugclearbounty <nick>` | Clear all bounties on a nick |
| `$mugtoggle [on\|off]` | Enable/disable per-channel |
| `$godmode <nick>` | Toggle luck override (owner only) |
| `$mugstats` | Show game statistics |

> **Auto-Voice:** Users with ≥500 coins automatically receive +v in configured channels. Drops below 500 = devoiced. Ops/hops/owners are exempt.

---

## 🛠️ Bot Admin (botadmin)

Owner/admin-only bot management commands.

**Owner commands:**

| Command | Description |
|---------|-------------|
| `$restart` | Restart the bot |
| `$breload <module\|all>` | Reload a plugin or all plugins |
| `$botquit [msg]` | Shut down the bot |
| `$raw <irc line>` | Send a raw IRC command |
| `$botnick <nick>` | Change the bot's nick |

**Admin commands:**

| Command | Description |
|---------|-------------|
| `$say <target> <msg>` | Make bot say something |
| `$act <target> <action>` | Make bot do a /me action |
| `$bjoin #channel [key]` | Join a channel |
| `$bpart #channel [msg]` | Leave a channel |
| `$bmode #channel <mode> [nick]` | Set a channel mode |
| `$bothelp` | List all admin commands |

---

## 🐄 Moo Counter (moo)

Say `moo` in chat to increment your counter. Full network leaderboards.

**Auto-triggers:**

| Trigger | Effect |
|---------|--------|
| `moo` (anywhere in message) | +1 moo |
| `/me moos` | +1 moo (no cooldown) |
| `sudo moo` | +10 moos (1/hour/user/channel) |

**Commands:**

| Command | Aliases | Description |
|---------|---------|-------------|
| `$moocount` | `$mymoo` | Your moo count |
| `$mootop` | `$topmoo` | Global moo leaderboard |
| `$mootopchan` | `$chanmootop`, `$topmoochan` | Per-channel leaderboard |
| `$totalmoo` | `$moostats` | Global and channel totals |
| `$moohelp` | `$aboutmoo` | Help (PM) |
| `$mooreset` | — | Reset a user's moos (admin only) |

---

## ⭐ Karma (karma)

Inline `++` / `--` karma system with per-channel and global tracking.

**Inline usage:**

| Syntax | Effect |
|--------|--------|
| `nick++` | Give +1 karma |
| `nick--` | Give -1 karma |
| `nick==` | Check a nick's karma inline |

**Commands:**

| Command | Description |
|---------|-------------|
| `$karma <nick>` | Channel + global karma for a user |
| `$karmatop [N]` / `$ktop` | Top N users globally (default 5) |
| `$karmabottom [N]` / `$kbottom` | Bottom N users globally |
| `$channeltop [N]` / `$ctop` | Top N in this channel (default 10) |
| `$channelbottom [N]` / `$cbottom` | Bottom N in this channel |
| `$setkarma <nick> <value>` | Set karma (channel ops only) |

> Cooldown: 10 min per user per channel between karma changes.

---

## 🧩 Trivia (trivia)

Multi-player trivia with categories, progressive hints, streaks, and stats.

| Command | Description |
|---------|-------------|
| `$trivia [N]` | Start a game with N questions (default 100) |
| `$strivia` | Stop the current game |
| `$triviastats [nick]` / `$tstats` | View stats for yourself or another player |
| `$triviatop` / `$ttop` | Top 10 in this channel |
| `$triviatopserver` / `$ttopserver` | Top 10 across the server |

---

## 🌤️ Weather (weather)

Powered by PirateWeather API. Register your location for quick lookups.

| Command | Description |
|---------|-------------|
| `$w <location>` | Current weather for a location |
| `$w` | Current weather for your saved location |
| `$w -n <user>` | Current weather for another user's location |
| `$f <location>` | 3-day forecast |
| `$ef <location>` | Extended 8-day forecast (PM) |
| `$wa` | Weather alerts for your location (PM) |
| `$wa -n <user>` | Weather alerts for another user's location |
| `$space` / `$spaceweather` | Space weather report |
| `$register_location <location>` | Register your default location |
| `$change_location <location>` | Change your saved location |
| `$unregister_location` | Remove your saved location |
| `$helpweather` | Full help (PM) |

---

## 📈 Stocks (stock)

Look up stocks by ticker or company name via yfinance.

| Command | Description |
|---------|-------------|
| `$stock <symbol or name>` | Look up a stock (`$stock AAPL`, `$stock Apple`) |

---

## 🗳️ Voting (voting)

Create timed polls with multiple options. Requires halfop (`%`) or above to create.

| Command | Description |
|---------|-------------|
| `$vote Q:<question> A1:<opt> A2:<opt> [A3:...] T:<duration>` | Create a poll |
| `$v <number>` / `$castvote` | Cast your vote |
| `$votestats` / `$vstats` / `$voteresults` | Show current poll results |
| `$endvote` | End the poll early (creator or halfop+) |
| `$votehelp` | Full help guide (PM) |

> Duration formats: `30m`, `24h`, `2d`

---

## 📊 Channel Stats (monitor)

Tracks lines, words, actions, kicks, bans, joins, parts, quits, splits, and nick changes per user per channel.

| Command | Description |
|---------|-------------|
| `$stats [nick] [#channel]` | Stats for a user |
| `$rank [field] [#channel]` | Top 10 for a specific stat (default: lines) |
| `$chanstats [#channel]` | Aggregate stats for a channel |
| `$chanrank` | Top 10 channels by activity |
| `$statshelp` | Full command reference (PM) |

**Admin commands:**

| Command | Privilege | Description |
|---------|-----------|-------------|
| `$zapstats [#channel]` | Owner | Wipe all stats for a channel |
| `$zapnick <nick> [#channel]` | Op+ | Remove a single nick's stats |

---

## 🚔 Verbal Morality (curse)

Demolition Man-style Verbal Morality Statute. Disabled by default. When enabled, the bot issues fines for profanity with a randomized §X.X citation from the VMS.

| Command | Who | Description |
|---------|-----|-------------|
| `$curse on` | Halfop+ / Admin | Enable fining in this channel |
| `$curse off` | Halfop+ / Admin | Disable fining in this channel |
| `$curse` | Anyone | Check whether fining is enabled |

> The bot auto-monitors all messages when enabled; no command is needed to trigger a fine.

---

## 🤦 Facepalm (facepalm)

Auto-trigger: when someone does `/me facepalms` or `/me facepalmed`, the bot replies with a random facepalm reaction.

| Trigger | Description |
|---------|-------------|
| `/me facepalms` | Triggers a bot reaction |
| `/me facepalmed` | Also triggers a bot reaction |

> Channel cooldown: 15 seconds.

---

## (╯°□°）╯︵ ┻━┻ Table Flip (tableflip)

| Command | Description |
|---------|-------------|
| `$flip` | Play a 4-step table flip animation |

> Cooldown: 60 sec per user per channel.

---

## 🔑 PromoteMe (opme)

| Command | Description |
|---------|-------------|
| `$promoteme [nick]` | Promote yourself (or target) to channel op |

> Requires bot to have op. Admin-only by default (configurable).

---

## 🚪 Join (join)

| Command | Who | Description |
|---------|-----|-------------|
| `$join #channel [key]` | Owner only | Make the bot join a channel |

---

## 🎬 YouTube Titles (youtube_titles)

No commands — automatic. The bot detects any YouTube URL posted in chat and replies with the video title and author.
