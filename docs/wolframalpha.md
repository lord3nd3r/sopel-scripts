# 🧮 Wolfram Alpha (wolframalpha)

Queries [Wolfram Alpha](https://www.wolframalpha.com/) for math, unit conversions, factual lookups, and computational answers.

---

## Setup

1. Get a free API key at: https://developer.wolframalpha.com/
2. Open `wolframalpha.py` and set `WA_API_KEY = 'your_key_here'` at the top.

---

## Commands

All commands accept the same query syntax.

| Command | Description |
|---------|-------------|
| `$wa <query>` | Query Wolfram Alpha |
| `$calc <expr>` | Calculate a math expression |
| `$math <expr>` | Alias for `$calc` |
| `$convert <query>` | Unit/currency conversion |
| `$wolframalpha <query>` | Full command name |

---

## Examples

```
<End3r> $wa speed of light in mph
<devbox> Speed of light: 6.706 × 10^8 mph — [ https://www.wolframalpha.com/input/?i=speed+of+light+in+mph ]

<End3r> $calc 2^32
<devbox> Result: 4294967296 — [ https://www.wolframalpha.com/input/?i=2%5E32 ]

<End3r> $convert 100 USD to EUR
<devbox> Result: 92.45 euros (EUR) — [ https://www.wolframalpha.com/input/?i=100+USD+to+EUR ]

<End3r> $wa population of Japan
<devbox> Population: 123.3 million people (2024 estimate) — [ ... ]
```

---

## Notes

- Results are truncated to 300 characters.
- A link to the full Wolfram Alpha result page is always appended.
- If Wolfram Alpha has no primary result pod, the plugin falls back to the first available result.
- If there are no results at all, spelling suggestions are shown when available.
