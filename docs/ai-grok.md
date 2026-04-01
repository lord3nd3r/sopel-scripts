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
