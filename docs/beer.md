# 🍺 Bartender (beer)

Virtual bartender with a tip economy integrated directly with the **mug** game's coin system.

---

## Setup

**No config needed.** Just drop the script in place and it works.

**1. Place the script:**
```
~/.sopel/scripts/beer.py
```

**Data Persistence:**
All coin balances are stored in `bot.db` under the `mug_game` plugin. Bartender tip stats are stored in `bot.db` under the `beer` plugin.

---

## Menu & Prices

All prices are in **coins** (🪙).

| Command | Aliases | Cost | Description |
|---------|---------|------|-------------|
| `$scotch [nick]` | — | 15 🪙 | Premium Scotch whisky 🏴󠁧󠁢󠁳󠁣󠁴󠁿🥃 |
| `$whiskey [nick]` | `$whisky` | 12 🪙 | Fine whiskey 🥃 |
| `$irish [nick]` | `$irishwhiskey` | 10 🪙 | Irish whiskey 🇮🇪🥃 |
| `$beer [nick]` | — | 5 🪙 | Serve a random beer 🍺 |
| `$shot [nick]` | — | 7 🪙 | Serve a random shot 🥃 |
| `$vodka [nick]` | — | 10 🪙 | Premium vodka 🥃 |
| `$rum [nick]` | — | 10 🪙 | Spiced rum 🏴‍☠️🥃 |
| `$tequila [nick]` | — | 10 🪙 | Fine tequila 🇲🇽🥃 |
| `$gin [nick]` | — | 10 🪙 | Botanical gin 🌿🥃 |
| `$brandy [nick]` | `$cognac` | 12 🪙 | Brandy / Cognac 🥃 |
| `$margarita [nick]` | `$marg` | 9 🪙 | Margarita Salt rim! 🧂🍹 |
| `$sake [nick]` | — | 9 🪙 | Sake 🍶 |
| `$liqueur [nick]` | `$cordial` | 8 🪙 | Liqueur 🍯🥃 |
| `$wine [nick]` | — | 8 🪙 | Glass of wine 🍷 |
| `$cava [nick]` | `$prosecco` | 8 🪙 | Sparkling Cava 🍾🥂 |
| `$mead [nick]` | — | 7 🪙 | Horn of mead ⚔️🍯 |
| `$magners [nick]` | — | 6 🪙 | Magners cider 🍎🍺 |
| `$drink [nick]` | — | 10 🪙 | Mixed drink 🍹 |
| `$mocktail [nick]` | `$virgin` | 4 🪙 | Mocktail (non-alcoholic) 🍹 |
| `$coffee [nick]` | `$caffeine` | 3 🪙 | Coffee ☕ |
| `$decaf [nick]` | `$decaffeinated` | 3 🪙 | Decaf coffee ☕😴 |
| `$tea [nick]` | `$cuppa` | 3 🪙 | Tea 🍵 |
| `$water [nick]` | `$hydrate` | Free | Water (Responsible hydration!) 💧 |
| `$pizza [nick]` | — | 15 🪙 | Pizza 🍕 |
| `$appetizer [nick]` | `$snack`, `$food` | 8 🪙 | Appetizer 🍽️ |
| `$surprise [nick]` | `$random` | Varies | Random menu item and price 🎉 |

---

## Economy

* **Starting Tab**: Ordering for the first time opens a tab with **1,000 starting coins**.
* **Daily Bonus**: Users receive a **100 coin credit** once every 24 hours. Credits are applied when you order or check your tab.
* **Shared Balance**: Coins are shared with the **mug** game. It is a single unified economy.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `$tip <nick> <amount>` | Tip another user for great service (deducts from your coins) | `$tip m0n 50` |
| `$barcash` / `$balance` | Check your current coin balance | `$barcash` |
| `$toptip` | See the top 5 most tipped bartenders | `$toptip` |
| `$barhelp` | Get the full menu and command guide (sent via PM) | `$barhelp` |

### Admin PM Commands

Must be private messaged to the bot. Requires bot admin/owner status.

| Command | Description | Example |
|---------|-------------|---------|
| `$adjbal <nick> <+/-amount>` | Adjust a user's coin balance | `$adjbal m0n +500` |
| `$barreset <nick>` | Reset a user's balance to 1,000 coins and clear their tips | `$barreset m0n` |
| `$barreset all confirm` | Reset ALL users' balances and clear all tips (requires `confirm`) | `$barreset all confirm` |

---

## Examples

**Order a drink for yourself:**
```
<User> $beer
* Glitchy slides a frosty Guinness 🍺 across the bar to User ✨
```
*(You will receive a PM notice: Paid 5 coins - Remaining balance: 995 coins 🪙)*

**Buy someone else a drink:**
```
<User> $shot Friend
* Glitchy lines up a shot of Jägermeister 🦌🥃 for Friend
```

**Tip another user:**
```
<User> $tip Friend 100
<Glitchy> User tips Friend 100 coins! 💰✨
```
*(You will receive a PM notice: New balance: 895 coins 🪙)*
