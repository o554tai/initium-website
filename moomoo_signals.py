#!/usr/bin/env python3
"""
Moomoo Paper Trading Signal Generator
======================================
Generates clean, actionable trade signals formatted for manual entry
into Moomoo's paper trading simulator.

Strategy: EMA Crossover + RSI + Trailing Stop
- BUY when fast EMA crosses above slow EMA AND RSI < 70
- SELL when fast EMA crosses below slow EMA OR RSI > 75 OR trailing stop hit
- Position size: 25% of virtual portfolio per trade
- Stop loss: 8% trailing stop from highest price since entry

Usage:
  python moomoo_signals.py --tickers AAPL,TSLA,NVDA --cash 100000
  python moomoo_signals.py --tickers D05.SI,U11.SI --cash 50000
  python moomoo_signals.py --watchlist --file watchlist.txt --cash 100000

Output format is designed for easy copy-paste into Moomoo paper trades.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
plain_mode = False  # set by --plain flag

def p(text: str = ""):
    """Print that respects --plain mode."""
    if plain_mode:
        # Strip rich markup for plain text
        import re
        clean = re.sub(r'\[(/?)[^\]]+\]', '', text)
        print(clean)
    else:
        console.print(text)

# ── Strategy Config ──────────────────────────────────────────────────────────
FAST_EMA = 12
SLOW_EMA = 26
RSI_PERIOD = 14
RSI_ENTRY_MAX = 70
RSI_EXIT_MAX = 75
TRAILING_STOP_PCT = 0.08
POSITION_PCT = 0.25
COMMISSION_PCT = 0.001


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ema(df["Close"], FAST_EMA)
    df["ema_slow"] = ema(df["Close"], SLOW_EMA)
    df["rsi"] = rsi(df["Close"], RSI_PERIOD)
    return df


def get_signal(ticker: str, cash: float) -> dict:
    """Analyze a ticker and return a clean signal dict."""
    t = yf.Ticker(ticker)
    hist = t.history(period="6mo")
    if hist.empty:
        return {"ticker": ticker, "error": "No data"}

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    df = add_indicators(hist)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    price = float(latest["Close"])
    ema_fast = float(latest["ema_fast"])
    ema_slow = float(latest["ema_slow"])
    rsi_val = float(latest["rsi"]) if pd.notna(latest["rsi"]) else 50

    prev_fast = float(prev["ema_fast"])
    prev_slow = float(prev["ema_slow"])

    # Determine signal
    signal = "HOLD"
    reason = "No crossover"
    action = None

    # Buy signal: crossover + RSI filter
    if prev_fast <= prev_slow and ema_fast > ema_slow and rsi_val < RSI_ENTRY_MAX:
        signal = "🟢 BUY"
        action = "BUY"
        reason = f"EMA crossover ({ema_fast:.2f} > {ema_slow:.2f}), RSI {rsi_val:.1f}"
    # Sell signals
    elif prev_fast >= prev_slow and ema_fast < ema_slow:
        signal = "🔴 SELL"
        action = "SELL"
        reason = f"EMA crossunder ({ema_fast:.2f} < {ema_slow:.2f})"
    elif rsi_val > RSI_EXIT_MAX:
        signal = "🔴 SELL"
        action = "SELL"
        reason = f"RSI overbought {rsi_val:.1f} > {RSI_EXIT_MAX}"
    else:
        # Trend status
        if ema_fast > ema_slow:
            signal = "📈 TREND UP"
            reason = f"EMA bullish, RSI {rsi_val:.1f}"
        else:
            signal = "📉 TREND DOWN"
            reason = f"EMA bearish, RSI {rsi_val:.1f}"

    # Position sizing for BUY signals
    position = {}
    if action == "BUY":
        invest = cash * POSITION_PCT
        shares = int(invest / price)
        if shares < 1:
            shares = 1
        cost = shares * price * (1 + COMMISSION_PCT)
        stop_price = price * (1 - TRAILING_STOP_PCT)
        position = {
            "shares": shares,
            "invest_amount": shares * price,
            "total_cost": cost,
            "stop_loss": stop_price,
            "risk_amount": (price - stop_price) * shares,
        }

    return {
        "ticker": ticker,
        "price": price,
        "signal": signal,
        "action": action,
        "reason": reason,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "rsi": rsi_val,
        "position": position,
    }


def print_moomoo_card(s: dict, cash: float):
    """Print a Moomoo-ready trade card."""
    ticker = s["ticker"]
    price = s["price"]
    signal = s["signal"]
    reason = s["reason"]

    if s.get("error"):
        p(f"[red]{ticker}: {s['error']}[/red]")
        return

    # Header
    p(f"\n{'='*50}")
    p(f"[bold]{ticker}[/bold]  {signal}")
    p(f"{'='*50}")

    # Price & indicators
    p(f"  Current Price:  ${price:.2f}")
    p(f"  EMA {FAST_EMA}:        {s['ema_fast']:.2f}")
    p(f"  EMA {SLOW_EMA}:        {s['ema_slow']:.2f}")
    p(f"  RSI:            {s['rsi']:.1f}")
    p(f"  Reason:         {reason}")

    # Moomoo trade instructions
    if s["action"] == "BUY":
        pos = s["position"]
        p(f"\n[bold green]📋 MOOMOO PAPER TRADE ORDER[/bold green]")
        p(f"  Action:         BUY")
        p(f"  Ticker:         {ticker}")
        p(f"  Order Type:     Limit (or Market if urgent)")
        p(f"  Limit Price:    ${price:.2f}")
        p(f"  Quantity:       {pos['shares']} shares")
        p(f"  Invest Amount:  ${pos['invest_amount']:,.2f}")
        p(f"  Est. Cost:      ${pos['total_cost']:,.2f} (inc. 0.1% comm)")
        p(f"\n[bold yellow]🛑 STOP LOSS SETUP[/bold yellow]")
        p(f"  Stop Type:      Trailing Stop")
        p(f"  Stop Price:     ${pos['stop_loss']:.2f} ({TRAILING_STOP_PCT*100:.0f}% below entry)")
        p(f"  Risk Amount:    ${pos['risk_amount']:,.2f}")
        p(f"\n[dim]Steps in Moomoo app:[/dim]")
        p(f"  1. Search {ticker} → Tap 'Trade'")
        p(f"  2. Switch to 'Paper Trade' / 'Simulator' mode")
        p(f"  3. Select BUY → Enter quantity: {pos['shares']}")
        p(f"  4. Set limit price: ${price:.2f} (or Market)")
        p(f"  5. After fill: Set trailing stop at ${pos['stop_loss']:.2f}")

    elif s["action"] == "SELL":
        p(f"\n[bold red]📋 MOOMOO PAPER TRADE ORDER[/bold red]")
        p(f"  Action:         SELL")
        p(f"  Ticker:         {ticker}")
        p(f"  Order Type:     Market (or Limit at ${price:.2f})")
        p(f"  Reason:         {reason}")
        p(f"\n[dim]Steps in Moomoo app:[/dim]")
        p(f"  1. Go to Positions → Find {ticker}")
        p(f"  2. Tap SELL → Enter your position quantity")
        p(f"  3. Submit order")

    else:
        p(f"\n[dim]No action needed. Hold and monitor.[/dim]")

    p(f"{'='*50}")


def print_dashboard(signals: list[dict], cash: float):
    """Print a summary dashboard of all signals."""
    if plain_mode:
        p(f"\n{'='*55}")
        p(f"  MOOMOO SIGNAL DASHBOARD  |  Cash: ${cash:,.2f}")
        p(f"{'='*55}")
        p(f"  {'Ticker':<10} {'Price':>10} {'Signal':<18} {'RSI':>6} {'Trend':<10} {'Action':<12}")
        p(f"  {'-'*10} {'-'*10} {'-'*18} {'-'*6} {'-'*10} {'-'*12}")
        for s in signals:
            if s.get("error"):
                p(f"  {s['ticker']:<10} {'ERROR':>10}")
                continue
            trend = "Bull" if s["ema_fast"] > s["ema_slow"] else "Bear"
            action = s["signal"] if s["action"] else "-"
            if s["action"] == "BUY":
                action += f" ({s['position']['shares']}sh)"
            p(f"  {s['ticker']:<10} ${s['price']:>8.2f} {action:<18} {s['rsi']:>5.1f} {trend:<10} {s['signal']:<12}")
        p(f"{'='*55}")
        return

    table = Table(title=f"📊 Moomoo Signal Dashboard  |  Cash: ${cash:,.2f}", show_lines=True)
    table.add_column("Ticker", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Signal")
    table.add_column("RSI", justify="right")
    table.add_column("EMA Trend")
    table.add_column("Action")

    for s in signals:
        if s.get("error"):
            table.add_row(s["ticker"], "—", "[red]ERROR[/red]", "—", "—", "—")
            continue

        trend = "📈 Bull" if s["ema_fast"] > s["ema_slow"] else "📉 Bear"
        action_text = s["signal"] if s["action"] else "—"

        if s["action"] == "BUY":
            action_text += f" ({s['position']['shares']} sh)"

        table.add_row(
            s["ticker"],
            f"${s['price']:.2f}",
            s["signal"],
            f"{s['rsi']:.1f}",
            trend,
            action_text,
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="Moomoo Paper Trading Signal Generator")
    parser.add_argument("--tickers", default="AAPL,TSLA,NVDA", help="Comma-separated tickers")
    parser.add_argument("--cash", type=float, default=100000, help="Virtual cash amount (default 100k)")
    parser.add_argument("--watchlist", action="store_true", help="Read tickers from file")
    parser.add_argument("--file", default="watchlist.txt", help="Watchlist file path")
    parser.add_argument("--plain", action="store_true", help="Plain text output (for cron/Telegram)")
    args = parser.parse_args()

    global plain_mode
    plain_mode = args.plain

    if args.watchlist:
        watchlist_path = Path(args.file)
        if watchlist_path.exists():
            tickers = [t.strip().upper() for t in watchlist_path.read_text().splitlines() if t.strip()]
        else:
            p(f"[red]Watchlist file not found: {args.file}[/red]")
            return
    else:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]

    p(f"\n[bold cyan]🚀 Moomoo Signal Generator[/bold cyan]")
    p(f"[dim]Strategy: EMA{FAST_EMA}/{SLOW_EMA} Crossover + RSI | Cash: ${args.cash:,.2f}[/dim]\n")

    signals = []
    for ticker in tickers:
        s = get_signal(ticker, args.cash)
        signals.append(s)

    # Dashboard first
    print_dashboard(signals, args.cash)

    # Then detailed cards for actionable signals
    actionable = [s for s in signals if s.get("action")]
    if actionable:
        p(f"\n[bold]📌 Actionable Signals: {len(actionable)}[/bold]")
        for s in actionable:
            print_moomoo_card(s, args.cash)
    else:
        p("\n[dim]No actionable signals right now. Check back tomorrow.[/dim]")

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = Path(f"moomoo_signals_{timestamp}.txt")
    lines = []
    for s in signals:
        if s.get("error"):
            lines.append(f"{s['ticker']}: ERROR - {s['error']}")
            continue
        lines.append(f"{s['ticker']} | ${s['price']:.2f} | {s['signal']} | RSI {s['rsi']:.1f} | {s['reason']}")
        if s.get("action") == "BUY":
            pos = s["position"]
            lines.append(f"  → BUY {pos['shares']} shares @ ${s['price']:.2f}, Stop @ ${pos['stop_loss']:.2f}")
    out_path.write_text("\n".join(lines))
    p(f"\n[dim]Signals saved to: {out_path.absolute()}[/dim]")


if __name__ == "__main__":
    main()
