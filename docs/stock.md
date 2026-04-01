# 📈 Stocks (stock)

Look up stocks by ticker or company name via yfinance.

---

## Setup

**1. Install dependencies:**
```bash
pip install yfinance
```

**2. Place the script:**
```
~/.sopel/scripts/stock.py
```

**No config section needed.** The script uses the free Yahoo Finance API via the `yfinance` library — no API key required.

---

## Commands

| Command | Description |
|---------|-------------|
| `$stock <symbol or name>` | Look up a stock |

---

## Examples

**Look up by ticker:**
```
<User> $stock AAPL
<Glitchy> 📈 Apple Inc. (AAPL): $189.84 | +1.23 (+0.65%) | Vol: 52.3M | Cap: $2.95T
```

**Look up by company name:**
```
<User> $stock Microsoft
<Glitchy> 📈 Microsoft Corp. (MSFT): $378.91 | -2.10 (-0.55%) | Vol: 18.7M | Cap: $2.81T
```

**Another example:**
```
<User> $stock Tesla
<Glitchy> 📈 Tesla Inc. (TSLA): $248.42 | +5.67 (+2.33%) | Vol: 98.1M | Cap: $789B
```
