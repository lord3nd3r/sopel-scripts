# 🧠 AI Chatbot (ai-grok)

Talks to you when mentioned by name. Uses xAI Grok with web search.

---

## Setup

**1. Install dependencies:**
```bash
pip install requests
```

**2. Add to your Sopel `.cfg` file:**
```ini
[grok]
# Required — your xAI API key (get one from https://console.x.ai)
api_key = xai-XXXXXXXXXXXXXXXXXXXXXXXX

# Optional — model to use (default: grok-4-1-fast-reasoning)
# Choices: grok-4-1-fast-reasoning, grok-4-fast-reasoning, grok-3, grok-beta
model = grok-4-1-fast-reasoning

# Optional — custom system prompt (the bot's personality)
system_prompt = You are Grok, a witty AI assistant on IRC.

# Optional — channels where the bot will NOT respond
blocked_channels =
    #quiet-room
    #no-bots

# Optional — nicks the bot will completely ignore
banned_nicks =
    SpamBot
    AnnoyingUser

# Optional — nicks ignored in conversation (no replies, but still tracked)
ignored_nicks =
    LogBot

# Optional — how to detect if a mention is directed at the bot
# Choices: heuristic (default), off, model
intent_check = heuristic
```

**3. Place the script:**
```
~/.sopel/scripts/ai-grok.py
```

> **Note:** Per-channel system prompts can be set via `grok_channel_prompts.json` in the scripts directory.

---

## Commands

### Talk to the Bot

| Command | Who | Description |
|---------|-----|-------------|
| `BotNick: <message>` | Anyone | Talk to the bot |
| `/me pets BotNick` | Anyone | Emote interaction |
| `$grokreset` | Anyone | Reset your conversation history |
| `$grokreset channel` | Op+ / Admin | Reset all channel conversation history |
| `$testemote` | Anyone | Test that the emote plugin is loaded |

### Admin PM Commands

| Command | Description |
|---------|-------------|
| `$join #channel [key]` | Make bot join a channel |
| `$part #channel` | Make bot leave a channel |
| `$ignore <nick>` | Add nick to ignore list |
| `$unignore <nick>` | Remove nick from ignore list |

---

## 🔍 Web Search (Automatic)

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

### Asking for Sources

You can ask the bot to include source links in its response:

```
Grok: what's the latest news? show me the links
Grok: search for election results with sources
```

**Trigger phrases:** `show me the links`, `sources`, `citations`, `references`, `urls`, `include links`

> **Note:** The bot uses a strict extraction system that queries the API for genuine deep-link article URLs to prevent hallucinations. It does not output raw links mid-sentence; instead, it generates a clean list of verified, clickable sources at the end of its response.

---

## 🕐 Time & Date Queries

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

### Setting Your Timezone

Tell the bot your timezone and it will remember it for all future time queries:

| Method | Example |
|--------|---------|
| Tell the bot | `Grok: I'm in EST` |
| Explicit set | `Grok: set my timezone to CST` |
| Natural phrasing | `Grok: I live in Pacific` |

**Supported abbreviations:** `EST` / `EDT` / `ET` / `Eastern`, `CST` / `CDT` / `CT` / `Central`, `MST` / `MDT` / `MT` / `Mountain`, `PST` / `PDT` / `PT` / `Pacific`, `UTC` / `GMT`

### Setting Your Time Format

Prefer 12-hour or 24-hour time? Tell the bot:

```
Grok: I prefer 12hr
Grok: use 24 hour
```

Preferences are saved in the database and persist across restarts.

---

## 💬 Review Mode

Ask the bot to summarize or give its opinion on what's been discussed in the channel. Channel messages are **persisted to the database** so review mode survives bot restarts.

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
Grok: catch me up, what did I miss?
Grok: tldr
```

> **Cooldown:** Review mode has a 30-second cooldown per channel to prevent spam.

---

## 🤗 Emote Interactions

The bot reacts to `/me` actions and emote-style messages directed at it. Responses are **generated dynamically by the AI** and vary each time.

| Action | Example Trigger |
|--------|-----------------|
| pet / pat | `/me pets Grok` |
| hug / cuddle / snuggle | `/me hugs Grok` |
| poke / boop | `/me pokes Grok` |
| kiss | `/me kisses Grok` |
| slap / smack | `/me slaps Grok` |
| highfive | `/me highfives Grok` |
| wave / wink / dance / twirl | `/me waves at Grok` |

**Trigger formats:**
```
/me pets Grok
* User hugs Grok
```

---

## Examples

**Chatting with the bot:**
```
<User> Glitchy: what's the weather like on Mars?
<Glitchy> Mars is currently experiencing a mild dust storm in the Hellas Basin...
```

**Emote interaction:**
```
* User pets Glitchy
* Glitchy purrs and nuzzles User
```

**Resetting your history:**
```
<User> $grokreset
<Glitchy> User: Your conversation history has been reset.
```

**Resetting channel history (ops only):**
```
<@Admin> $grokreset channel
<Glitchy> Admin: Channel conversation history has been reset.
```

**Testing emote plugin:**
```
<User> $testemote
<Glitchy> Emote plugin is loaded and working!
```

**Admin PM — join a channel:**
```
/msg Glitchy $join #newchannel
```

**Admin PM — ignore a user:**
```
/msg Glitchy $ignore SpamBot
```
