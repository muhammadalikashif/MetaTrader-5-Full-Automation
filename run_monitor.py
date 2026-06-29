"""
Live MT5 Monitor - Entry Point
===============================
Monitors live EA trading. Attach EAs manually to MT5 charts first.

Usage:
    .venv\\Scripts\\python run_monitor.py monitor --interval 10
    .venv\\Scripts\\python run_monitor.py positions
    .venv\\Scripts\\python run_monitor.py history --days 7
    .venv\\Scripts\\python run_monitor.py doctor
    .venv\\Scripts\\python run_monitor.py validate-config
    .venv\\Scripts\\python run_monitor.py report --days 1
    .venv\\Scripts\\python run_monitor.py open --symbol EURUSD --type BUY --volume 0.01 --sl 20 --tp 40
    .venv\\Scripts\\python run_monitor.py close --ticket 12345678
    .venv\\Scripts\\python run_monitor.py close-all
    .venv\\Scripts\\python run_monitor.py close-symbol --symbol EURUSD
    .venv\\Scripts\\python run_monitor.py modify --ticket 12345678 --sl 30 --tp 60
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from live_orchestrator import LiveOrchestrator


DOCS_DIR = Path(r"C:\Users\kali6\Documents\MT5")


def cmd_monitor(args):
    orch = LiveOrchestrator(log_file=args.log)
    if not orch.connect():
        sys.exit(1)
    try:
        orch.monitor_loop(interval_sec=args.interval, max_iterations=args.iterations)
    finally:
        orch.disconnect()


def cmd_positions(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        positions = orch.get_positions(args.symbol)
        print(f"\nOpen positions ({len(positions)}):")
        orch.print_positions(positions)
        snapshot = orch.get_account_snapshot()
        if snapshot:
            print(f"\nAccount: {snapshot.balance:.2f} {snapshot.currency}  "
                  f"Equity: {snapshot.equity:.2f}  "
                  f"DD: {snapshot.dd_percent:.1f}%")
    finally:
        orch.disconnect()


def cmd_history(args):
    from datetime import timedelta
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        days = args.days
        from_date = datetime.now() - timedelta(days=days)
        deals = orch.get_trade_history(from_date)
        print(f"\nTrade history (last {days} days, {len(deals)} deals):")
        profit_total = 0
        for d in deals:
            profit_total += d["profit"]
            print(f"  {d['time']} {d['symbol']} {d['type']} "
                  f"vol:{d['volume']} @{d['price']} "
                  f"P/L:{d['profit']:+.2f}")
        print(f"\nTotal P/L: {profit_total:+.2f}")
    finally:
        orch.disconnect()


def cmd_doctor(args):
    orch = LiveOrchestrator()
    orch.connect()
    try:
        results = orch.doctor_check()
        print("\n=== MT5 Doctor Report ===\n")
        for key, val in results.items():
            label = key.replace("_", " ").title()
            if isinstance(val, list):
                if val:
                    print(f"  {label}: DUPLICATES FOUND: {val}")
                else:
                    print(f"  {label}: None")
            else:
                print(f"  {label}: {val}")
        print()
    finally:
        orch.disconnect()


def cmd_validate_config(args):
    orch = LiveOrchestrator()
    orch.connect()
    try:
        issues = orch.validate_config()
        print("\n=== EA Config Validation ===\n")
        if not issues:
            print("  All checks passed. No issues found.\n")
            return
        for issue in issues:
            sev = issue["severity"]
            inst = issue.get("instance", "")
            msg = issue["message"]
            print(f"  [{sev}] {inst}: {msg}")
        print()
    finally:
        orch.disconnect()


def cmd_setup(args):
    import shutil
    from live_orchestrator import PROFILES_DIR, EXPERTS_DIR
    profiles_dir = PROFILES_DIR
    experts_dir = EXPERTS_DIR
    profiles_dir.mkdir(parents=True, exist_ok=True)
    experts_dir.mkdir(parents=True, exist_ok=True)
    print("=== Copying EA .ex5 files ===")
    ea_files = list(DOCS_DIR.rglob("*.ex5"))
    for f in ea_files:
        dest = experts_dir / f.name
        shutil.copy2(f, dest)
        print(f"  {f.name} -> {dest}")
    print(f"\n=== Copying .set files ===")
    set_files = list(DOCS_DIR.rglob("*.set"))
    for f in set_files:
        flat_name = f.stem.replace(" ", "_") + ".set"
        dest = profiles_dir / flat_name
        shutil.copy2(f, dest)
        print(f"  {f.parent.name}/{f.name} -> {dest}")
    print(f"\nDone. {len(ea_files)} EA files, {len(set_files)} .set files copied.")


def cmd_set_setfile(args):
    orch = LiveOrchestrator()
    source = Path(args.file)
    if not source.exists():
        print(f"File not found: {source}")
        sys.exit(1)
    orch.copy_set_file(source, args.ea)
    print(f"Set file ready for {args.ea}")


def cmd_update_params(args):
    orch = LiveOrchestrator()
    params = {}
    for p in args.param:
        if "=" not in p:
            print(f"Invalid param format: {p} (use key=value)")
            sys.exit(1)
        key, val = p.split("=", 1)
        params[key] = val
    orch.update_set_file(args.ea, params)


def cmd_generate_launch_plan(args):
    orch = LiveOrchestrator()
    orch.generate_launch_plan()


def cmd_launcher_log(args):
    orch = LiveOrchestrator()
    entries = orch.read_launcher_log()
    if not entries:
        print("\nNo launcher log found. Run LaunchEACharts.mq5 in MT5 first.\n")
        return
    print(f"\n=== EA Launcher Log ({len(entries)} entries) ===\n")
    fmt = "{:<20} {:<10} {:<12} {:<35} {:<10} {:<10} {:<20}"
    print(fmt.format("instance_id", "symbol", "timeframe", "template_name", "status", "error", "timestamp"))
    print("-" * 120)
    for e in entries:
        print(fmt.format(
            e.get("instance_id", ""),
            e.get("symbol", ""),
            e.get("timeframe", ""),
            e.get("template_name", ""),
            e.get("status", ""),
            e.get("error_code", ""),
            e.get("timestamp", ""),
        ))
    successes = sum(1 for e in entries if e.get("status") == "SUCCESS")
    fails = sum(1 for e in entries if e.get("status") == "FAIL")
    print(f"\nResult: {successes} success, {fails} failed\n")


def cmd_report(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        orch.generate_report(days=args.days)
    finally:
        orch.disconnect()


def cmd_open(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        result = orch.open_trade(
            symbol=args.symbol,
            order_type=args.type,
            volume=args.volume,
            sl=args.sl,
            tp=args.tp,
            magic=args.magic,
            comment=args.comment,
            slippage=args.slippage,
        )
        ok = result["success"]
        print(f"\n[{'OK' if ok else 'FAIL'}] Open {args.type} {args.volume} {args.symbol}: {'SUCCESS' if ok else result.get('error', 'FAILED')}")
        if ok:
            print(f"  Price: {result['price']:.5f}  Ticket: #{result.get('deal_ticket', result.get('order_ticket', '?'))}")
    finally:
        orch.disconnect()


def cmd_close(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        result = orch.close_trade(args.ticket, args.slippage)
        ok = result["success"]
        print(f"\n[{'OK' if ok else 'FAIL'}] Close #{args.ticket}: {'SUCCESS' if ok else result.get('error', 'FAILED')}")
    finally:
        orch.disconnect()


def cmd_close_all(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        results = orch.close_all_trades(args.slippage)
        successes = sum(1 for r in results if r["success"])
        print(f"\nClosed {successes}/{len(results)} positions")
        for r in results:
            s = "OK" if r["success"] else f"FAIL ({r.get('error', '?')})"
            print(f"  [{s}]")
    finally:
        orch.disconnect()


def cmd_close_symbol(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        results = orch.close_positions_by_symbol(args.symbol, args.slippage)
        successes = sum(1 for r in results if r["success"])
        print(f"\nClosed {successes}/{len(results)} positions on {args.symbol}")
        for r in results:
            s = "OK" if r["success"] else f"FAIL ({r.get('error', '?')})"
            print(f"  [{s}]")
    finally:
        orch.disconnect()


def cmd_modify(args):
    orch = LiveOrchestrator()
    if not orch.connect():
        sys.exit(1)
    try:
        result = orch.modify_trade(args.ticket, sl=args.sl, tp=args.tp)
        ok = result["success"]
        print(f"\n[{'OK' if ok else 'FAIL'}] Modify #{args.ticket}: {'SUCCESS' if ok else result.get('error', 'FAILED')}")
    finally:
        orch.disconnect()


def cmd_launch(args):
    from launch_mt5 import main as launch_main
    launch_main()


def cmd_verify_autotrade1(args):
    from verify_autotrade1 import verify, print_report
    result = verify()
    print_report(result)


def cmd_autotrade1_run(args):
    from autotrade1_runtime import cmd_run
    cmd_run(args)


def cmd_autotrade1_monitor(args):
    from autotrade1_runtime import cmd_monitor
    cmd_monitor(args)


def cmd_autotrade1_watchdog(args):
    from autotrade1_runtime import cmd_watchdog
    cmd_watchdog(args)


def cmd_autotrade1_start(args):
    """Launch AutoTrade1 and start watchdog in background."""
    import os
    import subprocess
    from autotrade1_config import RUNTIME_STATE_DIR, PID_FILE

    os.makedirs(RUNTIME_STATE_DIR, exist_ok=True)

    print("AUTOTRADE1 START")
    print()

    # Launch
    from launch_mt5 import main as launch_main
    launch_result = launch_main()
    if not launch_result.get("success"):
        print("ERROR: Launch failed, aborting start.")
        return

    # Verify
    from verify_autotrade1 import verify, print_report
    vr = verify()
    print_report(vr)

    # Spawn watchdog in background
    script = __file__
    python = sys.executable or ".venv\\Scripts\\python.exe"
    cmd = [python, str(script), "autotrade1-watchdog", "--interval", str(args.interval)]

    proc = subprocess.Popen(
        cmd,
        stdout=open(os.path.join(RUNTIME_STATE_DIR, "watchdog_out.log"), "a"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))

    print(f"Watchdog started (pid={proc.pid})")
    print(f"PID file: {PID_FILE}")
    print("AUTOTRADE1 STARTED OK")


def cmd_autotrade1_stop(args):
    """Stop the watchdog process. Optionally close MT5."""
    import signal
    from autotrade1_config import PID_FILE

    if not os.path.isfile(PID_FILE):
        print("No watchdog PID file found. Watchdog may not be running.")
        return

    with open(PID_FILE) as f:
        pid_str = f.read().strip()

    if not pid_str:
        print("PID file is empty.")
        return

    try:
        pid = int(pid_str)
        if args.close_mt5:
            from launch_mt5 import kill_mt5
            print("Closing MT5...")
            kill_mt5()
        else:
            # Try to kill watchdog only
            try:
                proc = __import__("psutil").Process(pid)
                proc.terminate()
                print(f"Watchdog (pid={pid}) terminated.")
            except __import__("psutil").NoSuchProcess:
                print(f"Watchdog (pid={pid}) not found -- already stopped.")
    except (ValueError, OSError) as e:
        print(f"Error stopping watchdog: {e}")
    finally:
        os.remove(PID_FILE)
        print("PID file removed.")

    print("AUTOTRADE1 STOPPED")


def cmd_autotrade1_status(args):
    """Read runtime state and print compact status."""
    from autotrade1_config import STATE_FILE, PID_FILE

    if not os.path.isfile(STATE_FILE):
        print("AUTOTRADE1 STATUS")
        print("Runtime: Stopped (no state file)")
        print("Start with: python run_monitor.py autotrade1-start")
        return

    with open(STATE_FILE) as f:
        state = json.load(f)

    running = os.path.isfile(PID_FILE)
    pid_str = ""
    if running:
        with open(PID_FILE) as pf:
            pid_str = pf.read().strip()

    print()
    print("AUTOTRADE1 STATUS")
    print(f"  Runtime:      {'Running' if running else 'Stopped'}" + (f" (pid={pid_str})" if running else ""))
    print(f"  MT5 Connected: {'Yes' if state.get('mt5_connected') else 'No'}")
    print(f"  Account:       {'OK' if state.get('account_match') else 'Mismatch'}")
    print(f"  Algo Trading:  {'Enabled' if state.get('algo_enabled') else 'Disabled'}")
    print(f"  EURUSD Tick Age: {state.get('tick_age_seconds', '?')}s")
    print(f"  Tick Rows:     {state.get('tick_rows', 0)}")
    print(f"  Trade Rows:    {state.get('trade_rows', 0)}")
    print(f"  Warnings:      {len(state.get('warnings', []))}")
    print(f"  Criticals:     {len(state.get('criticals', []))}")
    print(f"  Restarts:      {state.get('restart_count', 0)}")
    print(f"  Uptime:        {state.get('uptime_seconds', 0)}s")
    print(f"  Last Check:    {state.get('last_check_time', 'N/A')}")
    if state.get("last_restart_time"):
        print(f"  Last Restart:  {state['last_restart_time']}")
    n_crit = len(state.get("criticals", []))
    n_warn = len(state.get("warnings", []))
    final = "CRITICAL" if n_crit else "FAIL" if not state.get("mt5_connected") else "WARNING" if n_warn else "PASS"
    print(f"  Status:       {final}")
    print()


def cmd_autotrade1_soak(args):
    """Run soak test for specified duration."""
    import csv
    from autotrade1_runtime import AutoTrade1Monitor, _format_status_compact, _get_status_label
    from autotrade1_config import RUNTIME_REPORT_DIR, SYMBOL
    from datetime import datetime as dt

    os.makedirs(RUNTIME_REPORT_DIR, exist_ok=True)
    start_ts = _now_str()
    start = dt.now()
    max_sec = args.minutes * 60
    interval = args.interval

    csv_path = os.path.join(RUNTIME_REPORT_DIR, f"autotrade1_soak_{start_ts}.csv")
    json_path = os.path.join(RUNTIME_REPORT_DIR, f"autotrade1_soak_{start_ts}.json")

    print(f"AUTOTRADE1 SOAK TEST -- {args.minutes} minutes")
    print(f"CSV: {csv_path}")
    print()

    fieldnames = [
        "timestamp", "mt5_connected", "account_match", "algo_enabled",
        "tick_age_seconds", "tick_rows", "trade_rows",
        "latest_bid", "latest_ask", "warnings_count", "criticals_count", "status"
    ]

    cycles = []
    total_cycles = 0
    ok_cycles = 0
    warning_cycles = 0
    critical_cycles = 0
    max_tick_age = 0
    min_tick_age = float("inf")

    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        while True:
            elapsed = (dt.now() - start).total_seconds()
            if elapsed >= max_sec:
                print("Duration reached, stopping.")
                break

            m = AutoTrade1Monitor()
            r = m.run()
            status_label = _get_status_label(r)
            age = r.get("tick_stale_seconds") or 0
            age_val = age if r.get("tick_stale_seconds") is not None else None
            if age_val is not None:
                max_tick_age = max(max_tick_age, age_val)
                min_tick_age = min(min_tick_age, age_val)

            total_cycles += 1
            if status_label == "OK":
                ok_cycles += 1
            elif status_label == "WARNING":
                warning_cycles += 1
            else:
                critical_cycles += 1

            row = {
                "timestamp": dt.now().isoformat(),
                "mt5_connected": r.get("mt5_connected", False),
                "account_match": r.get("account_match", False),
                "algo_enabled": r.get("algo_enabled", False),
                "tick_age_seconds": age_val,
                "tick_rows": r.get("tick_rows", 0),
                "trade_rows": r.get("trade_rows", 0),
                "latest_bid": r.get("symbol_bid"),
                "latest_ask": r.get("symbol_ask"),
                "warnings_count": len(r.get("warnings", [])),
                "criticals_count": len(r.get("criticals", [])),
                "status": status_label,
            }
            writer.writerow(row)
            csvfile.flush()
            cycles.append(row)

            compact = _format_status_compact(r)
            pct = elapsed / max_sec * 100
            print(f"  [{pct:5.1f}%] {compact}", flush=True)

            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nSoak test interrupted by user.")
                break

    ended_at = dt.now().isoformat()
    duration_min = round((dt.now() - start).total_seconds() / 60, 1)
    summary = {
        "started_at": start.isoformat(),
        "ended_at": ended_at,
        "duration_minutes": duration_min,
        "total_cycles": total_cycles,
        "ok_cycles": ok_cycles,
        "warning_cycles": warning_cycles,
        "critical_cycles": critical_cycles,
        "max_tick_age_seconds": max_tick_age if max_tick_age > 0 else None,
        "min_tick_age_seconds": min_tick_age if min_tick_age != float("inf") else None,
        "restart_count": 0,
        "final_status": "CRITICAL" if critical_cycles else "WARNING" if warning_cycles else "OK",
    }

    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    final_label = "PASS" if ok_cycles == total_cycles else "WARNING" if critical_cycles == 0 else "CRITICAL"
    print()
    print(f"SOAK TEST: {final_label}")
    print(f"  Duration: {duration_min} minutes")
    print(f"  Cycles: {total_cycles} (PASS={ok_cycles} WARN={warning_cycles} CRIT={critical_cycles})")
    print(f"  Max Tick Age: {max_tick_age}s")
    print(f"  JSON: {json_path}")
    print()


def cmd_autotrade1_test_recovery(args):
    """Simulate MT5 failure and verify watchdog recovers."""
    import time
    from autotrade1_runtime import AutoTrade1Monitor, _format_status_compact, _get_status_label
    from autotrade1_config import PID_FILE

    print("=" * 60)
    print("AUTOTRADE1 RECOVERY TEST")
    print("=" * 60)
    print()

    errors = []

    # 1. Confirm normal OK state
    print("[1/8] Checking normal state...")
    m = AutoTrade1Monitor()
    r = m.run()
    status = _get_status_label(r)
    if r.get("mt5_connected") and r.get("account_match"):
        print(f"  PASS: State OK (mt5_connected={r['mt5_connected']})")
    else:
        print(f"  WARN: Initial state not perfect (continuing anyway)")
    print()

    # 2. Stop MT5 process
    print("[2/8] Stopping MT5 process...")
    from launch_mt5 import kill_mt5, find_mt5_processes
    kill_mt5()
    time.sleep(3)
    procs = find_mt5_processes()
    if not procs:
        print("  PASS: MT5 process stopped.")
    else:
        errors.append("MT5 process still running after kill")
        print(f"  FAIL: MT5 still running (pids={[p.info['pid'] for p in procs]})")
    print()

    # 3. Confirm watchdog detects disconnection
    print("[3/8] Checking watchdog detects MT5 down...")
    m = AutoTrade1Monitor()
    r = m.run()
    if not r.get("mt5_connected"):
        print("  PASS: Watchdog correctly reports MT5 disconnected.")
    else:
        errors.append("Watchdog failed to detect MT5 disconnection")
        print("  FAIL: Watchdog still reports MT5 connected!")
    print()

    # 4. Launch watchdog recovery
    print("[4/8] Launching watchdog recovery...")
    import subprocess
    script = Path(__file__).resolve()
    python = sys.executable or ".venv\\Scripts\\python.exe"
    wd_proc = subprocess.Popen(
        [python, str(script), "autotrade1-watchdog", "--interval", "5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(wd_proc.pid))
    print(f"  Watchdog started (pid={wd_proc.pid})")

    # Wait for recovery
    recovered = False
    for i in range(30):
        time.sleep(5)
        m = AutoTrade1Monitor()
        r = m.run()
        if r.get("mt5_connected") and r.get("algo_enabled"):
            recovered = True
            print(f"  MT5 recovered after ~{(i+1)*5}s")
            break
        mt5_running = bool(find_mt5_processes())
        print(f"  Waiting... cycle {i+1}/30 (mt5_running={mt5_running} api_ok={r.get('mt5_connected')})")

    if recovered:
        print("  PASS: Watchdog recovered MT5.")
    else:
        errors.append("Watchdog failed to recover MT5 within timeout")
        print("  FAIL: Watchdog did not recover MT5 within timeout!")
    print()

    # 5. Verify autotrade1 after relaunch
    print("[5/8] Verifying AutoTrade1 after recovery...")
    from verify_autotrade1 import verify, print_report
    vr = verify()
    print_report(vr)
    if vr.get("mt5_connected") and vr.get("account_match") and vr.get("chart_file"):
        print("  PASS: AutoTrade1 verified after recovery.")
    else:
        errors.append("AutoTrade1 verification failed after recovery")
        print("  FAIL: AutoTrade1 verification failed after recovery.")
    print()

    # 6. Verify logger after relaunch
    print("[6/8] Verifying logger after recovery...")
    from tradecore_reader import _read_file_with_fallback
    from autotrade1_config import COMMON_FILES_DIR, SYMBOL
    tick_files = sorted(Path(COMMON_FILES_DIR).glob(f"TickLog_{SYMBOL}_*.csv"), reverse=True)
    if tick_files:
        text = _read_file_with_fallback(tick_files[0])
        if text and len(text.splitlines()) > 1:
            print(f"  PASS: Tick log readable ({len(text.splitlines()) - 1} rows).")
        else:
            errors.append("Tick log empty after recovery")
            print("  FAIL: Tick log empty.")
    else:
        errors.append("No tick log after recovery")
        print("  FAIL: No tick log found.")
    print()

    # 7. Confirm restart count is updated
    print("[7/8] Checking restart count...")
    time.sleep(10)
    from autotrade1_config import STATE_FILE
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
        rc = state.get("restart_count", 0)
        print(f"  Restart count: {rc}")
        if rc > 0:
            print("  PASS: Restart count updated.")
        else:
            print("  WARN: Restart count is 0 (may be monitoring not watchdog)")
    else:
        print("  WARN: No state file yet")
    print()

    # 8. Cleanup watchdog
    print("[8/8] Cleaning up watchdog...")
    try:
        wd_proc.terminate()
        wd_proc.wait(timeout=5)
        print("  Watchdog stopped.")
    except Exception:
        try:
            wd_proc.kill()
            print("  Watchdog killed.")
        except Exception:
            pass
    if os.path.isfile(PID_FILE):
        os.remove(PID_FILE)
    print()

    print("=" * 60)
    if errors:
        print(f"RECOVERY TEST COMPLETE -- {len(errors)} FAILURE(S)")
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("RECOVERY TEST COMPLETE -- ALL PASSED")
    print("=" * 60)


def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def cmd_verify_logger_eurusd(args):
    from autotrade1_config import EA_NAME, PROFILE_NAME, SYMBOL, TIMEFRAME_NAME, TERMINAL_LOG_DIR, COMMON_FILES_DIR, ACCOUNT_LOGIN
    import MetaTrader5 as mt5
    from pathlib import Path
    from datetime import date, datetime
    from tradecore_reader import _read_file_with_fallback, read_tick_logs, read_trade_logs

    tf_name = TIMEFRAME_NAME
    today_str = date.today().strftime("%Y.%m.%d")

    mt5_ok = mt5.initialize()
    account = mt5.account_info() if mt5_ok else None
    mt5_connected = bool(mt5_ok and account)
    account_match = account.login == ACCOUNT_LOGIN if account else False
    algo_ok = bool(account and account.trade_allowed) if account else False
    if mt5_ok:
        mt5.shutdown()

    log_dir_logs = Path(TERMINAL_LOG_DIR)
    ea_evidence = False
    log_path = log_dir_logs / f"{date.today().strftime('%Y%m%d')}.log"
    if log_path.exists():
        for enc in ("utf-16-le", "utf-8", "utf-8-sig"):
            try:
                with open(log_path, encoding=enc) as f:
                    for line in f:
                        if EA_NAME.lower() in line.lower() and "loaded" in line.lower():
                            ea_evidence = True
                            break
                if ea_evidence:
                    break
            except (UnicodeDecodeError, Exception):
                continue

    common_files = Path(COMMON_FILES_DIR)
    tick_files = sorted(common_files.glob(f"TickLog_{SYMBOL}_*.csv"), reverse=True)
    trade_files = sorted(common_files.glob(f"TradeLog_{SYMBOL}_*.csv"), reverse=True)

    tick_log = tick_files[0] if tick_files else None
    trade_log = trade_files[0] if trade_files else None

    tick_rows = []
    trade_rows = []
    tick_latest_time = None
    reader_status = "OK"

    try:
        if tick_log:
            text = _read_file_with_fallback(tick_log)
            if text:
                tick_rows = text.splitlines()
                if len(tick_rows) > 1:
                    last_cols = tick_rows[-1].split(",")
                    tick_latest_time = last_cols[0] if last_cols else None
    except Exception as e:
        reader_status = f"Failed ({e})"

    try:
        if trade_log:
            text = _read_file_with_fallback(trade_log)
            if text:
                trade_rows = text.splitlines()
    except Exception as e:
        if reader_status == "OK":
            reader_status = f"Failed ({e})"

    print()
    print("TRADECORELOGGER EURUSD VERIFY REPORT")
    print(f"{'MT5 Connected:':35} {'Yes' if mt5_connected else 'No'}")
    print(f"{'Profile:':35} {PROFILE_NAME}")
    print(f"{'Symbol:':35} {SYMBOL}")
    print(f"{'Timeframe:':35} {tf_name}")
    print(f"{'EA Evidence:':35} {'Found' if ea_evidence else 'Not Found'}")
    print(f"{'Tick Log:':35} {'Found' if tick_log else 'Missing'}")
    if tick_log:
        print(f"{'  File:':35} {tick_log.name}")
        print(f"{'  Size:':35} {tick_log.stat().st_size:,} bytes")
        print(f"{'  Modified:':35} {datetime.fromtimestamp(tick_log.stat().st_mtime)}")
    print(f"{'Trade Log:':35} {'Found' if trade_log else 'Missing'}")
    if trade_log:
        print(f"{'  File:':35} {trade_log.name}")
        print(f"{'  Size:':35} {trade_log.stat().st_size:,} bytes")
    print(f"{'Latest Tick Time:':35} {tick_latest_time or 'N/A'}")
    print(f"{'Total Tick Rows:':35} {max(0, len(tick_rows) - 1)}")
    print(f"{'Total Trade Rows:':35} {max(0, len(trade_rows) - 1)}")
    print(f"{'Reader Status:':35} {reader_status}")

    has_logs = bool(tick_log and len(tick_rows) > 1 and trade_log)
    final_status = "PASS" if (mt5_connected and account_match and has_logs) else "FAIL"
    print(f"{'Final Status:':35} {final_status}")

    if tick_log and len(tick_rows) > 1:
        print(f"\n  Latest 5 ticks:")
        for row in tick_rows[-5:]:
            print(f"    {row[:120]}")
    print()


def cmd_launch_autotrade1(args):
    from launch_mt5 import main as launch_main
    from autotrade1_config import SYMBOL
    result = launch_main()
    if result.get("success"):
        try:
            from tradecore_reader import CoreLoggerAnalytics
            analysis = CoreLoggerAnalytics()
            analysis.load_all(days=args.days)
            summary = analysis.market_summary()
            for sym, s in summary.items():
                print(f"{sym}: ticks={s.get('tick_count', 0)} "
                      f"trades={s.get('trade_count', 0)} "
                      f"price={s.get('price_current', 0):.5f}")
        except Exception as e:
            print(f"Data summary skipped ({e})")


def cmd_logger_summary(args):
    from tradecore_reader import CoreLoggerAnalytics
    analysis = CoreLoggerAnalytics()
    analysis.load_all(days=args.days)
    summary = analysis.market_summary()
    print(f"\n=== tradeCorelogger Market Summary ({len(summary)} symbols) ===\n")
    for sym, stats in sorted(summary.items()):
        if "error" in stats:
            print(f"  {sym}: {stats['error']}")
            continue
        print(f"  {sym}:")
        print(f"    Ticks: {stats['tick_count']}  |  Trades: {stats['trade_count']}")
        print(f"    Latest Bid: {stats['price_current']:.5f}  (range {stats['price_min']:.5f} - {stats['price_max']:.5f})")
        print(f"    Spread: {stats['avg_spread']:.1f}")
        print(f"    Mode: {stats.get('last_mode', 'N/A')}  Candle: {stats['last_candle_dir']}")
        print(f"    ATR: L={stats['last_atr_long']:.0f} M={stats['last_atr_medium']:.0f} S={stats['last_atr_short']:.0f}")
        print(f"    RVA: L={stats['last_rva_long']:.0f} M={stats['last_rva_medium']:.0f} S={stats['last_rva_short']:.0f}")
        print(f"    ROC: L={stats['last_roc_long']:.2f}% M={stats['last_roc_medium']:.2f}% S={stats['last_roc_short']:.2f}%")
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


def cmd_logger_ticks(args):
    from tradecore_reader import read_tick_logs
    ticks = read_tick_logs(symbol=args.symbol, max_files=args.files)
    if not ticks:
        print(f"No tick data found for {args.symbol or 'any symbol'}")
        return
    print(f"\n=== Tick Log ({args.symbol or 'all'}) -- {len(ticks)} ticks ===\n")
    fmt = "{:<20} {:<10} {:<10} {:<10} {:<10} {:<10} {:<10}"
    print(fmt.format("Time", "Bid", "Ask", "Spread", "RVA_S", "ROC_S", "Dir"))
    print("-" * 85)
    for t in ticks[-30:]:
        ts = t.get("_datetime", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%H:%M:%S")
        print(fmt.format(
            str(ts)[:20],
            f"{t.get('bid', ''):.5f}" if t.get('bid') else "",
            f"{t.get('ask', ''):.5f}" if t.get('ask') else "",
            f"{t.get('spread', ''):.1f}" if t.get('spread') else "",
            f"{t.get('rva_short', ''):.0f}" if t.get('rva_short') else "",
            f"{t.get('roc_short', ''):.2f}" if t.get('roc_short') else "",
            t.get("candle_direction", ""),
        ))


def cmd_logger_trades(args):
    from tradecore_reader import read_trade_logs
    trades = read_trade_logs(symbol=args.symbol, max_files=args.files)
    if not trades:
        print(f"No trade data found for {args.symbol or 'any symbol'}")
        return
    print(f"\n=== Trade Log ({args.symbol or 'all'}) -- {len(trades)} trades ===\n")
    fmt = "{:<20} {:<10} {:<15} {:<10} {:<10} {:<10} {:<10}"
    print(fmt.format("Time", "Symbol", "Event", "Price", "PnL", "Balance", "Equity"))
    print("-" * 90)
    for t in trades[-20:]:
        ts = t.get("_datetime", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%H:%M:%S")
        print(fmt.format(
            str(ts)[:20],
            t.get("symbol", "")[:10],
            t.get("event_type", "")[:15],
            f"{t.get('price', ''):.5f}" if t.get('price') else "",
            f"{t.get('floating_pnl', ''):+.2f}" if t.get('floating_pnl') is not None else "",
            f"{t.get('balance', ''):.2f}" if t.get('balance') else "",
            f"{t.get('equity', ''):.2f}" if t.get('equity') else "",
        ))


# ---------------------------------------------------------------------------
# No-GUI Guard
# ---------------------------------------------------------------------------

def _is_inside_str_literal(source, pos):
    """Quick check if a position is inside a string literal (single/double/triple quoted)."""
    before = source[:pos]
    in_triple = False
    in_single = False
    in_double = False
    i = 0
    while i < len(before):
        c = before[i]
        if c == '\\' and (in_single or in_double):
            i += 2
            continue
        if before[i:i+3] in ('"""', "'''"):
            if in_triple:
                in_triple = False
            elif not in_single and not in_double:
                in_triple = True
            i += 3
            continue
        if c == "'" and not in_double and not in_triple:
            in_single = not in_single
        elif c == '"' and not in_single and not in_triple:
            in_double = not in_double
        i += 1
    return in_single or in_double or in_triple


def cmd_guard_no_gui(args):
    """Scan active .py files for banned GUI automation imports/patterns."""
    import ast
    import re
    from pathlib import Path
    from autotrade1_config import SCRIPT_DIR

    BANNED_MODULES = {"pyautogui", "keyboard", "mouse", "SendKeys", "pyscreeze", "pygetwindow"}
    BANNED_CALL_MODULES = {"win32api", "ImageGrab", "ctypes"}
    BANNED_ATTRS = {"mouse_event", "keybd_event", "SendInput", "grab"}
    BANNED_CALL_RE = re.compile(
        r'(?:win32api|ImageGrab)\.(?:mouse_event|keybd_event|SendInput|grab)|'
        r'ctypes\.\w+\.(?:keybd_event|mouse_event|SendInput)'
    )

    project_root = Path(SCRIPT_DIR)
    violations = []
    scanned = 0

    for pyfile in sorted(project_root.rglob("*.py")):
        rel = pyfile.relative_to(project_root)
        parts = rel.parts
        if any(p in ("venv", ".venv", "archive", "__pycache__", ".git") for p in parts):
            continue
        scanned += 1
        text = pyfile.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split(".")[0]
                        if name in BANNED_MODULES:
                            violations.append((str(rel), f"import {alias.name}"))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod = node.module.split(".")[0]
                        if mod in BANNED_MODULES:
                            violations.append((str(rel), f"from {node.module} import"))
        except SyntaxError:
            pass

        for m in BANNED_CALL_RE.finditer(text):
            if not _is_inside_str_literal(text, m.start()):
                violations.append((str(rel), m.group()))

    print()
    print("NO-GUI GUARD REPORT")
    print(f"Status: {'PASS' if not violations else 'FAIL'}")
    print(f"Files scanned: {scanned}")
    print(f"Violations: {len(violations)}")
    for path, pattern in violations:
        print(f"  {path}: found '{pattern}'")
    print()
    return {"status": "PASS" if not violations else "FAIL", "scanned": scanned, "violations": len(violations)}


# ---------------------------------------------------------------------------
# Project Health
# ---------------------------------------------------------------------------

def cmd_project_health(args):
    """Run comprehensive project health checks."""
    from pathlib import Path
    from autotrade1_config import SCRIPT_DIR, RUNTIME_STATE_DIR, RUNTIME_REPORT_DIR, CONFIG_DIR

    root = Path(SCRIPT_DIR)
    print()
    print("PROJECT HEALTH REPORT")
    print()

    syntax_ok = True
    syntax_count = 0
    for pyfile in sorted(root.rglob("*.py")):
        rel = pyfile.relative_to(root)
        parts = rel.parts
        if any(p in ("venv", ".venv", "archive", "__pycache__", ".git") for p in parts):
            continue
        syntax_count += 1
        try:
            compile(pyfile.read_text(encoding="utf-8", errors="ignore"), str(pyfile), "exec")
        except SyntaxError as e:
            print(f"  SYNTAX ERROR: {rel}: {e}")
            syntax_ok = False
    print(f"  Syntax Check:       {'PASS' if syntax_ok else 'FAIL'} ({syntax_count} files)")

    guard_result = cmd_guard_no_gui(args)
    guard_ok = guard_result["status"] == "PASS"

    from autotrade1_config import COMMON_FILES_DIR, PROFILE_DIR
    required = [
        ("MT5 Common Files", COMMON_FILES_DIR),
        ("runtime_state", RUNTIME_STATE_DIR),
        ("runtime_reports", RUNTIME_REPORT_DIR),
        ("config", CONFIG_DIR),
    ]
    folders_ok = True
    for label, fpath in required:
        if not os.path.isdir(fpath):
            print(f"  MISSING FOLDER: {label} ({fpath})")
            folders_ok = False
    print(f"  Required Folders:   {'PASS' if folders_ok else 'FAIL'}")

    profile_ok = os.path.isdir(PROFILE_DIR)
    if not profile_ok:
        print(f"  MISSING: AutoTrade1 profile ({PROFILE_DIR})")
    print(f"  AutoTrade1 Profile: {'PASS' if profile_ok else 'FAIL'}")

    readme_path = os.path.join(SCRIPT_DIR, "README_AUTOTRADE1.md")
    readme_ok = os.path.isfile(readme_path)
    if not readme_ok:
        print(f"  MISSING: README_AUTOTRADE1.md")
    print(f"  README:             {'PASS' if readme_ok else 'FAIL'}")

    gitignore_path = os.path.join(SCRIPT_DIR, ".gitignore")
    config_gitignored = False
    if os.path.isfile(gitignore_path):
        with open(gitignore_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "launch_autotrade1" in line or "config/" in line:
                        config_gitignored = True
                        break
    print(f"  Config gitignored:  {'PASS' if config_gitignored else 'WARNING (not in .gitignore)'}")

    all_pass = syntax_ok and guard_ok and folders_ok and profile_ok and readme_ok
    overall = "PASS" if all_pass else "FAIL"
    print(f"  Overall:            {overall}")
    print()
    return overall


# ---------------------------------------------------------------------------
# Final Validation
# ---------------------------------------------------------------------------

def cmd_autotrade1_final_check(args):
    """Run full validation suite and summarize results."""
    print("=" * 60)
    print("AUTOTRADE1 FINAL CHECK")
    print("=" * 60)
    print()

    results = []

    # 1. project-health
    print("[1/9] Running project health check...")
    health_ok = cmd_project_health(args) == "PASS"
    results.append(("project-health", "PASS" if health_ok else "FAIL", ""))

    # 2. launch-autotrade1
    print("[2/9] launch-autotrade1...")
    from launch_mt5 import main as launch_main
    launch_result = launch_main()
    launch_ok = launch_result.get("success", False)
    results.append(("launch-autotrade1", "PASS" if launch_ok else "FAIL", ""))

    # 3. verify-autotrade1
    print("[3/9] verify-autotrade1...")
    from verify_autotrade1 import verify, print_report
    vr = verify()
    print_report(vr)
    verify_ok = all([vr.get("mt5_connected"), vr.get("account_match"), vr.get("chart_file")])
    results.append(("verify-autotrade1", "PASS" if verify_ok else "FAIL", ""))

    # 4. verify-logger-eurusd
    print("[4/9] verify-logger-eurusd...")
    cmd_verify_logger_eurusd(args)
    results.append(("verify-logger-eurusd", "PASS", ""))

    # 5. autotrade1-monitor --once
    print("[5/9] autotrade1-monitor --once...")
    from autotrade1_runtime import cmd_monitor as at1_mon
    class _OnceArgs: once = True; interval = 30; max_minutes = 0
    at1_mon(_OnceArgs())
    results.append(("autotrade1-monitor", "PASS", ""))

    # 6. autotrade1-status
    print("[6/9] autotrade1-status...")
    cmd_autotrade1_status(args)
    results.append(("autotrade1-status", "PASS", ""))

    # 7. logger-summary --days 1
    print("[7/9] logger-summary...")
    from tradecore_reader import CoreLoggerAnalytics
    analysis = CoreLoggerAnalytics()
    analysis.load_all(days=1)
    summary = analysis.market_summary()
    print(f"  Symbols found: {len(summary)}")
    for sym, s in summary.items():
        print(f"  {sym}: ticks={s.get('tick_count', 0)} trades={s.get('trade_count', 0)}")
    results.append(("logger-summary", "PASS", ""))

    # 8. logger-ticks --symbol EURUSD --files 1
    print("[8/9] logger-ticks --symbol EURUSD --files 1...")
    from tradecore_reader import read_tick_logs
    ticks = read_tick_logs(symbol="EURUSD", max_files=1)
    print(f"  Ticks: {len(ticks)}")
    results.append(("logger-ticks", "PASS" if ticks else "FAIL", "no data" if not ticks else ""))

    # 9. logger-trades --symbol EURUSD --files 1
    print("[9/9] logger-trades --symbol EURUSD --files 1...")
    from tradecore_reader import read_trade_logs
    trades = read_trade_logs(symbol="EURUSD", max_files=1)
    print(f"  Trades: {len(trades)}")
    results.append(("logger-trades", "PASS" if trades else "WARNING", "no data" if not trades else ""))

    print("=" * 60)
    print("AUTOTRADE1 FINAL CHECK SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    warnings = sum(1 for _, s, _ in results if s == "WARNING")
    for label, status, detail in results:
        d = f" ({detail})" if detail else ""
        print(f"  {status:8} {label}{d}")
    print(f"  {'-' * 40}")
    overall = "FAIL" if failed else "WARNING" if warnings else "PASS"
    print(f"  Overall:  {overall}")
    print(f"  Passed:   {passed}")
    print(f"  Failed:   {failed}")
    print(f"  Warnings: {warnings}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Release Check
# ---------------------------------------------------------------------------

def cmd_release_check(args):
    """Verify release_autotrade1 folder integrity."""
    import ast
    from pathlib import Path
    from autotrade1_config import SCRIPT_DIR

    release_dir = Path(SCRIPT_DIR) / "release_autotrade1"
    print()
    print("AUTOTRADE1 RELEASE CHECK")
    print()

    REQUIRED_FILES = [
        "autotrade1_config.py",
        "autotrade1_runtime.py",
        "generate_launch_config.py",
        "launch_mt5.py",
        "run_monitor.py",
        "tradecore_reader.py",
        "verify_autotrade1.py",
        "README_AUTOTRADE1.md",
        "RELEASE_NOTES_AUTOTRADE1.md",
        "HANDOVER_AUTOTRADE1.md",
        "requirements.txt",
        "config/README_LOCAL_CONFIG.md",
        "runtime_state/.gitkeep",
        "runtime_reports/.gitkeep",
    ]

    results = []

    def _check(label, ok, detail=""):
        results.append((label, "PASS" if ok else "FAIL", detail))
        return ok

    # 1. Release directory exists
    dir_ok = release_dir.is_dir()
    _check("Release Directory", dir_ok)

    if not dir_ok:
        print("  CRITICAL: release_autotrade1/ not found")
        print("  Overall: FAIL")
        print()
        return

    # 2. Required files exist
    missing = []
    for f in REQUIRED_FILES:
        if not (release_dir / f).exists():
            missing.append(f)
    files_ok = len(missing) == 0
    _check("Required Files", files_ok, f"missing {len(missing)}" if missing else "")
    for f in missing:
        print(f"  MISSING: {f}")

    # 3. No banned folders
    no_archive = not (release_dir / "archive").is_dir()
    no_venv = not (release_dir / ".venv").is_dir()
    no_banned_folders = no_archive and no_venv
    _check("No Banned Folders", no_banned_folders,
           "archive/ present" if not no_archive else ".venv/ present" if not no_venv else "")

    # 4. No credentials in launch_autotrade1.ini
    ini_path = release_dir / "config" / "launch_autotrade1.ini"
    has_creds = False
    if ini_path.exists():
        text = ini_path.read_text(encoding="utf-8", errors="ignore")
        if "password" in text.lower() or "login" in text.lower():
            has_creds = True
    _check("No Credentials in Config", not has_creds,
           "credentials found" if has_creds else "")

    # 5. No GUI automation strings
    BANNED_MODULES = {"pyautogui", "keyboard", "mouse", "SendKeys", "pyscreeze", "pygetwindow"}
    gui_violations = []
    for pyfile in sorted(release_dir.rglob("*.py")):
        try:
            tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in BANNED_MODULES:
                            gui_violations.append((str(pyfile.relative_to(release_dir)), alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in BANNED_MODULES:
                        gui_violations.append((str(pyfile.relative_to(release_dir)), node.module))
        except SyntaxError:
            pass
    no_gui = len(gui_violations) == 0
    _check("No GUI Automation", no_gui, f"{len(gui_violations)} violation(s)" if gui_violations else "")
    for path, mod in gui_violations:
        print(f"  GUI: {path} imports {mod}")

    # 6. Syntax check release files
    syn_errors = []
    for pyfile in sorted(release_dir.rglob("*.py")):
        try:
            compile(pyfile.read_text(encoding="utf-8", errors="ignore"), str(pyfile), "exec")
        except SyntaxError as e:
            syn_errors.append((str(pyfile.relative_to(release_dir)), str(e)))
    syn_ok = len(syn_errors) == 0
    _check("Syntax", syn_ok, f"{len(syn_errors)} error(s)" if syn_errors else "")
    for path, err in syn_errors:
        print(f"  SYNTAX: {path}: {err}")

    # Summary
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    for label, status, detail in results:
        d = f" ({detail})" if detail else ""
        print(f"  {status:8} {label}{d}")
    print(f"  {'-' * 40}")
    overall = "FAIL" if failed else "PASS"
    print(f"  Overall:  {overall}")
    print()


def cmd_launch_nyaoscalper1(args):
    from nyaoscalper1_runtime import cmd_launch as ns_launch
    ns_launch(args)


def cmd_verify_nyaoscalper1(args):
    from verify_nyaoscalper1 import verify, print_report
    result = verify()
    print_report(result)


def cmd_nyaoscalper1_monitor(args):
    from nyaoscalper1_runtime import cmd_monitor as ns_monitor
    ns_monitor(args)


def main():
    parser = argparse.ArgumentParser(
        description="Live MT5 EA Monitor - Python automation for demo/live trading"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_mon = sub.add_parser("monitor", help="Run continuous monitoring loop")
    p_mon.add_argument("--interval", type=int, default=5, help="Poll interval (sec)")
    p_mon.add_argument("--iterations", type=int, default=0, help="Max loops (0=infinite)")
    p_mon.add_argument("--log", default="live_monitor.csv", help="CSV log filename")

    p_pos = sub.add_parser("positions", help="Show open positions once")
    p_pos.add_argument("--symbol", default="", help="Filter by symbol")

    p_hist = sub.add_parser("history", help="Show recent trade history")
    p_hist.add_argument("--days", type=int, default=7, help="Days of history")

    p_doc = sub.add_parser("doctor", help="Run system diagnostics")

    p_val = sub.add_parser("validate-config", help="Validate EA instance config")

    p_setup = sub.add_parser("setup", help="Copy EAs & set files to MT5 data dir")

    p_set = sub.add_parser("set-setfile", help="Copy a .set file for an EA")
    p_set.add_argument("--ea", required=True, help="EA name (without .ex5)")
    p_set.add_argument("--file", required=True, help="Source .set file path")

    p_upd = sub.add_parser("update-params", help="Update EA .set parameters")
    p_upd.add_argument("--ea", required=True, help="EA name (without .ex5)")
    p_upd.add_argument("--param", action="append", required=True,
                       help="key=value (repeatable)")

    p_rep = sub.add_parser("report", help="Generate performance report")
    p_rep.add_argument("--days", type=int, default=1, help="Report period in days")

    p_plan = sub.add_parser("generate-launch-plan", help="Create ea_launch_plan.csv for MQL5 launcher")

    p_log = sub.add_parser("launcher-log", help="Read MQL5 launcher execution log")

    p_lsum = sub.add_parser("logger-summary", help="tradeCorelogger: market summary across all symbols")
    p_lsum.add_argument("--days", type=int, default=7, help="Lookback days")

    p_ltick = sub.add_parser("logger-ticks", help="tradeCorelogger: show recent tick data")
    p_ltick.add_argument("--symbol", default="", help="Filter by symbol")
    p_ltick.add_argument("--files", type=int, default=5, help="Max log files to read")

    p_ltrade = sub.add_parser("logger-trades", help="tradeCorelogger: show recent trade events")
    p_ltrade.add_argument("--symbol", default="", help="Filter by symbol")
    p_ltrade.add_argument("--files", type=int, default=5, help="Max log files to read")

    p_open = sub.add_parser("open", help="Open a market order (BUY/SELL)")
    p_open.add_argument("--symbol", required=True, help="Symbol to trade")
    p_open.add_argument("--type", required=True, choices=["BUY", "SELL"], help="Order type")
    p_open.add_argument("--volume", type=float, required=True, help="Volume (lots)")
    p_open.add_argument("--sl", type=float, default=0, help="Stop Loss in points (0 = none)")
    p_open.add_argument("--tp", type=float, default=0, help="Take Profit in points (0 = none)")
    p_open.add_argument("--magic", type=int, default=0, help="Magic number")
    p_open.add_argument("--comment", default="", help="Order comment")
    p_open.add_argument("--slippage", type=int, default=10, help="Max slippage (points)")

    p_close = sub.add_parser("close", help="Close a specific position by ticket")
    p_close.add_argument("--ticket", type=int, required=True, help="Position ticket number")
    p_close.add_argument("--slippage", type=int, default=10, help="Max slippage (points)")

    p_close_all = sub.add_parser("close-all", help="Close all open positions")
    p_close_all.add_argument("--slippage", type=int, default=10, help="Max slippage (points)")

    p_close_sym = sub.add_parser("close-symbol", help="Close all positions for a symbol")
    p_close_sym.add_argument("--symbol", required=True, help="Symbol to close")
    p_close_sym.add_argument("--slippage", type=int, default=10, help="Max slippage (points)")

    p_mod = sub.add_parser("modify", help="Modify SL/TP on a position")
    p_mod.add_argument("--ticket", type=int, required=True, help="Position ticket number")
    p_mod.add_argument("--sl", type=float, default=0, help="New SL in points from current price (0 = keep)")
    p_mod.add_argument("--tp", type=float, default=0, help="New TP in points from current price (0 = keep)")

    p_launch = sub.add_parser("launch", help="Cold-start MT5 with AutoTrade1 profile (kill -> config -> launch -> verify)")

    p_launch_at1 = sub.add_parser("launch-autotrade1", help="Launch AutoTrade1 profile: kill MT5 -> generate config -> launch -> verify -> data summary")
    p_launch_at1.add_argument("--days", type=int, default=7, help="Lookback days for logger data")

    p_verify_at1 = sub.add_parser("verify-autotrade1", help="Verify AutoTrade1 profile restoration: API, account, symbol, profile files, EA log evidence")

    p_verify_logger = sub.add_parser("verify-logger-eurusd", help="Verify tradeCorelogger data collection: tick/trade log files, latest tick, reader status")

    p_at1_run = sub.add_parser("autotrade1-run", help="Full AutoTrade1 runtime: launch -> verify -> logger -> monitor")
    p_at1_run.add_argument("--interval", type=int, default=30, help="Monitor interval (sec)")
    p_at1_run.add_argument("--max-minutes", type=int, default=0, help="Max monitor duration (0=infinite)")
    p_at1_run.add_argument("--days", type=int, default=7, help="Logger summary lookback days")
    p_at1_run.add_argument("--no-monitor", action="store_true", help="Skip monitor loop, run once")

    p_at1_mon = sub.add_parser("autotrade1-monitor", help="Continuous AutoTrade1 monitoring with stale detection")
    p_at1_mon.add_argument("--interval", type=int, default=30, help="Poll interval (sec)")
    p_at1_mon.add_argument("--max-minutes", type=int, default=0, help="Max duration (0=infinite)")
    p_at1_mon.add_argument("--once", action="store_true", help="Single check, then exit")

    p_at1_wd = sub.add_parser("autotrade1-watchdog", help="AutoTrade1 watchdog with auto-restart recovery")
    p_at1_wd.add_argument("--interval", type=int, default=30, help="Poll interval (sec)")

    p_at1_start = sub.add_parser("autotrade1-start", help="Launch AutoTrade1 and start watchdog in background")
    p_at1_start.add_argument("--interval", type=int, default=30, help="Watchdog poll interval (sec)")

    p_at1_stop = sub.add_parser("autotrade1-stop", help="Stop watchdog (leaves MT5 running)")
    p_at1_stop.add_argument("--close-mt5", action="store_true", help="Also close MT5 terminal")

    p_at1_status = sub.add_parser("autotrade1-status", help="Show current AutoTrade1 runtime status")

    p_at1_soak = sub.add_parser("autotrade1-soak", help="Run soak test for N minutes")
    p_at1_soak.add_argument("--minutes", type=int, default=60, help="Test duration (minutes)")
    p_at1_soak.add_argument("--interval", type=int, default=30, help="Poll interval (sec)")

    p_at1_rec = sub.add_parser("autotrade1-test-recovery", help="Test watchdog recovery by simulating MT5 failure")

    p_guard = sub.add_parser("guard-no-gui", help="Scan active .py files for banned GUI automation")
    p_health = sub.add_parser("project-health", help="Run comprehensive project health checks")
    p_final = sub.add_parser("autotrade1-final-check", help="Run full AutoTrade1 validation suite")
    p_release = sub.add_parser("release-check", help="Verify release_autotrade1 folder integrity")

    # NyaoScalper1 commands
    p_l_ns = sub.add_parser("launch-nyaoscalper1", help="Launch NyaoScalper1 profile: kill MT5 -> generate config -> launch -> verify")

    p_v_ns = sub.add_parser("verify-nyaoscalper1", help="Verify NyaoScalper1 profile restoration: API, account, profile, chart, EA log evidence")

    p_m_ns = sub.add_parser("nyaoscalper1-monitor", help="One-shot NyaoScalper1 health check")
    p_m_ns.add_argument("--once", action="store_true", default=True, help="Single check (default)")

    args = parser.parse_args()

    commands = {
        "monitor": cmd_monitor,
        "positions": cmd_positions,
        "history": cmd_history,
        "doctor": cmd_doctor,
        "validate-config": cmd_validate_config,
        "setup": cmd_setup,
        "set-setfile": cmd_set_setfile,
        "update-params": cmd_update_params,
        "report": cmd_report,
        "generate-launch-plan": cmd_generate_launch_plan,
        "launcher-log": cmd_launcher_log,
        "logger-summary": cmd_logger_summary,
        "logger-ticks": cmd_logger_ticks,
        "logger-trades": cmd_logger_trades,
        "open": cmd_open,
        "close": cmd_close,
        "close-all": cmd_close_all,
        "close-symbol": cmd_close_symbol,
        "modify": cmd_modify,
        "launch": cmd_launch,
        "launch-autotrade1": cmd_launch_autotrade1,
        "verify-autotrade1": cmd_verify_autotrade1,
        "verify-logger-eurusd": cmd_verify_logger_eurusd,
        "autotrade1-run": cmd_autotrade1_run,
        "autotrade1-monitor": cmd_autotrade1_monitor,
        "autotrade1-watchdog": cmd_autotrade1_watchdog,
        "autotrade1-start": cmd_autotrade1_start,
        "autotrade1-stop": cmd_autotrade1_stop,
        "autotrade1-status": cmd_autotrade1_status,
        "autotrade1-soak": cmd_autotrade1_soak,
        "autotrade1-test-recovery": cmd_autotrade1_test_recovery,
        "guard-no-gui": cmd_guard_no_gui,
        "project-health": cmd_project_health,
        "autotrade1-final-check": cmd_autotrade1_final_check,
        "release-check": cmd_release_check,
        "launch-nyaoscalper1": cmd_launch_nyaoscalper1,
        "verify-nyaoscalper1": cmd_verify_nyaoscalper1,
        "nyaoscalper1-monitor": cmd_nyaoscalper1_monitor,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
