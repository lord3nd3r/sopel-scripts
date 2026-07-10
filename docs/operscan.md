# 🔍 IRC Operator Scanner (operscan)

An IRC operator scanner for Sopel. It allows users to scan any channel the bot is currently in to identify network or server IRC operators (`opers`) present.

---

## Setup

**1. Place the script:**
```
~/.sopel/scripts/operscan.py
```

---

## Commands

This command is **PM-only** (must be sent to the bot via private message).

| Command | Arguments | Description | Example |
|---------|-----------|-------------|---------|
| `$operscan` | `#channel` | Scans the specified channel and reports all nicks with the IRC operator flag (`*`) | `/msg Glitchy $operscan #chat` |

---

## Behavior

1. **Verification**: The bot first checks if it is in the target channel. If not, it returns an error.
2. **Scan Execution**: The bot sends a raw `WHO` command to the channel.
3. **Detection**:
   * It processes incoming WHO replies (numeric `352`).
   * It checks the flags field of the user's WHO information (e.g. `H*@`). The presence of `*` indicates the user is a network/server IRC operator.
4. **Response**: Once the WHO list ends (numeric `315`), the bot PMs the list of operators back to the requester.
5. **Timeout**: If the WHO responses are delayed or do not arrive, the scan times out after 15 seconds, returning any operators found up to that point.
