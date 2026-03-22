#!/usr/bin/env python3
"""
stock.py — Sopel IRC plugin for single-line stock lookups.
Usage in IRC: .stock <SYMBOL or Company Name>
Example:      .stock IWM   or   .stock Apple
"""

from sopel import plugin
import datetime
import yfinance as yf


# ── Helpers ────────────────────────────────────────────────────────────────────

def resolve_ticker(query):
    """Try the query as a ticker; fall back to name search."""
    ticker = yf.Ticker(query.upper())
    info = ticker.info
    if info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose"):
        return ticker

    try:
        results = yf.Search(query, max_results=5).quotes
        if results:
            symbol = results[0].get("symbol", "")
            if symbol:
                return yf.Ticker(symbol)
    except Exception:
        pass
    return None


def pct_change(history, days):
    """Return formatted % change string from `days` ago to most recent close."""
    if history is None or history.empty:
        return None
    closes = history["Close"].dropna()
    if len(closes) < 2:
        return None

    latest = float(closes.iloc[-1])
    cutoff = closes.index[-1] - datetime.timedelta(days=days)
    past = closes[closes.index <= cutoff]
    if past.empty:
        return None

    ref = float(past.iloc[-1])
    if ref == 0:
        return None
    pct = (latest - ref) / ref * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def trend_emoji(pct_str):
    if pct_str is None:
        return "⚪"
    try:
        val = float(pct_str.replace("%", "").replace("+", ""))
        if val > 0:
            return "🟢"
        if val < 0:
            return "🔴"
    except ValueError:
        pass
    return "⚪"


def fmt_period(label, pct_str):
    if pct_str is None:
        return f"{label}: N/A"
    return f"{trend_emoji(pct_str)} {label}: {pct_str}"


# ── Sopel command ──────────────────────────────────────────────────────────────

@plugin.command("stock")
def stock_cmd(bot, trigger):
    """Look up a stock by symbol or company name and show price + % changes."""
    query = trigger.group(2)
    if not query or not query.strip():
        bot.say("Usage: .stock <SYMBOL or Company Name> — e.g. .stock AAPL or .stock Apple")
        return
    query = query.strip()

    try:
        ticker = resolve_ticker(query)
    except Exception as e:
        bot.say(f"❌ Error looking up '{query}': {str(e)[:80]}")
        return

    if not ticker:
        bot.say(f"❌ No stock found for '{query}'. Try symbol or full name.")
        return

    try:
        info = ticker.info
        symbol = info.get("symbol", query.upper())
        name = info.get("longName") or info.get("shortName", symbol)
        currency = info.get("currency", "USD")
        price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose", 0)
        curr_symbol = "$" if currency == "USD" else f"{currency} "
        curr_str = f"{curr_symbol}{price:,.2f}"

        history = None
        try:
            history = ticker.history(period="2y", interval="1d")
        except Exception:
            pass

        p24h = pct_change(history, 1)
        p7d  = pct_change(history, 7)
        p30d = pct_change(history, 30)
        p6m  = pct_change(history, 182)
        p1y  = pct_change(history, 365)

        parts = [
            f"📈 {name} ({symbol})",
            f"💵 {curr_str}",
            fmt_period("24h", p24h),
            fmt_period("7d", p7d),
            fmt_period("30d", p30d),
            fmt_period("6m", p6m),
            fmt_period("1y", p1y),
        ]
        bot.say("  ".join(parts))

    except Exception as e:
        bot.say(f"❌ Data fetch failed for '{query}': {str(e)[:80]}")