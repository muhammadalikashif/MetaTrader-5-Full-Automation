# AutoTrade1 Runtime — Handover Document

## System Purpose

AutoTrade1 is a production-grade runtime for running the
**tradeCorelogger_v2.2** Expert Advisor on **EURUSD M5** in MetaTrader 5.

It provides:

- **Cold deployment** — from a stopped state to logged-in, EA-active terminal
- **Continuous monitoring** — health checks every N seconds
- **Watchdog recovery** — auto-restart MT5 on crash/disconnect/infra failure
- **Runtime state tracking** — JSON state file written every cycle
- **Soak testing** — run for N minutes, get CSV + JSON report
- **Recovery testing** — simulate MT5 crash, verify auto-recovery

## Architecture

```
run_monitor.py              CLI entry point (31 subcommands via argparse)
  ├── launch_mt5.py          Cold-start pipeline (kill -> config -> launch)
  ├── verify_autotrade1.py   Deployment verification
  ├── autotrade1_runtime.py  Monitor, watchdog, stale detection
  ├── tradecore_reader.py    CSV log parser (tick + trade)
  ├── generate_launch_config.py  INI file generator
  └── autotrade1_config.py   Central configuration (single source of truth)
```

## Runtime Flow

```
autotrade1-start
  └── launch_mt5 (kill -> config -> launch with /profile)
       └── verify_autotrade1 (API, account, symbol, profile, logs)
            └── spawn watchdog in background

Watchdog loop (every N seconds):
  └── AutoTrade1Monitor.run()
       ├── _check_api()       MT5 init, account info, terminal info, symbol tick
       ├── _check_profile()   Profile directory exists
       ├── _check_logs()      EA loaded evidence in terminal log
       ├── _check_tick_log()  Read latest tick CSV
       └── _check_trade_log() Read latest trade CSV
  └── _write_state()          Write autotrade1_state.json
  └── Decide if restart needed
       └── If yes: launch_mt5.main()
```

## Main Commands

| Command | Purpose |
|---------|---------|
| `autotrade1-start` | Full startup: launch -> verify -> watchdog bg |
| `autotrade1-stop` | Stop watchdog (optional `--close-mt5`) |
| `autotrade1-status` | Read state file, compact display |
| `launch-autotrade1` | Cold launch only (no watchdog) |
| `verify-autotrade1` | Check deployment status |
| `verify-logger-eurusd` | Check CSV log files |
| `autotrade1-monitor` | Health check loop or `--once` |
| `autotrade1-watchdog` | Recovery loop with auto-restart |
| `autotrade1-soak` | Duration-based test with reports |
| `autotrade1-test-recovery` | Simulate crash, verify recovery |
| `guard-no-gui` | Scan for banned GUI automation |
| `project-health` | Syntax, folders, README, guard |
| `autotrade1-final-check` | Full validation suite |
| `release-check` | Release folder integrity |
| `logger-summary` | Market summary across symbols |
| `logger-ticks` | Recent tick data |
| `logger-trades` | Recent trade events |

## Folder Structure

```
D:\MT5\
├── autotrade1_config.py          Central config (single source of truth)
├── autotrade1_runtime.py         Monitor, watchdog, state, reports
├── generate_launch_config.py     INI generator
├── launch_mt5.py                 Cold-start pipeline
├── run_monitor.py                CLI entry point
├── tradecore_reader.py           CSV parser
├── verify_autotrade1.py          Deployment verification
├── README_AUTOTRADE1.md          Operations guide
├── requirements.txt              Python dependencies
├── config/
│   ├── launch_autotrade1.ini     MT5 startup config (gitignored, has credentials)
│   └── README_LOCAL_CONFIG.md    Config folder warning
├── runtime_state/
│   ├── autotrade1_state.json     Current runtime state
│   ├── autotrade1_watchdog.pid   Watchdog PID
│   └── watchdog_out.log          Background output
├── runtime_reports/
│   ├── autotrade1_status_*.json  Status snapshots
│   └── autotrade1_soak_*.csv/*.json  Soak test reports
├── archive/                      Obsolete GUI scripts (do not use)
├── release_autotrade1/           Release package (this document lives here)
└── .venv/                        Virtual environment
```

## Generated Files

| File | When | Contents |
|------|------|----------|
| `autotrade1_state.json` | Every monitor/watchdog cycle | Status, MT5 connection, account, tick age, warnings, criticals, restart count, uptime |
| `autotrade1_watchdog.pid` | `autotrade1-start` | Process ID of background watchdog |
| `watchdog_out.log` | Watchdog running | Stdout from background watchdog process |
| `autotrade1_status_*.json` | `autotrade1-start` or monitor | Full snapshot with profile/symbol/EA info |
| `autotrade1_soak_*.csv` | `autotrade1-soak` | Per-cycle metrics (tick age, rows, status) |
| `autotrade1_soak_*.json` | `autotrade1-soak` | Summary (duration, cycles, min/max tick age) |
| `launch_autotrade1.ini` | `launch-autotrade1` or `autotrade1-start` | MT5 startup config with credentials |

## Monitoring Behavior

The monitor writes state every cycle. The state file is always current.
Use `autotrade1-status` to read it.

State transitions:

1. **PASS** — All checks OK, tick arriving, EA loaded
2. **WARNING** — Non-critical issues (tick stale > 2 min, algo disabled, no EA log evidence)
3. **CRITICAL** — Critical issues (tick stale > 5 min, terminal disconnected, no tick log)

## Watchdog Restart Policy

The watchdog **only restarts MT5 for infrastructure failures**:

| Condition | Restarts? |
|-----------|-----------|
| MT5 process not running | Yes |
| MT5 API cannot initialize | Yes |
| Terminal disconnected 2+ consecutive cycles | Yes |
| Account login mismatch | Yes |
| Profile directory missing | Yes |
| Logger files unreadable 3+ consecutive cycles | Yes |
| Tick log frozen 5+ minutes while MT5 connected | Yes |
| Stale tick (tick age > threshold) | **No** — reported as WARNING/CRITICAL only |

Stale ticks alone never trigger a restart. This avoids unnecessary recovery
during after-hours, weekends, or low-volatility periods.

## Known Limitations

1. **Tick timing uses server time** — CSV timestamps are in MetaQuotes-Demo
   server time (GMT+3). Stale tick detection computes server GMT offset
   dynamically from `symbol_info_tick().time`.
2. **Trade log may be empty** — tradeCorelogger_v2.2 only writes trades when
   it opens/closes positions. A quiet period produces 0 trade rows.
3. **CSV encoding** — MT5 writes CSV in UTF-8 with BOM. The reader falls back
   to UTF-16-LE and other encodings automatically.
4. **File locking** — If MT5 has the CSV file open exclusively, `PermissionError`
   occurs. Add `FILE_SHARE_READ` to tradeCorelogger and recompile to fix.
5. **Config credentials** — `launch_autotrade1.ini` contains account password
   in plain text. Do not commit this file.

## Troubleshooting Guide

### MT5 does not start

```
ERROR: MT5 did not start within 30s
```

Check:
- Is `terminal64.exe` at the path in `autotrade1_config.py`?
- Is the config file at `CONFIG_PATH` valid?
- Is another MT5 instance running? Kill it first.

### EA not loading

```
AUTOTRADE1 VERIFY: FAIL
EA Log Evidence: Not Found
```

Check:
- Is `tradeCorelogger_v2.2.ex5` in `MQL5/Experts/`?
- Is the AutoTrade1 profile saved correctly?
- Check MT5 terminal logs for compilation errors.

### Tick log missing

```
AUTOTRADE1 VERIFY: FAIL
Tick Log: Missing
```

Check:
- Is tradeCorelogger_v2.2 running and attached to EURUSD M5?
- Is `LOGGING_ENABLED=true` in the EA inputs?
- Check `MQL5/Common/Files/` for CSV files.

### Tick log locked

```
[SKIP] TickLog_EURUSD_2026.06.22.csv -- locked by MT5
```

Fix: Add `FILE_SHARE_READ` flag to the EA's file open call and recompile.

### Watchdog not starting

```
No watchdog PID file found. Watchdog may not be running.
```

Check:
- Run `autotrade1-start` first.
- Check `runtime_state/` for `autotrade1_watchdog.pid`.
- Check `watchdog_out.log` for errors.

### Stale ticks in after-hours

Expected. The watchdog does not restart MT5 for stale ticks alone.
Check `autotrade1-status` — if tick age is high but market is closed,
ignore it.

## Configuration

All system configuration lives in `autotrade1_config.py`:

```python
PROFILE_NAME = "AutoTrade1"      # MT5 saved profile name
SYMBOL = "EURUSD"                # Trading symbol
EA_NAME = "tradeCorelogger_v2.2" # EA file name
ACCOUNT_LOGIN = 5051817950        # Account number
```

Change any value to update the entire runtime.
