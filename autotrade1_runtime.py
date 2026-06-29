"""
autotrade1_runtime.py

AutoTrade1 automation runtime: monitor, stale detection, recovery, reports.

Commands (via run_monitor.py):
    autotrade1-run        Full workflow: launch -> verify -> logger -> monitor
    autotrade1-monitor    Continuous monitoring loop with stale detection
    autotrade1-watchdog   Recovery: auto-restart MT5 if needed
"""

import json
import os
import time
from datetime import datetime, date, timezone
from pathlib import Path

import MetaTrader5 as mt5

import launch_mt5
from tradecore_reader import _read_file_with_fallback
from autotrade1_config import *


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now()


def _today_str():
    return date.today().strftime("%Y%m%d")


def _today_log():
    return date.today().strftime("%Y.%m.%d")


def _read_log_lines(log_path, ea_name, positive_terms=None, error_terms=None):
    """Search a log file with encoding fallback. Returns (ea_found, lines, errors)."""
    ea_found = False
    lines = []
    errors = []
    for enc in ("utf-16-le", "utf-8", "utf-8-sig"):
        try:
            with open(log_path, "r", encoding=enc) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    lower = line.lower()
                    if ea_name.lower() in lower:
                        lines.append(line)
                        if positive_terms and any(t in lower for t in positive_terms):
                            ea_found = True
                    if error_terms:
                        for term in error_terms:
                            if term in lower:
                                errors.append(line[:150])
            break
        except (UnicodeDecodeError, Exception):
            continue
    return ea_found, lines, errors


def _read_tick_log(symbol=None):
    """Return (path, text, rows) for latest tick log, or (None, None, []) if missing."""
    if symbol is None:
        symbol = SYMBOL
    files = sorted(Path(COMMON_FILES_DIR).glob(f"TickLog_{symbol}_*.csv"), reverse=True)
    if not files:
        return None, None, []
    fp = files[0]
    text = _read_file_with_fallback(fp)
    if text is None:
        return fp, None, []
    rows = text.splitlines()
    return fp, text, rows


def _read_trade_log(symbol=None):
    """Return (path, text, rows) for latest trade log, or (None, None, []) if missing."""
    if symbol is None:
        symbol = SYMBOL
    files = sorted(Path(COMMON_FILES_DIR).glob(f"TradeLog_{symbol}_*.csv"), reverse=True)
    if not files:
        return None, None, []
    fp = files[0]
    text = _read_file_with_fallback(fp)
    if text is None:
        return fp, None, []
    rows = text.splitlines()
    return fp, text, rows


# ---------------------------------------------------------------------------
# Core Monitor
# ---------------------------------------------------------------------------

class AutoTrade1Monitor:
    """Single-cycle AutoTrade1 health check. Returns structured results."""

    def __init__(self):
        self.result = {
            "timestamp": _now().isoformat(),
            "mt5_connected": False,
            "account_match": False,
            "terminal_connected": False,
            "algo_enabled": False,
            "symbol_ok": False,
            "symbol_bid": None,
            "profile_exists": False,
            "ea_evidence": False,
            "tick_log": None,
            "tick_rows": 0,
            "tick_size": 0,
            "tick_size_prev": 0,
            "tick_latest_time": None,
            "tick_latest_dt": None,
            "tick_stale_seconds": None,
            "tick_growing": True,
            "trade_log": None,
            "trade_rows": 0,
            "warnings": [],
            "criticals": [],
        }

    def _check_api(self):
        if not mt5.initialize():
            self.result["mt5_connected"] = False
            self.result["criticals"].append("MT5 API init failed")
            return False

        account = mt5.account_info()
        if not account:
            self.result["mt5_connected"] = False
            self.result["criticals"].append("No account info")
            mt5.shutdown()
            return False

        self.result["mt5_connected"] = True
        self.result["account_match"] = account.login == ACCOUNT_LOGIN
        if not self.result["account_match"]:
            self.result["warnings"].append(
                f"Account mismatch: {account.login} != {ACCOUNT_LOGIN}"
            )

        terminal = mt5.terminal_info()
        self.result["terminal_connected"] = bool(terminal and terminal.connected)
        if not self.result["terminal_connected"]:
            self.result["criticals"].append("Terminal disconnected from trade server")

        self.result["algo_enabled"] = bool(account.trade_allowed)
        if not self.result["algo_enabled"]:
            self.result["warnings"].append("Algo trading is DISABLED")

        tick = mt5.symbol_info_tick(SYMBOL)
        self.result["server_tick_time"] = tick.time if tick else 0
        if tick:
            utc_now = datetime.now(timezone.utc)
            self.result["_gmt_offset"] = tick.time - int(utc_now.timestamp())

        sym = mt5.symbol_info(SYMBOL)
        if sym and sym.visible:
            self.result["symbol_ok"] = True
            self.result["symbol_bid"] = sym.bid
        else:
            self.result["warnings"].append(f"{SYMBOL} not visible in Market Watch")

        mt5.shutdown()
        return True

    def _check_profile(self):
        exists = os.path.isdir(PROFILE_DIR)
        self.result["profile_exists"] = exists
        if not exists:
            self.result["warnings"].append("AutoTrade1 profile directory missing")

    def _check_logs(self):
        today = _today_str()

        term_log = os.path.join(TERMINAL_LOG_DIR, f"{today}.log")
        if os.path.isfile(term_log):
            found, _, _ = _read_log_lines(term_log, EA_NAME, ["loaded", "initialized"])
            self.result["ea_evidence"] = found
            if not found:
                self.result["warnings"].append(
                    "EA evidence not found in terminal logs"
                )

    def _check_tick_log(self):
        fp, text, rows = _read_tick_log()
        if fp is None:
            self.result["warnings"].append("No EURUSD tick log found")
            return

        self.result["tick_log"] = str(fp)
        self.result["tick_rows"] = max(0, len(rows) - 1)
        self.result["tick_size"] = fp.stat().st_size if fp.exists() else 0

        if len(rows) > 1:
            last_cols = rows[-1].split(",")
            self.result["tick_latest_time"] = last_cols[0] if last_cols else None

            if self.result["tick_latest_time"]:
                try:
                    parts = self.result["tick_latest_time"].split(":")
                    if len(parts) == 3:
                        h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                        sec = int(s)
                        ms = int((s - sec) * 1_000_000)
                        gmt_off = self.result.get("_gmt_offset", 0)
                        utc_now = datetime.now(timezone.utc)
                        # CSV tick time is in SERVER time; convert to UTC
                        tick_utc_sec = (h * 3600 + m * 60 + sec) - gmt_off
                        now_utc_sec = utc_now.hour * 3600 + utc_now.minute * 60 + utc_now.second
                        age = (now_utc_sec - tick_utc_sec) % 86400
                        if age > 43200:
                            age -= 86400
                        tick_dt = _now().replace(hour=h, minute=m, second=sec, microsecond=ms)
                        self.result["tick_latest_dt"] = tick_dt.isoformat()
                        self.result["tick_stale_seconds"] = int(age)

                        if age > STALE_CRIT_SEC:
                            self.result["criticals"].append(
                                f"Tick stale for {int(age)}s (>{STALE_CRIT_SEC}s)"
                            )
                        elif age > STALE_WARN_SEC:
                            self.result["warnings"].append(
                                f"Tick stale for {int(age)}s (>{STALE_WARN_SEC}s)"
                            )
                except (ValueError, IndexError):
                    pass

    def _check_trade_log(self):
        fp, text, rows = _read_trade_log()
        if fp is None:
            self.result["warnings"].append("No EURUSD trade log found")
            return
        self.result["trade_log"] = str(fp)
        self.result["trade_rows"] = max(0, len(rows) - 1)

    def run(self):
        self._check_api()
        self._check_profile()
        self._check_logs()
        self._check_tick_log()
        self._check_trade_log()
        return self.result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _get_status_label(result):
    n_crit = len(result.get("criticals", []))
    n_warn = len(result.get("warnings", []))
    return "CRITICAL" if n_crit else "WARNING" if n_warn else "PASS"


def _write_state(result, restart_count=0, last_restart_time=0, session_start=None):
    """Write runtime state JSON for autotrade1-status to read."""
    os.makedirs(RUNTIME_STATE_DIR, exist_ok=True)
    now_ts = _now()
    uptime = 0
    if session_start:
        try:
            uptime = int((now_ts - datetime.fromisoformat(session_start)).total_seconds())
        except Exception:
            pass
    state = {
        "status": _get_status_label(result),
        "last_check_time": now_ts.isoformat(),
        "mt5_connected": result.get("mt5_connected", False),
        "account_match": result.get("account_match", False),
        "algo_enabled": result.get("algo_enabled", False),
        "symbol": SYMBOL,
        "latest_tick_time": result.get("tick_latest_time"),
        "tick_age_seconds": result.get("tick_stale_seconds"),
        "tick_rows": result.get("tick_rows", 0),
        "trade_rows": result.get("trade_rows", 0),
        "warnings": result.get("warnings", []),
        "criticals": result.get("criticals", []),
        "restart_count": restart_count,
        "last_restart_time": datetime.fromtimestamp(last_restart_time).isoformat() if last_restart_time else None,
        "uptime_seconds": uptime,
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, STATE_FILE)
    return STATE_FILE

def _format_status_compact(result):
    """One-line compact status for monitor loop."""
    now_str = _now().strftime("%Y-%m-%d %H:%M:%S")
    tick_age = result.get("tick_stale_seconds")
    age_str = f"{tick_age}s" if tick_age is not None else "?"
    n_warn = len(result.get("warnings", []))
    n_crit = len(result.get("criticals", []))
    errors = n_warn + n_crit
    return (
        f"[{now_str}] "
        f"{'CRITICAL' if n_crit else 'WARNING' if n_warn else 'PASS'} | "
        f"EURUSD tick age={age_str} | "
        f"tick rows={result.get('tick_rows', 0)} | "
        f"trade rows={result.get('trade_rows', 0)} | "
        f"MT5 connected={'yes' if result.get('mt5_connected') else 'no'} | "
        f"errors={errors}"
    )


def _write_report(result, session_start=None, session_end=None,
                   restart_count=0, final_status=None):
    os.makedirs(RUNTIME_REPORT_DIR, exist_ok=True)
    ts = _now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RUNTIME_REPORT_DIR, f"autotrade1_status_{ts}.json")

    report = {
        "session_start": session_start or result.get("timestamp"),
        "session_end": session_end or _now().isoformat(),
        "profile": PROFILE_NAME,
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME_NAME,
        "ea_name": EA_NAME,
        "account": ACCOUNT_LOGIN,
        "server": "MetaQuotes-Demo",
        "mt5_connected": result.get("mt5_connected"),
        "algo_trading": result.get("algo_enabled"),
        "tick_log_path": result.get("tick_log"),
        "trade_log_path": result.get("trade_log"),
        "latest_tick_time": result.get("tick_latest_time"),
        "tick_rows": result.get("tick_rows", 0),
        "trade_rows": result.get("trade_rows", 0),
        "errors_found": len(result.get("criticals", [])),
        "warnings_found": len(result.get("warnings", [])),
        "restart_count": restart_count,
        "final_status": final_status or (
            "CRITICAL" if result.get("criticals")
            else "WARNING" if result.get("warnings")
            else "PASS"
        ),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_run(args):
    """Full workflow: launch -> verify -> logger -> monitor."""
    session_start = _now().isoformat()
    print()

    print("[1/6] Launching AutoTrade1...")
    launch_result = launch_mt5.main()
    if not launch_result.get("success"):
        report = {
            "mt5_connected": False, "algo_enabled": False,
            "tick_rows": 0, "trade_rows": 0,
            "warnings": ["Launch failed"], "criticals": ["Launch failed"],
        }
        _write_report(report, session_start, final_status="FAIL")
        return

    print("[2/6] Running verify-autotrade1 checks...")
    from verify_autotrade1 import verify, print_report
    verify_result = verify()
    print_report(verify_result)

    print("[3/6] Running verify-logger-eurusd checks...")
    monitor = AutoTrade1Monitor()
    result = monitor.run()

    tick_status = "Found" if result.get("tick_log") else "Missing"
    trade_status = "Found" if result.get("trade_log") else "Missing"
    print(f"  Tick Log: {tick_status}")
    print(f"  Trade Log: {trade_status}")

    print("[4/6] Logger summary...")
    from tradecore_reader import CoreLoggerAnalytics
    analysis = CoreLoggerAnalytics()
    analysis.load_all(days=args.days)
    summary = analysis.market_summary()
    if SYMBOL in summary:
        s = summary[SYMBOL]
        if "error" not in s:
            print(
                f"  {SYMBOL}: ticks={s.get('tick_count', 0)} "
                f"trades={s.get('trade_count', 0)} "
                f"bid={s.get('price_current', 0):.5f} "
                f"mode={s.get('last_mode', '?')}"
            )

    print()
    print("AUTOTRADE1 RUNTIME STARTED")
    print(f"Profile: {PROFILE_NAME}")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME_NAME}")
    print(f"EA: {EA_NAME}")
    print(f"MT5 Connected: {'Yes' if result.get('mt5_connected') else 'No'}")
    print(f"Account: {ACCOUNT_LOGIN}")
    print(f"Algo Trading: {'Enabled' if result.get('algo_enabled') else 'Disabled'}")
    print(f"Tick Log: {tick_status}")
    print(f"Trade Log: {trade_status}")
    print(f"Latest Tick: {result.get('tick_latest_time', 'N/A')}")
    print(f"Runtime Monitor: Started")

    report_path = _write_report(result, session_start, final_status="RUNNING")
    print(f"Report: {report_path}")
    _write_state(result, session_start=session_start)

    if args.no_monitor:
        return

    print()
    print("--- Monitoring (Ctrl+C to stop) ---")
    _monitor_loop(interval=args.interval, max_minutes=args.max_minutes)


def cmd_monitor(args):
    """Continuous monitoring loop."""
    if args.once:
        m = AutoTrade1Monitor()
        r = m.run()
        _write_state(r)
        print(_format_status_compact(r))
        return

    _monitor_loop(interval=args.interval, max_minutes=args.max_minutes)


def cmd_watchdog(args):
    """Recovery mode: auto-restart MT5 if needed. Smart restart decisions."""
    print()
    print("AUTOTRADE1 WATCHDOG ACTIVE")
    print("Restart Policy: smart (no restart for stale ticks alone)")
    print(f"Cooldown: {RESTART_COOLDOWN_SEC // 60} minutes")
    print(f"Max Restarts Per Hour: {MAX_RESTARTS_PER_HOUR}")
    print()

    restart_count = 0
    last_restart_time = 0
    hour_restarts = []
    session_start = _now().isoformat()

    disconnected_cycles = 0
    unreadable_cycles = 0
    prev_tick_size = None
    tick_frozen_cycles = 0

    while True:
        m = AutoTrade1Monitor()
        r = m.run()
        status = _format_status_compact(r)
        print(status, flush=True)
        _write_state(r, restart_count, last_restart_time, session_start)

        now = _now()
        hour_restarts = [t for t in hour_restarts if (now - t).total_seconds() < 3600]

        if len(hour_restarts) >= MAX_RESTARTS_PER_HOUR:
            print(f"  CRITICAL: Max restarts ({MAX_RESTARTS_PER_HOUR}/h) reached")
            _write_report(r, session_start, restart_count=restart_count,
                          final_status="CRITICAL")
            return

        # --- Decide if restart is needed (Task 6 improved rules) ---
        needs_restart = False
        restart_reason = ""

        # 1. MT5 API cannot initialize
        if not r.get("mt5_connected"):
            needs_restart = True
            restart_reason = "MT5 not connected via API"
            disconnected_cycles += 1
        else:
            disconnected_cycles = 0

        # 2. terminal_info.connected false for 2 consecutive cycles
        if not r.get("terminal_connected") and r.get("mt5_connected"):
            disconnected_cycles += 1
            if disconnected_cycles >= MT5_RECONNECT_CYCLES:
                needs_restart = True
                restart_reason = f"Terminal disconnected for {disconnected_cycles} cycles"
        elif r.get("terminal_connected"):
            disconnected_cycles = 0

        # 3. Account mismatch
        if r.get("mt5_connected") and not r.get("account_match"):
            needs_restart = True
            restart_reason = "Account mismatch"

        # 4. Profile missing
        if not r.get("profile_exists"):
            needs_restart = True
            restart_reason = "Profile directory missing"

        # 5. Logger files unreadable for 3 consecutive cycles
        if r.get("mt5_connected") and not r.get("tick_log"):
            unreadable_cycles += 1
            if unreadable_cycles >= 3:
                needs_restart = True
                restart_reason = f"Tick log unreadable for {unreadable_cycles} cycles"
        else:
            unreadable_cycles = 0

        # 6. Tick log stopped growing for 5+ minutes while connected
        if r.get("mt5_connected") and r.get("tick_size") is not None:
            cur_size = r["tick_size"]
            if prev_tick_size is not None and cur_size == prev_tick_size:
                tick_frozen_cycles += 1
                frozen_sec = tick_frozen_cycles * args.interval
                if frozen_sec >= 300:
                    needs_restart = True
                    restart_reason = f"Tick log frozen {frozen_sec}s (size={cur_size})"
            else:
                tick_frozen_cycles = 0
            prev_tick_size = cur_size

        # Do NOT restart for stale tick alone -- only restart for infra failures

        if needs_restart:
            since_last = (now.timestamp() - last_restart_time) if last_restart_time else RESTART_COOLDOWN_SEC + 1
            if since_last < RESTART_COOLDOWN_SEC:
                print(f"  Cooldown: {int(RESTART_COOLDOWN_SEC - since_last)}s remaining")
                time.sleep(args.interval)
                continue

            print(f"  Restarting MT5... reason: {restart_reason}")
            restart_count += 1
            hour_restarts.append(now)
            last_restart_time = now.timestamp()

            launch_result = launch_mt5.main()
            if launch_result.get("success"):
                print("  Restart OK. Running verify...")
                from verify_autotrade1 import verify, print_report
                vr = verify()
                print_report(vr)

                _write_report(r, session_start, restart_count=restart_count,
                              final_status="RESTARTED")
            else:
                print("  Restart FAILED")
                _write_report(r, session_start, restart_count=restart_count,
                              final_status="RESTART_FAILED")

            disconnected_cycles = 0
            unreadable_cycles = 0
            tick_frozen_cycles = 0
            prev_tick_size = None

        time.sleep(args.interval)


def _monitor_loop(interval=30, max_minutes=0, callback=None):
    start = _now()
    max_seconds = max_minutes * 60 if max_minutes > 0 else None

    while True:
        if max_seconds and (_now() - start).total_seconds() > max_seconds:
            print("Max duration reached, stopping.")
            break

        m = AutoTrade1Monitor()
        r = m.run()
        status = _format_status_compact(r)
        print(status, flush=True)
        _write_state(r, session_start=start.isoformat())

        if callback:
            callback(r)

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped by user.", flush=True)
            break
