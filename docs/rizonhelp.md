# 🆘 rizonhelp — Rizon Network Help

A helper plugin for Rizon IRC network users. Provides quick access to common help topics, FAQ, and staff information.

### Features
- Look up network-specific help topics (VHosts, SASL, ZNC, ChanServ, etc.).
- Fuzzy search for topics.
- Multi-line responses for detailed help.
- Can be enabled/disabled per channel.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$rhelp` | List all available help topics | `$rhelp` |
| `$rhelp <topic>` | Show detailed help for a specific topic | `$rhelp vhost` |
| `$rizonhelpon` | Enable Rizon help in the channel (Ops only) | `$rizonhelpon` |
| `$rizonhelpoff` | Disable Rizon help in the channel (Ops only) | `$rizonhelpoff` |

### Common Topics
- `vhost`, `sasl`, `znc`, `register`, `identify`, `ghost`
- `chanserv`, `nickserv`, `memoserv`
- `banned`, `flooded`, `spammers`, `trolls`
- `webchat`, `ip`

---
