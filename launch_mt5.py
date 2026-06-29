"""
launch_mt5.py

Cold-start MT5 with the AutoTrade1 profile using native MT5 mechanisms only.
Pipeline: kill -> generate config -> launch with /config -> wait -> verify
"""

import os
import time
import subprocess

import psutil
import win32con
import win32gui

import MetaTrader5 as mt5

from autotrade1_config import SCRIPT_DIR, MT5_INSTALL_DIR, TERMINAL_EXE, DATA_DIR
from autotrade1_config import CONFIG_PATH, PROFILE_NAME, PROFILE_DIR, EA_NAME, SYMBOL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_mt5_processes():
    return [p for p in psutil.process_iter(["pid", "name", "exe"])
            if p.info["name"] and "terminal64" in p.info["name"].lower()]


def find_mt5_window():
    def enum_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "MetaTrader" in title and "5" in title:
                results.append(hwnd)
        return True

    hwnds = []
    win32gui.EnumWindows(enum_callback, hwnds)
    return hwnds[0] if hwnds else None


def kill_mt5(timeout=15):
    procs = find_mt5_processes()
    if not procs:
        print("No MT5 processes running.")
        return 0

    hwnd = find_mt5_window()

    if hwnd:
        print(f"Sending WM_CLOSE to MT5 window (hwnd={hwnd})...")
        win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    else:
        print("No MT5 window found, terminating processes directly...")
        for p in procs:
            p.terminate()

    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = find_mt5_processes()
        if not remaining:
            print("MT5 exited cleanly.")
            return 1
        time.sleep(0.5)

    print(f"MT5 did not exit within {timeout}s, force killing...")
    for p in remaining:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(1)
    return 1


def check_profile():
    if os.path.isdir(PROFILE_DIR):
        files = os.listdir(PROFILE_DIR)
        print(f"Profile '{PROFILE_NAME}' found ({len(files)} files) -> {PROFILE_DIR}")
        return True
    print(f"WARNING: Profile '{PROFILE_NAME}' not found at: {PROFILE_DIR}")
    print("Create it manually: open MT5 -> arrange EURUSD M5 + tradeCorelogger_v2.2 -> Save Profile As -> AutoTrade1")
    return False


def wait_for_process(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        procs = find_mt5_processes()
        if procs:
            pid = procs[0].info["pid"]
            print(f"MT5 process started (pid={pid})")
            return pid
        time.sleep(0.5)
    raise RuntimeError(f"MT5 did not start within {timeout}s")


def connect_mt5_api(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mt5.initialize():
            print("MetaTrader5 API connected.")
            return True
        time.sleep(1)
    raise RuntimeError(f"Could not connect to MetaTrader5 API within {timeout}s")


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


def print_success(result):
    a = result["account"]
    status = "PASS" if result["success"] else "FAIL"
    print(f"""
AUTOTRADE1 LAUNCH: {status}
Account:  {a['login']}
Server:   {a['server']}
Profile:  {PROFILE_NAME}
Symbol:   {SYMBOL}
Algo Trading: {'Enabled' if result['algo_ok'] else 'Disabled'}
MT5 Connected: {'Yes' if result['connected'] else 'No'}
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import generate_launch_config

    env = generate_launch_config.load_credentials()

    print("[1/5] Killing existing MT5...")
    kill_mt5()

    print()
    print("[2/5] Generating launch config...")
    generate_launch_config.generate(**env)

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

    print_success(result)
    return result


if __name__ == "__main__":
    result = main()
    exit(0 if result.get("success") else 1)
