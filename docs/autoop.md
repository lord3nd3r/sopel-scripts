# 🤖 Auto Op / Auto-Voice Plugin (`autoop.py`)

A simple but powerful plugin to automatically grant operator (`+o`), half-operator (`+h`), or voice (`+v`) to specific users as soon as they join the channel.

## 🌟 Features
- **Persistent Data:** Users added to the auto-mode lists are saved in the bot's internal database (`bot.db`) and survive bot restarts.
- **Admin-Only Security:** All modification commands require the user to be a bot admin or owner.
- **Immediate Application:** Modes are applied automatically via IRC's `JOIN` event.

## 🛠️ Commands

*Note: All commands must be run inside the channel where you want the modes applied.*

### Operator (`+o`)
| Command | Description |
|---------|-------------|
| `$aop <nick>` | Adds the specified user to the auto-op list. |
| `$dop <nick>` | Removes the user from the auto-op list. |

### Half-Operator (`+h`)
| Command | Description |
|---------|-------------|
| `$ahop <nick>` | Adds the specified user to the auto-halfop list. |
| `$dhop <nick>` | Removes the user from the auto-halfop list. |

### Voice (`+v`)
| Command | Description |
|---------|-------------|
| `$avoice <nick>` | Adds the specified user to the auto-voice list. |
| `$dvoice <nick>` | Removes the user from the auto-voice list. |

### Utility
| Command | Description |
|---------|-------------|
| `$alist` | Lists all users configured for auto-modes in the current channel. |

## 💡 Examples

Adding a trusted user to the auto-op list:
```
<Admin> $aop TrustedFriend
<Bot> ✅ Added TrustedFriend to the auto-op (+o) list for #mychannel.
```

Listing all active auto-modes:
```
<Admin> $alist
<Bot> Auto-modes for #mychannel | +o: TrustedFriend, OtherMod | +v: ChattyUser
```

## ⚙️ Requirements
- The user running the commands must be a configured bot admin (or owner) in the bot's `.cfg` file.
- For the bot to successfully apply the modes when users join, the bot itself must have operator privileges (`+o` or higher) in the channel.
