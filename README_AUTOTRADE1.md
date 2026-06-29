# AutoTrade1 Production Runner

## Overview

AutoTrade1 is a single-EA production runtime for MetaTrader 5. It deploys
**tradeCorelogger_v2.2** on **EURUSD M5** using the **AutoTrade1** profile.

All deployment uses **native MT5 mechanisms only**:

- Saved Profile restoration
- `/config:file.ini` startup parameter
- MetaTrader5 Python API

No GUI automation (pyautogui, keyboard shortcuts, mouse clicks, screenshots,
Alt-menu navigation).

## Required Setup

| Item | Value |
|------|-------|
| Profile | `AutoTrade1` (saved with EURUSD M5 + tradeCorelogger_v2.2) |
| EA | `tradeCorelogger_v2.2.ex5` in `MQL5/Experts/` |
| Account | 5051817950 @ MetaQuotes-Demo |
| MT5 Install | `C:\Program Files\MetaTrader 5\terminal64.exe` |
| Data Dir | `...\D0E8209F77C8CF37AD8BF550E51FF075` |
| Common Files | `...\Terminal\Common\Files` (tradeCorelogger CSV logs) |
| Config File | `autotrade1_config.py` (single source of truth) |

## Folder Paths

- `D:\MT5\config\` — launch config INI (gitignored)
- `D:\MT5\runtime_state\` — `autotrade1_state.json`, `autotrade1_watchdog.pid`
- `D:\MT5\runtime_reports\` — soak test reports, status snapshots
- `D:\MT5\archive\` — obsolete GUI-automation scripts (do not use)

## Commands

### Quick Start / Stop

```powershell
python run_monitor.py autotrade1-start       # Launch + verify + start watchdog
python run_monitor.py autotrade1-stop         # Stop watchdog (MT5 stays running)
python run_monitor.py autotrade1-stop --close-mt5  # Stop watchdog + close MT5
python run_monitor.py autotrade1-status       # Show runtime state
```

### Manual Commands

```powershell
python run_monitor.py launch-autotrade1       # Cold launch: kill -> config -> launch -> verify
python run_monitor.py verify-autotrade1       # Check API, account, profile, log evidence
python run_monitor.py verify-logger-eurusd    # Check tick/trade log files, reader
python run_monitor.py autotrade1-monitor --once    # Single health check
python run_monitor.py autotrade1-monitor           # Continuous monitoring (every 30s)
python run_monitor.py autotrade1-watchdog          # Monitor + auto-restart on failures
```

### Logger Commands

```powershell
python run_monitor.py logger-summary --days 7           # Market summary + buy/sell stats
python run_monitor.py logger-ticks --symbol EURUSD      # Recent ticks
python run_monitor.py logger-trades --symbol EURUSD     # Recent trade events
```

### Testing

```powershell
python run_monitor.py autotrade1-soak --minutes 60      # Run soak test (generates CSV + JSON)
python run_monitor.py autotrade1-test-recovery          # Simulate MT5 crash + verify recovery
```

### Health Checks

```powershell
python run_monitor.py guard-no-gui                # Scan for banned GUI automation in active files
python run_monitor.py project-health              # Syntax check + guard + folders + README + gitignore
python run_monitor.py autotrade1-final-check      # Full validation suite (all checks + commands)
```

## Normal Startup Flow

1. `autotrade1-start` launches MT5 via `/config:file.ini` + `/profile:AutoTrade1`
2. Verifies account, symbol, EA load, log evidence
3. Spawns watchdog in background (writes PID to `runtime_state/`)
4. Watchdog monitors every 30s, writes state to `autotrade1_state.json`
5. On failure (MT5 crash, disconnect, frozen ticks), watchdog restarts MT5

## Stale Tick Behavior

The watchdog **does not restart MT5 for stale ticks alone**. This avoids
unnecessary restarts during after-hours / weekends when no ticks arrive.

**What triggers a restart:**
- MT5 process not running or API cannot initialize
- Terminal disconnected from trade server for 2+ consecutive cycles
- Account mismatch (wrong login detected)
- Profile directory missing
- Logger files unreadable for 3+ consecutive cycles
- Tick log file frozen (not growing) for 5+ minutes while MT5 is connected

**What does NOT trigger a restart:**
- Stale tick (tick age > threshold) -- reported as WARNING/CRITICAL health state

A stale tick warning means the EA is running but the market may be closed.
The watchdog still reports the stale tick age in status and state file,
but leaves MT5 running.

## How to Monitor

```powershell
python run_monitor.py autotrade1-status       # Quick status
python run_monitor.py autotrade1-monitor --once   # One-cycle check
```

While watchdog runs, `runtime_state/autotrade1_state.json` is always current.

## How to Stop

```powershell
python run_monitor.py autotrade1-stop
```

This stops the watchdog process. MT5 stays open. Pass `--close-mt5` to also
close the terminal.

## Soak Test

```powershell
python run_monitor.py autotrade1-soak --minutes 5
python run_monitor.py autotrade1-soak --minutes 60 --interval 30
```

Output:

- `runtime_reports/autotrade1_soak_YYYYMMDD_HHMMSS.csv` — per-cycle data
- `runtime_reports/autotrade1_soak_YYYYMMDD_HHMMSS.json` — summary

## Recovery Test

```powershell
python run_monitor.py autotrade1-test-recovery
```

This stops MT5, verifies watchdog detects the failure, waits for recovery,
verifies AutoTrade1 and logger after restart, checks restart count, then
cleans up.

## Files Generated

| File | Description |
|------|-------------|
| `runtime_state/autotrade1_state.json` | Current runtime state (overwritten every cycle) |
| `runtime_state/autotrade1_watchdog.pid` | Watchdog process ID |
| `runtime_state/watchdog_out.log` | Watchdog background output |
| `runtime_reports/autotrade1_status_*.json` | Status snapshots |
| `runtime_reports/autotrade1_soak_*.csv` | Soak test per-cycle data |
| `runtime_reports/autotrade1_soak_*.json` | Soak test summary |

## What Not to Use Anymore

- **No pyautogui** — no mouse/keyboard automation
- **No keyboard shortcuts** — no Ctrl+E, Alt+F, etc.
- **No mouse clicks** — no win32api mouse events
- **No screenshots / image recognition**
- **No Alt-menu navigation**
- **No `LaunchEACharts.mq5`** — the profile-based approach replaces it

All deployment uses saved Profile + `/config` startup flag + MetaTrader5 API.

## Configuration

Single source: `autotrade1_config.py`

```python
PROFILE_NAME = "AutoTrade1"
SYMBOL = "EURUSD"
EA_NAME = "tradeCorelogger_v2.2"
ACCOUNT_LOGIN = 5051817950
```

Change any value in `autotrade1_config.py` to update the entire runtime.
