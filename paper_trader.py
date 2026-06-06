#!/usr/bin/env python3
"""
Educational Paper Trading Bot
==============================
A real, working algorithmic trading system that trades with virtual money.
Uses real market data from Yahoo Finance.

Strategy: EMA Crossover + RSI Filter
- Buys when fast EMA crosses above slow EMA AND RSI < 70 (not overbought)
- Sells when fast EMA crosses below slow EMA OR RSI > 75 (overbought exit)
- Trailing stop loss at -8% from highest price since entry

Run modes:
  --backtest   : Test strategy on historical data (default)
  --paper      : Paper trade using latest price
  --tickers    : Comma-separated tickers (default: AAPL,TSLA,NVDA)
  --cash       : Starting virtual cash (default: 10000)

Example:
  python paper_trader.py --backtest --tickers AAPL,TSLA --cash 5000
  python paper_trader.py --paper --tickers NVDA
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.table import Table

console = Console()

# ── Strategy Parameters ─────────────────────────────────────────────────────
FAST_EMA = 12
SLOW_EMA = 26
RSI_PERIOD = 14
RSI_ENTRY_MAX = 70
RSI_EXIT_MAX = 75
TRAILING_STOP_PCT = 0.08
COMMISSION_PCT = 0.001  # 0.1% per trade


# ── Data Classes ────────────────────────────────────────────────────────────
@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    highest_price: float = 0.0

    def __post_init__(self):
        self.highest_price = self.entry_price


@dataclass
class Trade:
    date: datetime
    ticker: str
    action: str  # BUY or SELL
    price: float
    shares: float
    value: float
    pnl: Optional[float] = None
    reason: str = ""


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


# ── Indicators ──────────────────────────────────────────────────────────────
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
    df["signal"] = 0
    df.loc[df["ema_fast"] > df["ema_slow"], "signal"] = 1
    df["crossover"] = df["signal"].diff()
    return df


# ── Engine ──────────────────────────────────────────────────────────────────
class PaperTradingEngine:
    def __init__(self, cash: float):
        self.portfolio = Portfolio(cash=cash)
        self.starting_cash = cash

    def buy(self, date, ticker, price, reason=""):
        if ticker in self.portfolio.positions:
            return
        invest_amount = self.portfolio.cash * 0.25  # 25% position sizing
        if invest_amount < 100:
            return
        cost = invest_amount * (1 + COMMISSION_PCT)
        if cost > self.portfolio.cash:
            return
        shares = invest_amount / price
        self.portfolio.cash -= cost
        pos = Position(ticker=ticker, entry_date=date, entry_price=price, shares=shares)
        self.portfolio.positions[ticker] = pos
        trade = Trade(
            date=date, ticker=ticker, action="BUY", price=price,
            shares=shares, value=invest_amount, reason=reason
        )
        self.portfolio.trades.append(trade)

    def sell(self, date, ticker, price, reason=""):
        pos = self.portfolio.positions.pop(ticker, None)
        if not pos:
            return
        gross = pos.shares * price
        net = gross * (1 - COMMISSION_PCT)
        pnl = net - (pos.shares * pos.entry_price)
        self.portfolio.cash += net
        trade = Trade(
            date=date, ticker=ticker, action="SELL", price=price,
            shares=pos.shares, value=gross, pnl=pnl, reason=reason
        )
        self.portfolio.trades.append(trade)

    def update_positions(self, date, prices: dict[str, float]):
        for ticker, pos in list(self.portfolio.positions.items()):
            price = prices.get(ticker)
            if not price:
                continue
            pos.highest_price = max(pos.highest_price, price)
            stop_price = pos.highest_price * (1 - TRAILING_STOP_PCT)
            if price <= stop_price:
                self.sell(date, ticker, price, reason="Trailing stop")

    def equity(self, prices: dict[str, float]) -> float:
        total = self.portfolio.cash
        for ticker, pos in self.portfolio.positions.items():
            total += pos.shares * prices.get(ticker, pos.entry_price)
        return total

    def run_backtest(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        console.print(f"\n[bold cyan]Fetching {ticker}...[/bold cyan]")
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data.empty:
            console.print(f"[red]No data for {ticker}[/red]")
            return pd.DataFrame()

        # Flatten multi-index columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = add_indicators(data)

        for idx, row in df.iterrows():
            price = float(row["Close"])
            date = idx

            # Update trailing stops for open positions
            self.update_positions(date, {ticker: price})

            # Exit logic
            if ticker in self.portfolio.positions:
                rsi_val = float(row["rsi"]) if pd.notna(row["rsi"]) else 50
                if row["crossover"] == -1:
                    self.sell(date, ticker, price, reason="EMA crossunder")
                elif rsi_val > RSI_EXIT_MAX:
                    self.sell(date, ticker, price, reason=f"RSI {rsi_val:.1f} > {RSI_EXIT_MAX}")
                continue

            # Entry logic
            if row["crossover"] == 1:
                rsi_val = float(row["rsi"]) if pd.notna(row["rsi"]) else 50
                if rsi_val < RSI_ENTRY_MAX:
                    self.buy(date, ticker, price, reason=f"EMA crossover, RSI {rsi_val:.1f}")

            # Record daily equity
            eq = self.equity({ticker: price})
            self.portfolio.history.append({
                "date": date,
                "ticker": ticker,
                "equity": eq,
                "price": price,
                "cash": self.portfolio.cash,
            })

        return df


# ── Reporting ───────────────────────────────────────────────────────────────
def report_results(engine: PaperTradingEngine, ticker: str):
    trades = [t for t in engine.portfolio.trades if t.ticker == ticker]

    table = Table(title=f"📊 {ticker} Trade Log", show_lines=True)
    table.add_column("Date", style="cyan")
    table.add_column("Action", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("Reason", style="dim")

    total_pnl = 0.0
    wins = 0
    losses = 0
    for t in trades:
        pnl_str = ""
        if t.pnl is not None:
            total_pnl += t.pnl
            if t.pnl > 0:
                wins += 1
                pnl_str = f"[green]+${t.pnl:,.2f}[/green]"
            else:
                losses += 1
                pnl_str = f"[red]-${abs(t.pnl):,.2f}[/red]"
        table.add_row(
            t.date.strftime("%Y-%m-%d"), t.action,
            f"${t.price:.2f}", f"{t.shares:.2f}",
            f"${t.value:,.2f}", pnl_str, t.reason
        )

    console.print(table)

    # Metrics
    if trades and len([t for t in trades if t.action == "SELL"]) > 0:
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        console.print(f"\n[bold]Metrics for {ticker}:[/bold]")
        console.print(f"  Total Trades: {len([t for t in trades if t.action == 'SELL'])}")
        console.print(f"  Win Rate: {win_rate:.1f}%")
        console.print(f"  Gross P&L: {'[green]' if total_pnl >= 0 else '[red]'}${total_pnl:,.2f}[/]")


def report_overall(engine: PaperTradingEngine, final_prices: dict[str, float]):
    eq = engine.equity(final_prices)
    ret = ((eq - engine.starting_cash) / engine.starting_cash) * 100

    console.print("\n" + "=" * 50)
    console.print("[bold magenta]🏦 FINAL PORTFOLIO REPORT[/bold magenta]")
    console.print(f"Starting Cash:  ${engine.starting_cash:,.2f}")
    console.print(f"Final Equity:   ${eq:,.2f}")
    console.print(f"Total Return:   {'[green]' if ret >= 0 else '[red]'}{ret:.2f}%[/]")
    console.print(f"Open Positions: {len(engine.portfolio.positions)}")
    console.print("=" * 50)

    # Equity curve to CSV
    if engine.portfolio.history:
        hist_df = pd.DataFrame(engine.portfolio.history)
        out_path = Path("paper_trade_history.csv")
        hist_df.to_csv(out_path, index=False)
        console.print(f"\n[dim]Equity curve saved to: {out_path.absolute()}[/dim]")


def paper_trade_live(tickers: list[str], cash: float):
    """Single-shot paper trade using today's latest price."""
    engine = PaperTradingEngine(cash=cash)
    prices = {}
    console.print("\n[bold cyan]📡 PAPER TRADE SNAPSHOT[/bold cyan]\n")

    for ticker in tickers:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo")
        if hist.empty:
            console.print(f"[red]No data for {ticker}[/red]")
            continue

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        price = float(latest["Close"])
        prices[ticker] = price

        # Simple indicator check
        df = add_indicators(hist)
        last = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else last

        rsi_val = float(last["rsi"]) if pd.notna(last["rsi"]) else 50
        ema_fast = float(last["ema_fast"])
        ema_slow = float(last["ema_slow"])
        prev_fast = float(prev_row["ema_fast"])
        prev_slow = float(prev_row["ema_slow"])

        signal = "HOLD"
        if ema_fast > ema_slow and rsi_val < RSI_ENTRY_MAX:
            if prev_fast <= prev_slow:
                signal = "🟢 BUY (crossover)"
            else:
                signal = "🟢 TREND UP"
        elif ema_fast < ema_slow:
            if prev_fast >= prev_slow:
                signal = "🔴 SELL (crossunder)"
            else:
                signal = "🔴 TREND DOWN"

        console.print(f"[bold]{ticker}[/bold]  ${price:.2f}  |  EMA: {ema_fast:.2f}/{ema_slow:.2f}  |  RSI: {rsi_val:.1f}  →  {signal}")

    console.print(f"\n[dim]Virtual Cash: ${cash:,.2f}  |  No real money deployed.[/dim]")


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Educational Paper Trading Bot")
    parser.add_argument("--tickers", default="AAPL,TSLA,NVDA", help="Comma-separated tickers")
    parser.add_argument("--cash", type=float, default=10000, help="Starting virtual cash")
    parser.add_argument("--backtest", action="store_true", help="Run backtest mode")
    parser.add_argument("--paper", action="store_true", help="Run paper trade snapshot")
    parser.add_argument("--period", default="1y", help="Backtest period (e.g., 1y, 6mo)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    if args.paper:
        paper_trade_live(tickers, args.cash)
        return

    # Default to backtest
    engine = PaperTradingEngine(cash=args.cash)
    final_prices = {}

    for ticker in tickers:
        df = engine.run_backtest(ticker, period=args.period)
        if not df.empty:
            final_prices[ticker] = float(df["Close"].iloc[-1])
            report_results(engine, ticker)

    report_overall(engine, final_prices)


if __name__ == "__main__":
    main()
