# 🍺 Bartender (beer)

Virtual bartender with a tip economy. Every user gets a $100 daily credit.

---

## Menu

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

## Economy

| Command | Description |
|---------|-------------|
| `$tip <nick> <amount>` | Tip another user |
| `$barcash` / `$balance` | Check your balance |
| `$toptip` | Top 5 most tipped bartenders |
| `$barhelp` | Full help guide (PM) |

## Admin PM Commands

| Command | Description |
|---------|-------------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's balance |
| `$barreset <nick>` | Reset a user's balance to $100 |
| `$barreset all confirm` | Reset ALL balances |

---

## Examples

**Order a beer for yourself:**
```
<User> $beer
<Glitchy> 🍺 User grabs a cold Guinness from the bar! ($5)
```

**Buy someone a drink:**
```
<User> $beer Friend
<Glitchy> 🍺 User slides a Heineken down the bar to Friend! ($5)
```

**Order a whiskey:**
```
<User> $whiskey
<Glitchy> 🥃 User enjoys a glass of Jameson 18-Year. Smooth. ($12)
```

**Get a surprise drink:**
```
<User> $surprise
<Glitchy> 🎉 User gets a surprise Mojito! ($10)
```

**Tip someone:**
```
<User> $tip Bartender 20
<Glitchy> User tipped Bartender $20! 💰
```

**Check your balance:**
```
<User> $barcash
<Glitchy> User, your bar tab balance is $63.00
```

**Top tippers:**
```
<User> $toptip
<Glitchy> 🏆 Top Tipped: 1. Bartender ($450) 2. Server ($280) ...
```

**Admin — adjust a balance:**
```
/msg Glitchy $adjbal User +500
```

**Admin — reset all balances:**
```
/msg Glitchy $barreset all confirm
```
