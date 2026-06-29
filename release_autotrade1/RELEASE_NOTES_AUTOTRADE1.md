# AutoTrade1 Runtime v1.0 — Release Notes

## Target

- **Symbol:** EURUSD
- **Timeframe:** M5
- **EA:** tradeCorelogger_v2.2
- **Account:** 5051817950 @ MetaQuotes-Demo
- **Profile:** AutoTrade1 (saved profile with EURUSD M5 chart + EA attached)

## What Works

| Area | Status |
|------|--------|
| Cold launch (kill -> config -> launch -> verify) | PASS |
| Profile-based deployment (no GUI automation) | PASS |
| tradeCorelogger_v2.2 EA loading and logging | PASS |
| Tick log reading and parsing | PASS |
| Trade log reading and parsing | PASS |
| Continuous monitoring with stale tick detection | PASS |
| Watchdog with smart restart logic | PASS |
| Runtime state tracking (autotrade1_state.json) | PASS |
| Background watchdog start/stop | PASS |
| Soak test (CSV + JSON reports) | PASS |
| Recovery test (simulate MT5 crash -> watchdog recovers) | PASS |
| No-GUI guard (scans for banned automation) | PASS |
| Project health check (syntax, folders, README) | PASS |
| Final validation suite | PASS |

## Commands

```
python run_monitor.py autotrade1-start              # Launch + start watchdog
python run_monitor.py autotrade1-stop                # Stop watchdog
python run_monitor.py autotrade1-stop --close-mt5    # Stop watchdog + close MT5
python run_monitor.py autotrade1-status              # Show runtime state
python run_monitor.py launch-autotrade1              # Cold launch (manual)
python run_monitor.py verify-autotrade1              # Verify deployment
python run_monitor.py verify-logger-eurusd           # Verify logger files
python run_monitor.py autotrade1-monitor --once      # Single health check
python run_monitor.py autotrade1-monitor             # Continuous monitoring
python run_monitor.py autotrade1-watchdog            # Monitor + auto-restart
python run_monitor.py autotrade1-soak --minutes 60   # Soak test
python run_monitor.py autotrade1-test-recovery       # Recovery test
python run_monitor.py guard-no-gui                   # GUI automation scan
python run_monitor.py project-health                 # Health check
python run_monitor.py autotrade1-final-check         # Full validation
python run_monitor.py release-check                  # Release folder check
```

## Known Warnings

1. **Stale ticks during after-hours/weekends:** Expected. The watchdog
   reports stale tick age but does NOT restart MT5 for this alone.
2. **Trade log may be empty if no trades occurred:** Expected.
   tradeCorelogger_v2.2 only writes trades when it opens/closes positions.
3. **Config gitignore warning:** `launch_autotrade1.ini` is not in `.gitignore`.
   Local installs should add it.
4. **`logger-trades` may return 0 rows** if scanning the latest file only
   during a quiet period. Use `--files 5` or `logger-summary` for the full
   picture.

## What Is Intentionally Not Included

- AutoTrade5 / XAUUSD — paused indefinitely
- Trading strategy logic — this runtime deploys, monitors, and recovers the EA only
- GUI automation — no pyautogui, keyboard, mouse, screenshots, or image recognition
- Trade placement — the system does not open or close trades
- EA input modification — the AutoTrade1 profile is not altered at runtime

## No-GUI Automation Policy

All deployment uses **native MT5 mechanisms**:

1. **Saved Profile** (`/profile:AutoTrade1`)
2. **Startup config** (`/config:launch_autotrade1.ini`)
3. **MetaTrader5 Python API** (account info, symbol info, tick data)

No mouse clicks, no keyboard shortcuts, no Ctrl+E, no Alt-menu navigation,
no screenshots, no image recognition.

## How to Start/Stop/Status

```powershell
# Start (launch + verify + background watchdog)
python run_monitor.py autotrade1-start

# Check status
python run_monitor.py autotrade1-status

# Stop (leaves MT5 running)
python run_monitor.py autotrade1-stop

# Stop and close MT5
python run_monitor.py autotrade1-stop --close-mt5
```

## How to Run Recovery Test

```powershell
python run_monitor.py autotrade1-test-recovery
```

This simulates an MT5 crash and verifies the watchdog detects, restarts,
and confirms the system recovers.

## Files Generated

| File | Description |
|------|-------------|
| `runtime_state/autotrade1_state.json` | Current status (overwritten) |
| `runtime_state/autotrade1_watchdog.pid` | Watchdog PID |
| `runtime_state/watchdog_out.log` | Watchdog stdout |
| `runtime_reports/autotrade1_status_*.json` | Status snapshot |
| `runtime_reports/autotrade1_soak_*.csv` | Soak test per-cycle |
| `runtime_reports/autotrade1_soak_*.json` | Soak test summary |
| `config/launch_autotrade1.ini` | MT5 startup config (credentials) |
