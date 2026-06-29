"""
mt5_dashboard_service.py

Read-only service layer for the Streamlit dashboard.
All MT5 API calls are wrapped in a single init/fetch/shutdown cycle.
"""

import os
from datetime import date, datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd

from nyaoscalper1_config import (
    ACCOUNT_LOGIN, SYMBOL, EA_NAME, PROFILE_NAME,
    PROFILE_DIR, TERMINAL_LOG_DIR, MQL5_LOG_DIR,
)

EXPECTED_CHART_FILE = "chart01.chr"
POSITIVE_TERMS = ["initialized", "loaded successfully"]
ERROR_TERMS = ["error", "cannot", "failed", "license"]


class MTSDashboardService:
    """Read-only MT5 data provider. All fetches within one init/shutdown cycle."""

    def __init__(self):
        self._connected = False

    def _ensure_init(self):
        self._connected = mt5.initialize()
        return self._connected

    def _shutdown(self):
        mt5.shutdown()
        self._connected = False

    def _get_account_info(self):
        acc = mt5.account_info()
        if not acc:
            return {}
        return {
            "login": acc.login,
            "server": acc.server,
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "margin_level": acc.margin_level,
            "currency": acc.currency,
            "leverage": acc.leverage,
            "trade_allowed": acc.trade_allowed,
        }

    def _get_terminal_info(self):
        term = mt5.terminal_info()
        if not term:
            return {}
        return {
            "connected": term.connected,
            "company": term.company,
            "name": term.name,
            "maxbars": term.maxbars,
        }

    def _get_symbol_tick(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {}
        info = mt5.symbol_info(symbol)
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": tick.ask - tick.bid if tick.ask and tick.bid else 0,
            "time": datetime.fromtimestamp(tick.time) if tick.time else None,
            "digits": info.digits if info else 5,
        }

    def _get_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return pd.DataFrame()
        records = []
        for p in positions:
            records.append({
                "ticket": p.ticket,
                "time": datetime.fromtimestamp(p.time),
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "swap": p.swap,
                "magic": p.magic,
                "comment": p.comment,
            })
        return pd.DataFrame(records)

    def _get_recent_deals(self, symbol, limit=20):
        from_date = datetime.now() - timedelta(days=7)
        deals = mt5.history_deals_get(from_date, datetime.now())
        if not deals:
            return pd.DataFrame()
        records = []
        for d in deals:
            if d.symbol != symbol:
                continue
            records.append({
                "time": datetime.fromtimestamp(d.time),
                "ticket": d.ticket,
                "type": "BUY" if d.type == 0 else "SELL" if d.type == 1 else f"TYPE_{d.type}",
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "commission": d.commission,
                "swap": d.swap,
                "magic": d.magic,
                "comment": d.comment,
            })
        df = pd.DataFrame(records)
        return df.sort_values("time", ascending=False).head(limit)

    def _get_nyaoscalper1_status(self):
        result = {
            "profile_folder": os.path.isdir(PROFILE_DIR),
            "chart_file": os.path.isfile(os.path.join(PROFILE_DIR, EXPECTED_CHART_FILE)),
            "ea_log_evidence": False,
            "ea_log_lines": [],
            "errors": [],
        }
        today_str = date.today().strftime("%Y%m%d")
        for log_dir in (TERMINAL_LOG_DIR, MQL5_LOG_DIR):
            log_path = os.path.join(log_dir, f"{today_str}.log")
            if not os.path.isfile(log_path):
                continue
            for enc in ("utf-16-le", "utf-8", "utf-8-sig"):
                try:
                    with open(log_path, "r", encoding=enc) as f:
                        for line in f:
                            lower = line.strip().lower()
                            if EA_NAME.lower() in lower:
                                result["ea_log_lines"].append(line.strip())
                                if any(t in lower for t in POSITIVE_TERMS):
                                    result["ea_log_evidence"] = True
                            for term in ERROR_TERMS:
                                if term in lower and EA_NAME.lower() in lower:
                                    result["errors"].append(line.strip()[:150])
                    break
                except (UnicodeDecodeError, Exception):
                    continue
        return result

    def _compute_position_summary(self, positions_df):
        if positions_df.empty:
            return {
                "count": 0, "buy_count": 0, "sell_count": 0,
                "buy_volume": 0.0, "sell_volume": 0.0,
                "floating_pnl": 0.0, "best_pnl": 0.0, "worst_pnl": 0.0,
            }
        buys = positions_df[positions_df["type"] == "BUY"]
        sells = positions_df[positions_df["type"] == "SELL"]
        return {
            "count": len(positions_df),
            "buy_count": len(buys),
            "sell_count": len(sells),
            "buy_volume": buys["volume"].sum() if not buys.empty else 0.0,
            "sell_volume": sells["volume"].sum() if not sells.empty else 0.0,
            "floating_pnl": positions_df["profit"].sum(),
            "best_pnl": positions_df["profit"].max(),
            "worst_pnl": positions_df["profit"].min(),
        }

    def fetch_all(self):
        """
        Single init/fetch/shutdown cycle. Returns dict with all data.
        Returns {"connected": False} if MT5 cannot initialize.
        """
        if not self._ensure_init():
            return {"connected": False}
        try:
            account = self._get_account_info()
            terminal = self._get_terminal_info()
            tick = self._get_symbol_tick(SYMBOL)
            positions = self._get_positions(SYMBOL)
            deals = self._get_recent_deals(SYMBOL, 20)
            status = self._get_nyaoscalper1_status()
            summary = self._compute_position_summary(positions)
            return {
                "connected": True,
                "account": account,
                "terminal": terminal,
                "tick": tick,
                "positions": positions,
                "deals": deals,
                "status": status,
                "summary": summary,
            }
        finally:
            self._shutdown()
