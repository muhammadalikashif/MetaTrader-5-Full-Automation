"""
Live MT5 Orchestrator
======================
Manages live EA trading on demo/live account.
Monitor positions, track P&L, generate reports.

Usage:
    from live_orchestrator import LiveOrchestrator

    orch = LiveOrchestrator()
    orch.connect()
    orch.monitor_loop(interval_sec=5)
"""

import csv
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import MetaTrader5 as mt5


MT5_DATA_DIR = (
    Path(os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming")))
    / "MetaQuotes"
    / "Terminal"
    / "D0E8209F77C8CF37AD8BF550E51FF075"
)

PROFILES_DIR = MT5_DATA_DIR / "MQL5" / "Profiles" / "Tester"
EXPERTS_DIR = MT5_DATA_DIR / "MQL5" / "Experts"
TEMPLATES_DIR = MT5_DATA_DIR / "MQL5" / "Profiles" / "Templates"
FILES_DIR = MT5_DATA_DIR / "MQL5" / "Files"
LOG_DIR = Path("logs")
REPORT_DIR = Path("reports")
CONFIG_DIR = Path("config")
LOG_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)


@dataclass
class PositionInfo:
    ticket: int = 0
    symbol: str = ""
    type_str: str = ""
    volume: float = 0.0
    price_open: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    swap: float = 0.0
    commission: float = 0.0
    time: datetime = field(default_factory=datetime.now)
    magic: int = 0
    comment: str = ""


@dataclass
class AccountSnapshot:
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    margin_free: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    drawdown: float = 0.0
    dd_percent: float = 0.0
    open_positions: int = 0
    server: str = ""
    currency: str = ""
    leverage: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "margin_free": self.margin_free,
            "margin_level": self.margin_level,
            "profit": self.profit,
            "drawdown": self.drawdown,
            "dd_percent": self.dd_percent,
            "open_positions": self.open_positions,
            "server": self.server,
            "currency": self.currency,
            "leverage": self.leverage,
        }


def load_ea_config() -> list[dict]:
    config_path = CONFIG_DIR / "ea_instances.json"
    if not config_path.exists():
        return []
    with open(config_path, "r") as f:
        data = json.load(f)
    return data.get("instances", [])


def save_ea_config(instances: list[dict]):
    config_path = CONFIG_DIR / "ea_instances.json"
    with open(config_path, "w") as f:
        json.dump({"instances": instances}, f, indent=2)


class LiveOrchestrator:
    """Main class for live MT5 EA monitoring and management."""

    def __init__(self, mt5_path: Optional[str] = None, log_file: str = "live_monitor.csv"):
        self.connected = False
        self.mt5_path = mt5_path
        self.log_file = Path(LOG_DIR / log_file)
        self._init_log_file()
        self._peak_equity = 0.0

    def _init_log_file(self):
        if not self.log_file.exists():
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "balance", "equity", "margin", "margin_free",
                    "margin_level", "profit", "drawdown", "dd_pct",
                    "open_positions", "server", "currency", "leverage",
                ])

    def connect(self) -> bool:
        if self.mt5_path:
            result = mt5.initialize(path=self.mt5_path)
        else:
            result = mt5.initialize()
        if result:
            self.connected = True
            info = mt5.terminal_info()
            if info:
                print(f"[MT5] Connected: {info.name} (build {info.build})")
            account = mt5.account_info()
            if account:
                print(f"[MT5] Account: {account.login} | {account.server} | {account.currency} | Leverage 1:{account.leverage}")
                self._peak_equity = account.equity
        else:
            error = mt5.last_error()
            print(f"[MT5] Connection FAILED: error {error}")
        return self.connected

    def disconnect(self):
        mt5.shutdown()
        self.connected = False

    def get_positions(self, symbol: str = "") -> list[PositionInfo]:
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            result.append(PositionInfo(
                ticket=p.ticket,
                symbol=p.symbol,
                type_str="BUY" if p.type == 0 else "SELL",
                volume=p.volume,
                price_open=p.price_open,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                swap=p.swap,
                commission=getattr(p, 'commission', 0),
                time=datetime.fromtimestamp(p.time),
                magic=p.magic,
                comment=p.comment,
            ))
        return result

    def get_account_snapshot(self) -> Optional[AccountSnapshot]:
        account = mt5.account_info()
        if account is None:
            return None
        equity = account.equity
        if equity > self._peak_equity:
            self._peak_equity = equity
        dd = self._peak_equity - equity if equity < self._peak_equity else 0
        dd_pct = (dd / self._peak_equity * 100) if self._peak_equity > 0 else 0
        positions = self.get_positions()
        return AccountSnapshot(
            balance=account.balance,
            equity=equity,
            margin=account.margin,
            margin_free=account.margin_free,
            margin_level=account.margin_level,
            profit=account.profit,
            drawdown=dd,
            dd_percent=dd_pct,
            open_positions=len(positions),
            server=account.server,
            currency=account.currency,
            leverage=account.leverage,
        )

    def log_snapshot(self, snapshot: AccountSnapshot):
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                snapshot.timestamp.isoformat(),
                f"{snapshot.balance:.2f}",
                f"{snapshot.equity:.2f}",
                f"{snapshot.margin:.2f}",
                f"{snapshot.margin_free:.2f}",
                f"{snapshot.margin_level:.2f}",
                f"{snapshot.profit:.2f}",
                f"{snapshot.drawdown:.2f}",
                f"{snapshot.dd_percent:.2f}",
                snapshot.open_positions,
                snapshot.server,
                snapshot.currency,
                snapshot.leverage,
            ])

    def print_positions(self, positions: list[PositionInfo]):
        if not positions:
            print("  No open positions")
            return
        for p in positions:
            print(f"  #{p.ticket} {p.symbol} {p.type_str} {p.volume:.2f} "
                  f"@{p.price_open:.5f} SL:{p.sl:.5f} TP:{p.tp:.5f} "
                  f"P/L:{p.profit:.2f} Magic:{p.magic}")

    def symbol_info(self, symbol: str) -> Optional[dict]:
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "tick_size": info.trade_tick_size,
            "tick_value": info.trade_tick_value,
            "contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "spread": info.spread,
            "digits": info.digits,
            "trade_mode": info.trade_mode,
            "trade_stops_level": info.trade_stops_level,
            "trade_freeze_level": info.trade_freeze_level,
        }

    def open_trade(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl: float = 0,
        tp: float = 0,
        magic: int = 0,
        comment: str = "",
        slippage: int = 10,
    ) -> dict:
        if not self.connected:
            return {"success": False, "error": "Not connected to MT5"}
        if not mt5.symbol_info(symbol):
            return {"success": False, "error": f"Symbol {symbol} not found"}
        if not mt5.symbol_info_tick(symbol):
            return {"success": False, "error": f"No tick data for {symbol}"}

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return {"success": False, "error": f"Cannot get info for {symbol}"}

        digits = symbol_info.digits
        point = symbol_info.point
        tick = mt5.symbol_info_tick(symbol)

        order_type_upper = order_type.upper()
        if order_type_upper == "BUY":
            mt5_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif order_type_upper == "SELL":
            mt5_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            return {"success": False, "error": f"Invalid order_type: {order_type}. Use BUY or SELL"}

        volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
        volume = max(symbol_info.volume_min, min(volume, symbol_info.volume_max))
        if volume < symbol_info.volume_min:
            return {"success": False, "error": f"Volume {volume} below minimum {symbol_info.volume_min}"}

        sl_price = 0
        tp_price = 0
        if sl != 0:
            if order_type_upper == "BUY":
                sl_price = round(price - sl * point, digits)
            else:
                sl_price = round(price + sl * point, digits)
        if tp != 0:
            if order_type_upper == "BUY":
                tp_price = round(price + tp * point, digits)
            else:
                tp_price = round(price - tp * point, digits)

        filling_mode = symbol_info.filling_mode
        if filling_mode & 2:
            type_filling = mt5.ORDER_FILLING_IOC
        elif filling_mode & 1:
            type_filling = mt5.ORDER_FILLING_FOK
        else:
            type_filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "deviation": slippage,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }
        if sl_price != 0:
            request["sl"] = sl_price
        if tp_price != 0:
            request["tp"] = tp_price

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": f"order_send returned None (error {mt5.last_error()})"}

        ret = {
            "success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "retcode": result.retcode,
            "comment": result.comment,
            "price": price,
            "volume": volume,
        }
        if result.order:
            ret["order_ticket"] = result.order
        if result.deal:
            ret["deal_ticket"] = result.deal
        if not ret["success"]:
            ret["error"] = f"Order rejected: retcode={result.retcode} ({result.comment})"
        else:
            print(f"[TRADE] {order_type} {volume} {symbol} @ {price:.{digits}f} (SL={sl_price} TP={tp_price}) ticket=#{ret.get('deal_ticket', '?')}")
        return ret

    def close_trade(self, ticket: int, slippage: int = 10) -> dict:
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            return {"success": False, "error": f"Position #{ticket} not found"}
        position = position[0]

        symbol = position.symbol
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": f"No tick data for {symbol}"}

        digits = mt5.symbol_info(symbol).digits
        order_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        price = tick.bid if position.type == 0 else tick.ask

        info = mt5.symbol_info(symbol)
        filling_mode = info.filling_mode if info else 2
        if filling_mode & 2:
            type_filling = mt5.ORDER_FILLING_IOC
        elif filling_mode & 1:
            type_filling = mt5.ORDER_FILLING_FOK
        else:
            type_filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": position.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": slippage,
            "magic": position.magic,
            "comment": "closed by Python",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": f"order_send returned None"}

        ret = {
            "success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "retcode": result.retcode,
            "comment": result.comment,
            "price": price,
        }
        if result.deal:
            ret["deal_ticket"] = result.deal
        if not ret["success"]:
            ret["error"] = f"Close rejected: retcode={result.retcode} ({result.comment})"
        else:
            print(f"[TRADE] Closed #{ticket} {symbol} @ {price:.{digits}f}")
        return ret

    def close_positions_by_symbol(self, symbol: str, slippage: int = 10) -> list[dict]:
        positions = self.get_positions(symbol)
        if not positions:
            print(f"[TRADE] No open positions for {symbol}")
            return []
        results = []
        for p in positions:
            results.append(self.close_trade(p.ticket, slippage))
        return results

    def close_all_trades(self, slippage: int = 10) -> list[dict]:
        positions = self.get_positions()
        if not positions:
            print("[TRADE] No open positions to close")
            return []
        results = []
        for p in positions:
            results.append(self.close_trade(p.ticket, slippage))
        return results

    def modify_trade(self, ticket: int, sl: float = 0, tp: float = 0) -> dict:
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            return {"success": False, "error": f"Position #{ticket} not found"}
        position = position[0]

        symbol = position.symbol
        info = mt5.symbol_info(symbol)
        digits = info.digits
        point = info.point
        price_current = position.price_current

        sl_price = position.sl
        tp_price = position.tp

        if sl != 0:
            sl_price = round(price_current + sl * point if sl > 0 else price_current - abs(sl) * point, digits)
        if tp != 0:
            tp_price = round(price_current + tp * point if tp > 0 else price_current - abs(tp) * point, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": sl_price,
            "tp": tp_price,
            "magic": position.magic,
            "comment": "modified by Python",
        }

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": f"order_send returned None"}

        ret = {
            "success": result.retcode == mt5.TRADE_RETCODE_DONE,
            "retcode": result.retcode,
            "comment": result.comment,
        }
        if not ret["success"]:
            ret["error"] = f"Modify rejected: retcode={result.retcode} ({result.comment})"
        else:
            print(f"[TRADE] Modified #{ticket} {position.symbol}: SL={sl_price} TP={tp_price}")
        return ret

    def get_trade_history(
        self, from_date: datetime, to_date: Optional[datetime] = None
    ) -> list:
        if to_date is None:
            to_date = datetime.now()
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        return [
            {
                "ticket": d.ticket,
                "symbol": d.symbol,
                "type": "BUY" if d.type == 0 else ("SELL" if d.type == 1 else "OTHER"),
                "volume": d.volume,
                "price": d.price,
                "profit": d.profit,
                "commission": d.commission,
                "swap": d.swap,
                "time": datetime.fromtimestamp(d.time).isoformat(),
                "magic": d.magic,
                "comment": d.comment,
            }
            for d in deals
        ]

    def get_trade_history_grouped(self, from_date: datetime) -> dict:
        deals = self.get_trade_history(from_date)
        groups = defaultdict(lambda: {
            "magic": 0, "symbol": "", "ea_name": "",
            "total_closed_profit": 0.0, "floating_profit": 0.0,
            "trades": 0, "wins": 0, "losses": 0,
            "commission": 0.0, "swap": 0.0,
        })
        for d in deals:
            key = f"{d['magic']}_{d['symbol']}"
            g = groups[key]
            g["magic"] = d["magic"]
            g["symbol"] = d["symbol"]
            g["total_closed_profit"] += d["profit"]
            g["commission"] += d["commission"]
            g["swap"] += d["swap"]
            g["trades"] += 1
            if d["profit"] > 0:
                g["wins"] += 1
            elif d["profit"] < 0:
                g["losses"] += 1
        positions = self.get_positions()
        for p in positions:
            key = f"{p.magic}_{p.symbol}"
            if key in groups:
                groups[key]["floating_profit"] += p.profit
            else:
                groups[key] = {
                    "magic": p.magic, "symbol": p.symbol, "ea_name": "",
                    "total_closed_profit": 0.0, "floating_profit": p.profit,
                    "trades": 0, "wins": 0, "losses": 0,
                    "commission": 0.0, "swap": 0.0,
                }
        configs = load_ea_config()
        magic_to_name = {c.get("magic_number", 0): c.get("instance_id", "") for c in configs}
        for key, g in groups.items():
            g["ea_name"] = magic_to_name.get(g["magic"], f"magic_{g['magic']}")
            g["win_rate"] = round((g["wins"] / g["trades"] * 100), 1) if g["trades"] > 0 else 0.0
        return dict(groups)

    def doctor_check(self) -> dict:
        results = {}
        results["python_package"] = self._check_python_package()
        if not self.connected:
            results["mt5_connection"] = "NOT CONNECTED"
        else:
            results["mt5_connection"] = "OK"
        results["account_info"] = self._check_account_info()
        results["terminal_info"] = self._check_terminal_info()
        results["algo_trading"] = self._check_algo_trading()
        results["data_path"] = str(MT5_DATA_DIR)
        results["experts_dir"] = "OK" if EXPERTS_DIR.exists() else "MISSING"
        results["profiles_tester_dir"] = "OK" if PROFILES_DIR.exists() else "MISSING"
        results["templates_dir"] = "OK" if TEMPLATES_DIR.exists() else "MISSING"
        results["logs_dir"] = "OK" if LOG_DIR.exists() else "MISSING"
        results["ex5_count"] = len(list(EXPERTS_DIR.glob("*.ex5"))) if EXPERTS_DIR.exists() else 0
        results["set_count"] = len(list(PROFILES_DIR.glob("*.set"))) if PROFILES_DIR.exists() else 0
        results["config_magic_duplicates"] = self._check_magic_duplicates()
        return results

    def _check_python_package(self) -> str:
        try:
            import MetaTrader5 as _mt5
            return f"MetaTrader5 {_mt5.__version__}"
        except ImportError as e:
            return f"FAILED: {e}"

    def _check_account_info(self) -> str:
        try:
            acc = mt5.account_info()
            if acc:
                return f"OK: login={acc.login} server={acc.server} balance={acc.balance:.2f} {acc.currency}"
            return "UNAVAILABLE"
        except Exception as e:
            return f"ERROR: {e}"

    def _check_terminal_info(self) -> str:
        try:
            info = mt5.terminal_info()
            if info:
                return f"OK: {info.name} build={info.build} path={info.path}"
            return "UNAVAILABLE"
        except Exception as e:
            return f"ERROR: {e}"

    def _check_algo_trading(self) -> str:
        try:
            info = mt5.terminal_info()
            if info:
                return f"{'ENABLED' if info.trade_allowed else 'DISABLED'}"
            return "UNAVAILABLE"
        except Exception as e:
            return f"ERROR: {e}"

    def _check_magic_duplicates(self) -> list:
        configs = load_ea_config()
        magics = [c.get("magic_number") for c in configs if c.get("enabled", False)]
        seen = set()
        dupes = []
        for m in magics:
            if m in seen:
                dupes.append(m)
            seen.add(m)
        return dupes

    def validate_config(self) -> list[dict]:
        issues = []
        configs = load_ea_config()
        if not configs:
            return [{"severity": "WARN", "message": "No EA instances configured in config/ea_instances.json"}]
        magics = []
        template_names = []
        for i, c in enumerate(configs):
            idx = c.get("instance_id", f"#{i}")
            if not c.get("enabled", False):
                continue
            if not c.get("ea_name"):
                issues.append({"severity": "ERROR", "instance": idx, "message": "Missing ea_name"})
            sym = c.get("symbol")
            if not sym:
                issues.append({"severity": "ERROR", "instance": idx, "message": "Missing symbol"})
            tf = c.get("timeframe")
            if not tf:
                issues.append({"severity": "ERROR", "instance": idx, "message": "Missing timeframe"})
            elif tf not in self.TIMEFRAME_MAP:
                issues.append({"severity": "ERROR", "instance": idx, "message": f"Invalid timeframe: {tf}"})
            magic = c.get("magic_number")
            if not magic:
                issues.append({"severity": "ERROR", "instance": idx, "message": "Missing magic_number"})
            else:
                magics.append((idx, magic))
            set_file = c.get("set_file_name")
            if set_file:
                set_path = PROFILES_DIR / set_file
                if not set_path.exists():
                    issues.append({"severity": "WARN", "instance": idx, "message": f"set_file not found: {set_file}"})
            template = c.get("template_name")
            if not template:
                issues.append({"severity": "ERROR", "instance": idx, "message": "Missing template_name (required for launcher)"})
            else:
                template_names.append((idx, template))
                tpl_path = TEMPLATES_DIR / template
                if not tpl_path.exists():
                    issues.append({"severity": "WARN", "instance": idx, "message": f"template not found: {template} (create it manually in MT5 first)"})
            if self.connected:
                if sym and mt5.symbol_info(sym) is None:
                    issues.append({"severity": "WARN", "instance": idx, "message": f"Symbol {sym} not found in Market Watch"})
        seen_magics = {}
        for idx, m in magics:
            if m in seen_magics:
                issues.append({"severity": "ERROR", "instance": idx, "message": f"Duplicate magic_number {m} (also used by {seen_magics[m]})"})
            seen_magics[m] = idx
        seen_tpl = {}
        for idx, t in template_names:
            if t in seen_tpl:
                issues.append({"severity": "ERROR", "instance": idx, "message": f"Duplicate template_name {t} (also used by {seen_tpl[t]})"})
            seen_tpl[t] = idx
        return issues

    def update_set_file(self, ea_name: str, params: dict[str, str]) -> Path:
        set_path = PROFILES_DIR / f"{ea_name}.set"
        lines = []
        if set_path.exists():
            with open(set_path, "r", encoding="utf-8") as f:
                for line in f:
                    lines.append(line)
        remaining = dict(params)
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith(";"):
                key = stripped.split("=")[0].strip()
                if key in remaining:
                    parts = stripped.split("||")
                    parts[0] = f"{key}={remaining.pop(key)}"
                    new_lines.append("||".join(parts) + "\n")
                    continue
            new_lines.append(line)
        for key, val in remaining.items():
            new_lines.append(f"{key}={val}\n")
        set_path.parent.mkdir(parents=True, exist_ok=True)
        with open(set_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[SET] Updated {set_path.name} ({len(params)} params)")
        return set_path

    def copy_set_file(self, source: Path, ea_name: str) -> Path:
        import shutil
        dest = PROFILES_DIR / f"{ea_name}.set"
        if source.exists():
            shutil.copy2(source, dest)
            print(f"[SET] Copied {source.name} -> {dest}")
        return dest

    def copy_ea_file(self, source: Path) -> Path:
        import shutil
        dest = EXPERTS_DIR / source.name
        if source.exists():
            shutil.copy2(source, dest)
            print(f"[EA] Copied {source.name} -> {dest}")
        return dest

    def monitor_loop(self, interval_sec: int = 5, max_iterations: int = 0):
        if not self.connected:
            print("[MONITOR] Not connected. Call connect() first.")
            return
        iteration = 0
        print(f"[MONITOR] Starting loop (every {interval_sec}s)...")
        try:
            while True:
                if max_iterations > 0 and iteration >= max_iterations:
                    break
                snapshot = self.get_account_snapshot()
                if snapshot:
                    self.log_snapshot(snapshot)
                    positions = self.get_positions()
                    print(f"\n[{snapshot.timestamp.strftime('%H:%M:%S')}] "
                          f"Bal:{snapshot.balance:.2f} Eq:{snapshot.equity:.2f} "
                          f"DD:{snapshot.dd_percent:.1f}% "
                          f"Pos:{snapshot.open_positions} "
                          f"P/L:{snapshot.profit:+.2f}")
                    self.print_positions(positions)
                time.sleep(interval_sec)
                iteration += 1
        except KeyboardInterrupt:
            print("\n[MONITOR] Stopped by user")

    TIMEFRAME_MAP = {
        "PERIOD_M1": 1, "PERIOD_M2": 2, "PERIOD_M3": 3,
        "PERIOD_M4": 4, "PERIOD_M5": 5, "PERIOD_M6": 6,
        "PERIOD_M10": 10, "PERIOD_M12": 12, "PERIOD_M15": 15,
        "PERIOD_M20": 20, "PERIOD_M30": 30,
        "PERIOD_H1": 16385, "PERIOD_H2": 16386, "PERIOD_H3": 16387,
        "PERIOD_H4": 16388, "PERIOD_H6": 16390, "PERIOD_H8": 16392,
        "PERIOD_H12": 16396,
        "PERIOD_D1": 16408, "PERIOD_W1": 32769, "PERIOD_MN1": 49153,
    }

    def generate_launch_plan(self) -> Path:
        configs = load_ea_config()
        plan_path = FILES_DIR / "ea_launch_plan.csv"
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["instance_id", "symbol", "timeframe", "template_name", "magic_number", "enabled"])
            for c in configs:
                writer.writerow([
                    c.get("instance_id", ""),
                    c.get("symbol", ""),
                    c.get("timeframe", ""),
                    c.get("template_name", ""),
                    c.get("magic_number", 0),
                    "true" if c.get("enabled", False) else "false",
                ])
        print(f"[LAUNCH] Plan written: {plan_path} ({len([c for c in configs if c.get('enabled')])} enabled)")
        return plan_path

    def read_launcher_log(self) -> list[dict]:
        log_path = FILES_DIR / "ea_launcher_log.csv"
        if not log_path.exists():
            return []
        entries = []
        with open(log_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(row)
        return entries

    def generate_report(self, days: int):
        from datetime import timedelta
        from_date = datetime.now() - timedelta(days=days)
        grouped = self.get_trade_history_grouped(from_date)
        snapshot = self.get_account_snapshot()
        status = {
            "report_time": datetime.now().isoformat(),
            "period_days": days,
            "account": snapshot.to_dict() if snapshot else {},
            "groups": grouped,
        }
        status_path = REPORT_DIR / "live_status.json"
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2, default=str)
        csv_path = REPORT_DIR / "daily_report.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["magic", "symbol", "ea_name", "closed_profit", "floating_profit",
                             "trades", "wins", "losses", "win_rate", "commission", "swap"])
            for key, g in grouped.items():
                writer.writerow([
                    g["magic"], g["symbol"], g["ea_name"],
                    f"{g['total_closed_profit']:.2f}", f"{g['floating_profit']:.2f}",
                    g["trades"], g["wins"], g["losses"], f"{g['win_rate']:.1f}",
                    f"{g['commission']:.2f}", f"{g['swap']:.2f}",
                ])
        html_path = REPORT_DIR / "daily_report.html"
        rows_html = ""
        for key, g in grouped.items():
            bg = "#e8f5e9" if g["total_closed_profit"] >= 0 else "#ffebee"
            rows_html += f"""
            <tr style="background:{bg}">
                <td>{g['magic']}</td>
                <td>{g['symbol']}</td>
                <td>{g['ea_name']}</td>
                <td>{g['total_closed_profit']:.2f}</td>
                <td>{g['floating_profit']:.2f}</td>
                <td>{g['trades']}</td>
                <td>{g['wins']}</td>
                <td>{g['losses']}</td>
                <td>{g['win_rate']:.1f}%</td>
                <td>{g['commission']:.2f}</td>
                <td>{g['swap']:.2f}</td>
            </tr>"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MT5 Live Report</title>
<style>body{{font-family:sans-serif;margin:20px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:8px;text-align:right}}
th{{background:#333;color:#fff;text-align:center}}
tr:nth-child(even){{background:#f9f9f9}}
h2{{color:#333}}
.summary{{display:flex;gap:20px;margin:20px 0}}
.card{{background:#f5f5f5;border-radius:8px;padding:15px;min-width:120px;text-align:center}}
.card .value{{font-size:24px;font-weight:bold}}
.card .label{{font-size:12px;color:#666}}
.pos{{color:#2e7d32}}
.neg{{color:#c62828}}</style></head><body>
<h2>MT5 Live Performance Report</h2>
<p>Period: last {days} day(s) | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<div class="summary">
<div class="card"><div class="value">{snapshot.balance:.2f}</div><div class="label">Balance ({snapshot.currency})</div></div>
<div class="card"><div class="value {'pos' if snapshot.equity >= snapshot.balance else 'neg'}">{snapshot.equity:.2f}</div><div class="label">Equity</div></div>
<div class="card"><div class="value">{snapshot.dd_percent:.1f}%</div><div class="label">Drawdown</div></div>
<div class="card"><div class="value">{snapshot.open_positions}</div><div class="label">Open Positions</div></div>
</div>
<h3>Performance by Magic Number / Symbol</h3>
<table>
<thead><tr>
<th>Magic</th><th>Symbol</th><th>EA Name</th><th>Closed P/L</th><th>Floating P/L</th>
<th>Trades</th><th>Wins</th><th>Losses</th><th>Win Rate</th><th>Commission</th><th>Swap</th>
</tr></thead><tbody>
{rows_html}
</tbody></table>
</body></html>"""
        with open(html_path, "w") as f:
            f.write(html)
        print(f"[REPORT] CSV: {csv_path}")
        print(f"[REPORT] HTML: {html_path}")
        print(f"[REPORT] JSON: {status_path}")
