# 🗳️ Voting (voting)

Create timed polls with multiple options. Requires halfop (`%`) or above to create.

---

## Commands

| Command | Description |
|---------|-------------|
| `$vote Q:<question> A1:<opt> A2:<opt> [A3:...] T:<duration>` | Create a poll |
| `$v <number>` / `$castvote` | Cast your vote |
| `$votestats` / `$vstats` / `$voteresults` | Show current poll results |
| `$endvote` | End the poll early (creator or halfop+) |
| `$votehelp` | Full help guide (PM) |

> **Duration formats:** `30m`, `24h`, `2d`

---

## Examples

**Create a poll:**
```
<%Admin> $vote Q:Best programming language? A1:Python A2:JavaScript A3:Rust A4:Go T:1h
<Glitchy> 🗳️ Poll created! "Best programming language?" — Vote with $v 1-4. Ends in 1 hour.
<Glitchy> 1. Python | 2. JavaScript | 3. Rust | 4. Go
```

**Cast a vote:**
```
<User> $v 3
<Glitchy> 🗳️ User voted for option 3 (Rust)!
```

**Check results mid-poll:**
```
<User> $votestats
<Glitchy> 🗳️ "Best programming language?" — Python: 4 | JavaScript: 2 | Rust: 6 | Go: 1 | Total: 13
```

**End poll early:**
```
<%Admin> $endvote
<Glitchy> 🗳️ Poll ended! Results: 1st Rust (6) | 2nd Python (4) | 3rd JavaScript (2) | 4th Go (1)
```

**Simple yes/no poll:**
```
<%Admin> $vote Q:Should we add a new channel? A1:Yes A2:No T:24h
<Glitchy> 🗳️ Poll created! "Should we add a new channel?" — Vote with $v 1-2. Ends in 24 hours.
```
