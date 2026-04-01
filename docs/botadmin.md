# 🛠️ Bot Admin (botadmin)

Owner/admin-only bot management commands.

---

## Owner Commands

| Command | Description |
|---------|-------------|
| `$restart` | Restart the bot |
| `$breload <module\|all>` | Reload a plugin or all plugins |
| `$botquit [msg]` | Shut down the bot |
| `$raw <irc line>` | Send a raw IRC command |
| `$botnick <nick>` | Change the bot's nick |

## Admin Commands

| Command | Description |
|---------|-------------|
| `$say <target> <msg>` | Make bot say something |
| `$act <target> <action>` | Make bot do a /me action |
| `$bjoin #channel [key]` | Join a channel |
| `$bpart #channel [msg]` | Leave a channel |
| `$bmode #channel <mode> [nick]` | Set a channel mode |
| `$bothelp` | List all admin commands |

---

## Examples

**Restart the bot:**
```
/msg Glitchy $restart
```

**Reload a single plugin:**
```
/msg Glitchy $breload mug
```

**Reload all plugins:**
```
/msg Glitchy $breload all
```

**Shut down the bot:**
```
/msg Glitchy $botquit Goodnight!
```

**Send a raw IRC command:**
```
/msg Glitchy $raw PRIVMSG #channel :Hello from raw!
```

**Change bot nick:**
```
/msg Glitchy $botnick NewNick
```

**Make the bot say something:**
```
/msg Glitchy $say #channel Hello everyone!
```

**Make the bot do an action:**
```
/msg Glitchy $act #channel waves at everyone
```

**Join/part channels:**
```
/msg Glitchy $bjoin #newchannel
/msg Glitchy $bpart #oldchannel See ya!
```

**Set a channel mode:**
```
/msg Glitchy $bmode #channel +o User
```

**List admin commands:**
```
/msg Glitchy $bothelp
```
