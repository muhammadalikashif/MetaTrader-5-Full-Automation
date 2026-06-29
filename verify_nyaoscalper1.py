"""
verify_nyaoscalper1.py

Verifies that the NyaoScalper1 profile loaded correctly after a cold launch.
Checks: MT5 API, account, profile files, symbol, log evidence.
"""

import os
from datetime import date

import MetaTrader5 as mt5

from nyaoscalper1_config import DATA_DIR, PROFILE_DIR, TERMINAL_LOG_DIR, MQL5_LOG_DIR
from nyaoscalper1_config import ACCOUNT_LOGIN, SYMBOL, EA_NAME, PROFILE_NAME, TIMEFRAME_NAME, PRESET

EXPECTED_CHART_FILE = "chart01.chr"
POSITIVE_TERMS = ["initialized", "loaded successfully"]
ERROR_TERMS = ["error", "cannot", "failed", "license"]


def read_utf16_le(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        pass
    try:
        with open(path, "r", encoding="utf-16-le") as f:
            text = f.read()
            if text and text[0] == "\ufeff":
                text = text[1:]
            return text
    except Exception:
        return None


def search_terminallog(log_dir, today_str, ea_name):
    results = {"ea_found": False, "errors": [], "lines": []}
    log_path = os.path.join(log_dir, f"{today_str}.log")
    if not os.path.isfile(log_path):
        return results

    for enc in ("utf-16-le", "utf-8", "utf-8-sig"):
        try:
            with open(log_path, "r", encoding=enc) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    lower = line.lower()
                    if ea_name.lower() in lower:
                        results["lines"].append(line)
                        if any(t in lower for t in POSITIVE_TERMS):
                            results["ea_found"] = True
                    for term in ERROR_TERMS:
                        if term in lower:
                            results["errors"].append((f"'{term}'", line))
            break
        except (UnicodeDecodeError, Exception):
            continue
    return results


def search_mql5log(log_dir, today_str, ea_name):
    results = {"ea_found": False, "errors": [], "lines": []}
    log_path = os.path.join(log_dir, f"{today_str}.log")
    if not os.path.isfile(log_path):
        return results

    text = read_utf16_le(log_path)
    if text is None:
        return results

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if ea_name.lower() in lower:
            results["lines"].append(line)
            if any(t in lower for t in POSITIVE_TERMS):
                results["ea_found"] = True
        for term in ERROR_TERMS:
            if term in lower:
                results["errors"].append((f"'{term}'", line))
    return results


def verify():
    result = {
        "mt5_connected": False,
        "account_match": False,
        "account_login": None,
        "profile_folder": False,
        "chart_file": False,
        "symbol_ok": False,
        "symbol_bid": None,
        "ea_log_evidence": False,
        "ea_log_lines": [],
        "error_count": 0,
        "errors_short": [],
    }

    today_str = date.today().strftime("%Y%m%d")

    if not mt5.initialize():
        return result

    try:
        result["mt5_connected"] = True

        account = mt5.account_info()
        if account:
            result["account_login"] = account.login
            result["account_match"] = account.login == ACCOUNT_LOGIN

        terminal = mt5.terminal_info()
        connected = bool(terminal and terminal.connected)
        result["mt5_connected"] = result["mt5_connected"] and connected

        symbol_info = mt5.symbol_info(SYMBOL)
        if symbol_info:
            result["symbol_bid"] = symbol_info.bid
            result["symbol_ok"] = symbol_info.visible and symbol_info.bid > 0
    finally:
        mt5.shutdown()

    result["profile_folder"] = os.path.isdir(PROFILE_DIR)
    chart_path = os.path.join(PROFILE_DIR, EXPECTED_CHART_FILE)
    result["chart_file"] = os.path.isfile(chart_path)

    terms_result = search_terminallog(TERMINAL_LOG_DIR, today_str, EA_NAME)
    mql5_result = search_mql5log(MQL5_LOG_DIR, today_str, EA_NAME)

    result["ea_log_evidence"] = terms_result["ea_found"] or mql5_result["ea_found"]
    result["ea_log_lines"] = terms_result["lines"] + mql5_result["lines"]

    all_errors = terms_result["errors"] + mql5_result["errors"]
    seen = set()
    for label, line in all_errors:
        if line not in seen:
            seen.add(line)
            result["errors_short"].append(f"{label}: {line[:120]}")
    result["error_count"] = len(result["errors_short"])

    return result


def print_report(result):
    n_errors = result.get("error_count", 0)
    fail_checks = [
        result.get("mt5_connected"),
        result.get("account_match"),
        result.get("profile_folder"),
        result.get("chart_file"),
        result.get("symbol_ok"),
    ]
    if all(fail_checks):
        if result.get("ea_log_evidence"):
            status = "PASS"
        else:
            status = "WARNING"
    else:
        status = "FAIL"

    print()
    print(f"NYAOSCALPER1 VERIFY REPORT")
    print(f"{'MT5 Connected:':30} {'Yes' if result['mt5_connected'] else 'No'}")
    print(f"{'Account:':30} {'OK' if result['account_match'] else 'Mismatch'}")
    print(f"{'Profile Folder:':30} {'Found' if result['profile_folder'] else 'Missing'}")
    print(f"{'Chart File:':30} {'Found' if result['chart_file'] else 'Missing'}")
    print(f"{'Symbol:':30} {SYMBOL}")
    print(f"{'Timeframe:':30} {TIMEFRAME_NAME}")
    print(f"{'Preset:':30} {PRESET}")
    print(f"{'Tick:':30} {'OK' if result['symbol_ok'] else 'Missing'} (bid={result['symbol_bid']})")
    print(f"{'EA Evidence:':30} {'Found' if result['ea_log_evidence'] else 'Not Found'}")
    if result['ea_log_lines']:
        for line in result['ea_log_lines'][:3]:
            safe = line.encode('ascii', errors='replace').decode('ascii')[:120]
            print(f"{'':30} {safe}")
    print(f"{'Errors Found:':30} {n_errors}")
    for err in result['errors_short'][:5]:
        safe = err.encode('ascii', errors='replace').decode('ascii')[:120]
        print(f"{'':30} {safe}")
    print(f"{'Final Status:':30} {status}")
    print()

    return result


if __name__ == "__main__":
    r = verify()
    print_report(r)
    ok = all([r.get("mt5_connected"), r.get("account_match"), r.get("profile_folder"), r.get("chart_file")])
    exit(0 if ok else 1)
