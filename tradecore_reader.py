"""
tradeCorelogger CSV Reader
===========================
Parses TickLog_*.csv and TradeLog_*.csv files produced by
tradeCorelogger_v2.2 EA (logs to MT5 Common Files directory).

Usage:
    from tradecore_reader import read_tick_logs, read_trade_logs, CoreLoggerAnalytics

    # Load latest tick data
    ticks = read_tick_logs(symbol="EURUSD")
    trades = read_trade_logs(symbol="EURUSD")

    # Analyze
    analysis = CoreLoggerAnalytics()
    analysis.load_all()
    stats = analysis.symbol_stats("EURUSD")
"""

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from autotrade1_config import COMMON_FILES_DIR

MT5_COMMON_DIR = Path(COMMON_FILES_DIR)


def _parse_timestamp(ts: str, file_date: Optional[str] = None) -> Optional[datetime]:
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S",
                 "%Y.%m.%d", "%Y-%m-%d", "%H:%M:%S"):
        try:
            dt = datetime.strptime(ts, fmt)
            if fmt == "%H:%M:%S" and file_date:
                dt = dt.replace(year=file_date.year, month=file_date.month, day=file_date.day)
            return dt
        except ValueError:
            continue
    return None

def _file_date_from_name(fp: Path) -> Optional[datetime]:
    stem = fp.stem
    parts = stem.split("_")
    for p in parts:
        try:
            return datetime.strptime(p, "%Y.%m.%d")
        except ValueError:
            continue
    return None


def find_log_files(prefix: str, symbol: str = "", date: str = "") -> list[Path]:
    pattern = f"{prefix}_{symbol}_{date}*.csv" if symbol else f"{prefix}_*.csv"
    if date:
        pattern = f"{prefix}_{symbol}_{date}.csv" if symbol else f"{prefix}_*_{date}.csv"
    return sorted(MT5_COMMON_DIR.glob(pattern), reverse=True)


def _read_file_with_fallback(fp: Path):
    try:
        return fp.read_text(encoding="utf-8-sig")
    except PermissionError:
        print(f"  [SKIP] {fp.name} -- locked by MT5 (add FILE_SHARE_READ to tradeCorelogger & recompile)", file=__import__('sys').stderr)
        return None
    except UnicodeDecodeError:
        pass
    try:
        text = fp.read_text(encoding="utf-16-le")
        if text and text[0] == "\ufeff":
            text = text[1:]
        return text
    except Exception:
        print(f"  [SKIP] {fp.name} -- unknown encoding", file=__import__('sys').stderr)
        return None


def read_tick_logs(
    symbol: str = "",
    date: str = "",
    max_files: int = 5,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[dict]:
    files = find_log_files("TickLog", symbol, date)[:max_files]
    if not files:
        return []

    rows = []
    for fp in files:
        text = _read_file_with_fallback(fp)
        if text is None:
            continue
        reader = csv.DictReader(text.splitlines())
        file_dt = _file_date_from_name(fp)
        for row in reader:
            ts = _parse_timestamp(row.get("timestamp", ""), file_dt)
            if ts:
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                row["_datetime"] = ts
                row["_file"] = fp.name
            for key in ("bid", "ask", "last", "spread", "delta_price",
                        "rva_long", "rva_medium", "rva_short",
                        "roc_long", "roc_medium", "roc_short",
                        "roc_live_interbar", "roc_live_intrabar",
                        "atr_long", "atr_medium", "atr_short",
                        "live_pip_range", "live_velocity",
                        "volume"):
                if key in row and row[key]:
                    try:
                        row[key] = float(row[key])
                    except ValueError:
                        pass
            for key in ("delta_time_msc",):
                if key in row and row[key]:
                    try:
                        row[key] = int(row[key])
                    except ValueError:
                        pass
            rows.append(row)
    return rows


def read_trade_logs(
    symbol: str = "",
    date: str = "",
    max_files: int = 5,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[dict]:
    files = find_log_files("TradeLog", symbol, date)[:max_files]
    if not files:
        return []

    rows = []
    for fp in files:
        text = _read_file_with_fallback(fp)
        if text is None:
            continue
        reader = csv.DictReader(text.splitlines())
        file_dt = _file_date_from_name(fp)
        for row in reader:
            ts = _parse_timestamp(row.get("timestamp", ""), file_dt)
            if ts:
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                row["_datetime"] = ts
                row["_file"] = fp.name
            for key in ("volume", "price", "slippage",
                        "rva_long", "rva_medium", "rva_short",
                        "roc_long", "roc_medium", "roc_short",
                        "roc_live_interbar", "roc_live_intrabar",
                        "atr_long", "atr_medium", "atr_short",
                        "live_pip_range", "live_velocity",
                        "floating_pnl", "open_trades", "open_buys", "open_sells",
                        "balance", "equity", "drawdown"):
                if key in row and row[key]:
                    try:
                        row[key] = float(row[key])
                    except ValueError:
                        pass
            rows.append(row)
    return rows


class CoreLoggerAnalytics:
    """Aggregates and analyzes tradeCorelogger data across symbols/dates."""

    def __init__(self):
        self.ticks: dict[str, list[dict]] = defaultdict(list)
        self.trades: dict[str, list[dict]] = defaultdict(list)
        self.symbols: set = set()

    def load_all(self, days: int = 7):
        for fp in sorted(MT5_COMMON_DIR.glob("TickLog_*.csv"), reverse=True):
            parts = fp.stem.split("_")
            if len(parts) >= 3:
                sym = parts[1]
                self.symbols.add(sym)
        for sym in self.symbols:
            self.ticks[sym] = read_tick_logs(symbol=sym)
            self.trades[sym] = read_trade_logs(symbol=sym)

    def symbol_stats(self, symbol: str) -> dict:
        ticks = self.ticks.get(symbol, [])
        trades = self.trades.get(symbol, [])
        if not ticks:
            return {"symbol": symbol, "error": "No data"}

        bids = [v for t in ticks for v in [t.get("bid")] if isinstance(v, (int, float))]
        stats = {
            "symbol": symbol,
            "tick_count": len(ticks),
            "trade_count": len(trades),
            "first_tick": ticks[0].get("_datetime") if ticks else None,
            "last_tick": ticks[-1].get("_datetime") if ticks else None,
            "price_min": min(bids) if bids else 0,
            "price_max": max(bids) if bids else 0,
            "price_current": bids[-1] if bids else 0,
            "avg_spread": sum(t.get("spread", 0) for t in ticks if t.get("spread")) / max(len([t for t in ticks if t.get("spread")]), 1),
            "last_rva_long": ticks[-1].get("rva_long", 0) if ticks else 0,
            "last_rva_medium": ticks[-1].get("rva_medium", 0) if ticks else 0,
            "last_rva_short": ticks[-1].get("rva_short", 0) if ticks else 0,
            "last_atr_long": ticks[-1].get("atr_long", 0) if ticks else 0,
            "last_atr_medium": ticks[-1].get("atr_medium", 0) if ticks else 0,
            "last_atr_short": ticks[-1].get("atr_short", 0) if ticks else 0,
            "last_roc_long": ticks[-1].get("roc_long", 0) if ticks else 0,
            "last_roc_medium": ticks[-1].get("roc_medium", 0) if ticks else 0,
            "last_roc_short": ticks[-1].get("roc_short", 0) if ticks else 0,
            "last_candle_dir": ticks[-1].get("candle_direction", "") if ticks else "",
            "last_mode": ticks[-1].get("mode", "") if ticks else "",
        }

        if trades:
            profits = []
            buy_count = 0
            sell_count = 0
            total_volume_buy = 0.0
            total_volume_sell = 0.0
            last_trade_time = None

            for t in trades:
                v = t.get("floating_pnl")
                if v is not None and v != "":
                    try:
                        profits.append(float(v))
                    except (ValueError, TypeError):
                        pass
                ot = t.get("order_type")
                if ot is None:
                    ot = ""
                vol = 0
                try:
                    vol = float(t.get("volume", 0))
                except (ValueError, TypeError):
                    pass
                if "BUY" in ot:
                    buy_count += 1
                    total_volume_buy += vol
                elif "SELL" in ot:
                    sell_count += 1
                    total_volume_sell += vol

                tt = t.get("_datetime") or t.get("timestamp")
                if tt:
                    last_trade_time = str(tt)

            balances = [t.get("balance", 0) for t in trades if t.get("balance")]
            equities = [t.get("equity", 0) for t in trades if t.get("equity")]

            stats.update({
                "last_balance": balances[-1] if balances else 0,
                "last_equity": equities[-1] if equities else 0,
                "last_drawdown": trades[-1].get("drawdown", 0),
                "avg_floating_pnl": sum(profits) / max(len(profits), 1),
                "total_open_trades": trades[-1].get("open_trades", 0) if trades else 0,
                "buy_trades": buy_count,
                "sell_trades": sell_count,
                "buy_volume": total_volume_buy,
                "sell_volume": total_volume_sell,
                "net_pnl": sum(profits) if profits else 0,
                "last_trade_time": last_trade_time,
            })

        return stats

    def market_summary(self) -> dict[str, dict]:
        return {sym: self.symbol_stats(sym) for sym in sorted(self.symbols)}

    def recent_mode_changes(self, symbol: str = "", limit: int = 10) -> list[dict]:
        trades = self.trades.get(symbol, []) if symbol else []
        if not symbol:
            for sym in self.symbols:
                trades.extend(self.trades[sym])
            trades.sort(key=lambda x: x.get("_datetime") or datetime.min, reverse=True)
        return [
            {"time": t.get("_datetime"), "symbol": t.get("symbol"),
             "event": t.get("event_type"), "mode": t.get("mode"),
             "pnl": t.get("floating_pnl"), "balance": t.get("balance"),
             "equity": t.get("equity")}
            for t in trades[:limit]
        ]


def export_to_dataframe(symbol: str = "", days: int = 1):
    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed, skipping dataframe export")
        return None

    ticks = read_tick_logs(symbol=symbol)
    trades = read_trade_logs(symbol=symbol)

    result = {}
    if ticks:
        df = pd.DataFrame(ticks)
        if "_datetime" in df.columns:
            df["_datetime"] = pd.to_datetime(df["_datetime"])
        result["ticks"] = df
    if trades:
        df = pd.DataFrame(trades)
        if "_datetime" in df.columns:
            df["_datetime"] = pd.to_datetime(df["_datetime"])
        result["trades"] = df
    return result if result else None


if __name__ == "__main__":
    import os
    analysis = CoreLoggerAnalytics()
    analysis.load_all(days=7)
    summary = analysis.market_summary()
    print(f"\n=== tradeCorelogger Market Summary ({len(summary)} symbols) ===\n")
    for sym, stats in sorted(summary.items()):
        if "error" in stats:
            print(f"  {sym}: {stats['error']}")
            continue
        print(f"  {sym}:")
        print(f"    Ticks: {stats['tick_count']}  |  Trades: {stats['trade_count']}")
        print(f"    Tick Range: {stats.get('first_tick', '?')} -> {stats.get('last_tick', '?')}")
        print(f"    Latest Bid: {stats['price_current']:.5f}")
        print(f"    Spread: {stats['avg_spread']:.1f}")
        print(f"    Mode: {stats['last_mode']}  Candle: {stats['last_candle_dir']}")
        if stats.get("buy_trades") is not None:
            print(f"    Buy Trades: {stats['buy_trades']} ({stats['buy_volume']:.2f} lots)  "
                  f"Sell Trades: {stats['sell_trades']} ({stats['sell_volume']:.2f} lots)")
        if stats.get("net_pnl") is not None:
            print(f"    Net PnL: {stats['net_pnl']:.2f}")
        if stats.get("last_balance"):
            print(f"    Balance: {stats['last_balance']:.2f}  Equity: {stats['last_equity']:.2f}  DD: {stats['last_drawdown']:.2f}")
        if stats.get("last_trade_time"):
            print(f"    Last Trade: {stats['last_trade_time']}")
        print()

    print("=== Recent Trade Events ===\n")
    for ev in analysis.recent_mode_changes(limit=5):
        print(f"  {ev['time']} | {ev['symbol']} | {ev['event']} | mode={ev['mode']} | PnL={ev['pnl']:+.2f}")
    print()
