"""
nyaoscalper1_runtime.py

NyaoScalper1 automation runtime: cold launch and one-shot monitor.
No trade placement, no EA input changes, no profile modification, no watchdog.
"""

import os
import time
import subprocess
from datetime import date

import MetaTrader5 as mt5

import generate_launch_config
from launch_mt5 import kill_mt5, find_mt5_processes, wait_for_process, connect_mt5_api

from nyaoscalper1_config import (
    SCRIPT_DIR, MT5_INSTALL_DIR, TERMINAL_EXE, DATA_DIR,
    CONFIG_PATH, CONFIG_DIR, PROFILE_NAME, PROFILE_DIR, EA_NAME, SYMBOL,
    ACCOUNT_LOGIN, TERMINAL_LOG_DIR, MQL5_LOG_DIR,
)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------


def check_profile():
    if os.path.isdir(PROFILE_DIR):
        files = os.listdir(PROFILE_DIR)
        print(f"Profile '{PROFILE_NAME}' found ({len(files)} files) -> {PROFILE_DIR}")
        return True
    print(f"WARNING: Profile '{PROFILE_NAME}' not found at: {PROFILE_DIR}")
    return False


def verify_launch():
    result = {"success": False, "account": None, "symbol_ok": False, "algo_ok": False, "connected": False}

    account = mt5.account_info()
    if not account:
        print("ERROR: No account info available.")
        return result

    terminal = mt5.terminal_info()

    result["account"] = {
        "login": account.login,
        "server": account.server,
        "balance": account.balance,
        "equity": account.equity,
    }
    result["algo_ok"] = bool(account.trade_allowed)
    result["connected"] = bool(terminal and terminal.connected)

    symbol_info = mt5.symbol_info(SYMBOL)
    result["symbol_ok"] = bool(symbol_info and symbol_info.visible)

    return result


def launch():
    print("[1/5] Killing existing MT5...")
    kill_mt5()

    print()
    print("[2/5] Generating launch config...")
    creds = generate_launch_config.load_credentials()
    os.makedirs(CONFIG_DIR, exist_ok=True)
    generate_launch_config.generate(
        login=creds["login"],
        password=creds["password"],
        server=creds["server"],
        profile_name=PROFILE_NAME,
        out_path=CONFIG_PATH,
    )

    print()
    print("[3/5] Checking profile...")
    profile_ok = check_profile()

    print()
    print("[4/5] Launching MT5...")
    cmd = [TERMINAL_EXE, f"/config:{CONFIG_PATH}", f"/profile:{PROFILE_NAME}"]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.Popen(cmd, cwd=MT5_INSTALL_DIR)
    mt5_pid = wait_for_process()
    print(f"  PID: {mt5_pid}")

    print()
    print("[5/5] Verifying via MetaTrader5 API...")
    result = {}
    try:
        connect_mt5_api()
        print()
        result = verify_launch()
    finally:
        mt5.shutdown()

    result["success"] = (
        profile_ok
        and result.get("algo_ok", False)
        and result.get("symbol_ok", False)
        and result.get("connected", False)
    )

    a = result["account"]
    status = "PASS" if result["success"] else "FAIL"
    print(f"""
NYAOSCALPER1 LAUNCH: {status}
Account:  {a['login']}
Server:   {a['server']}
Profile:  {PROFILE_NAME}
Symbol:   {SYMBOL}
Algo Trading: {'Enabled' if result['algo_ok'] else 'Disabled'}
MT5 Connected: {'Yes' if result['connected'] else 'No'}
""")

    return result


# ---------------------------------------------------------------------------
# One-shot monitor
# ---------------------------------------------------------------------------


class NyaoScalper1Monitor:
    """Single-cycle NyaoScalper1 health check. No trade logging, no watchdog."""

    def __init__(self):
        self.result = {
            "timestamp": None,
            "mt5_connected": False,
            "account_match": False,
            "algo_enabled": False,
            "symbol_ok": False,
            "symbol_bid": None,
            "profile_exists": False,
            "ea_evidence": False,
            "warnings": [],
            "criticals": [],
        }

    def run(self):
        from datetime import datetime

        self.result["timestamp"] = datetime.now().isoformat()
        self._check_api()
        self._check_profile()
        self._check_logs()
        return self.result

    def _check_api(self):
        if not mt5.initialize():
            self.result["mt5_connected"] = False
            self.result["criticals"].append("MT5 API init failed")
            return

        account = mt5.account_info()
        if not account:
            self.result["mt5_connected"] = False
            self.result["criticals"].append("No account info")
            mt5.shutdown()
            return

        self.result["mt5_connected"] = True
        self.result["account_match"] = account.login == ACCOUNT_LOGIN
        if not self.result["account_match"]:
            self.result["warnings"].append(
                f"Account mismatch: {account.login} != {ACCOUNT_LOGIN}"
            )

        self.result["algo_enabled"] = bool(account.trade_allowed)
        if not self.result["algo_enabled"]:
            self.result["warnings"].append("Algo trading is DISABLED")

        tick = mt5.symbol_info_tick(SYMBOL)
        if tick:
            self.result["symbol_ok"] = tick.bid > 0
            self.result["symbol_bid"] = tick.bid
        else:
            self.result["warnings"].append(f"No tick data for {SYMBOL}")

        mt5.shutdown()

    def _check_profile(self):
        self.result["profile_exists"] = os.path.isdir(PROFILE_DIR)
        if not self.result["profile_exists"]:
            self.result["warnings"].append("NyaoScalper1 profile directory missing")

    def _check_logs(self):
        today = date.today().strftime("%Y%m%d")

        for log_dir, label in [(TERMINAL_LOG_DIR, "terminal"), (MQL5_LOG_DIR, "MQL5")]:
            log_path = os.path.join(log_dir, f"{today}.log")
            if not os.path.isfile(log_path):
                continue
            for enc in ("utf-16-le", "utf-8", "utf-8-sig"):
                try:
                    with open(log_path, "r", encoding=enc) as f:
                        for line in f:
                            lower = line.lower()
                            if EA_NAME.lower() in lower:
                                if any(t in lower for t in ("initialized", "loaded", "success")):
                                    self.result["ea_evidence"] = True
                            for term in ("error", "cannot", "failed"):
                                if term in lower and EA_NAME.lower() in lower:
                                    self.result["criticals"].append(
                                        f"{label} log: {line.strip()[:150]}"
                                    )
                    break
                except (UnicodeDecodeError, Exception):
                    continue


def cmd_launch(args):
    result = launch()
    return result


def cmd_monitor(args):
    m = NyaoScalper1Monitor()
    r = m.run()

    n_warn = len(r.get("warnings", []))
    n_crit = len(r.get("criticals", []))
    status = "CRITICAL" if n_crit else "WARNING" if n_warn else "PASS"

    from datetime import datetime

    print()
    print(f"NYAOSCALPER1 MONITOR  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'MT5 Connected:':25} {'Yes' if r['mt5_connected'] else 'No'}")
    print(f"{'Account:':25} {'OK' if r['account_match'] else 'Mismatch'}")
    print(f"{'Algo Trading:':25} {'Enabled' if r['algo_enabled'] else 'Disabled'}")
    print(f"{'Profile:':25} {'Found' if r['profile_exists'] else 'Missing'}")
    print(f"{'EURUSD Tick:':25} {'OK' if r['symbol_ok'] else 'Missing'} (bid={r['symbol_bid']})")
    print(f"{'EA Evidence:':25} {'Found' if r['ea_evidence'] else 'Not Found'}")
    print(f"{'Warnings:':25} {n_warn}")
    for w in r["warnings"]:
        print(f"{'':25} {w[:120]}")
    print(f"{'Criticals:':25} {n_crit}")
    for c in r["criticals"]:
        print(f"{'':25} {c[:120]}")
    print(f"{'Status:':25} {status}")
    print()

    return r
