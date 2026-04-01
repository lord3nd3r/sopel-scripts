# 🧠 AI Chatbot (ai-grok)

Talks to you when mentioned by name. Uses xAI Grok with web search.

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
