# MetaTrader 5 Full Automation

Python-based production runtime for MetaTrader 5 with two isolated automation
targets, a live Streamlit dashboard, and zero GUI automation.

---

## Overview

| Target | Profile | Symbol | Timeframe | EA | Status |
|--------|---------|--------|-----------|----|--------|
| **AutoTrade1** | `AutoTrade1` | EURUSD | M5 | tradeCorelogger_v2.2 | Stable Production |
| **NyaoScalper1** | `NyaoScalper1` | EURUSD | M1 | nyao_scalper | Active |

All deployment uses **native MT5 mechanisms only**:
- Saved Profile restoration
- `/config:file.ini` startup parameter
- MetaTrader5 Python API

No GUI automation (pyautogui, keyboard shortcuts, mouse clicks, screenshots,
Alt-menu navigation) is used anywhere in the codebase.

---

## Architecture

```
D:\MT5\
  autotrade1_config.py        AutoTrade1 constants
  autotrade1_runtime.py       AutoTrade1 monitor + watchdog
  verify_autotrade1.py        AutoTrade1 verification
  nyaoscalper1_config.py      NyaoScalper1 constants (isolated)
  nyaoscalper1_runtime.py     NyaoScalper1 launch + monitor
  verify_nyaoscalper1.py      NyaoScalper1 verification
  generate_launch_config.py   Shared MT5 launch config generator
  launch_mt5.py               Shared cold-start pipeline
  run_monitor.py              CLI entry point (38 commands)
  mt5_dashboard_service.py    Read-only MT5 data service
  dashboard.py                Streamlit live dashboard
  tradecore_reader.py         CSV log parser
  requirements.txt            Python dependencies
  config/                     Launch INI files (gitignored - contains credentials)
  release_autotrade1/         AutoTrade1 production release package
  archive/                    Obsolete GUI scripts (do not use)
```

---

## Setup

### Prerequisites

- MetaTrader 5 installed at `C:\Program Files\MetaTrader 5`
- Python 3.11+ with virtual environment

### Installation

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Credentials (optional - fallbacks baked into configs)
$env:MT5_LOGIN = "5051817950"
$env:MT5_PASSWORD = "7gAuQw-g"
$env:MT5_SERVER = "MetaQuotes-Demo"
```

### Required Manual Setup (one time)

1. Open MT5, log into account `5051817950 @ MetaQuotes-Demo`
2. Arrange EURUSD M5 chart + attach `tradeCorelogger_v2.2.ex5` EA
3. Save Profile As: `AutoTrade1`
4. Arrange EURUSD M1 chart + attach `nyao_scalper.ex5` EA with `aggressive.set`
5. Save Profile As: `NyaoScalper1`

Both profiles must exist before launching.

---

## AutoTrade1 (Production)

Stable single-EA runtime for EURUSD M5 + tradeCorelogger_v2.2.

### Quick Start

```powershell
python run_monitor.py autotrade1-start      # Launch + verify + watchdog
python run_monitor.py autotrade1-status     # Show runtime state
python run_monitor.py autotrade1-stop       # Stop watchdog
```

### Manual Commands

```powershell
python run_monitor.py launch-autotrade1          # Cold launch
python run_monitor.py verify-autotrade1          # Verify deployment
python run_monitor.py autotrade1-monitor --once  # Single health check
python run_monitor.py autotrade1-monitor         # Continuous monitor
python run_monitor.py autotrade1-watchdog         # Monitor + auto-restart
```

### Watchdog Behavior

The watchdog monitors every 30 seconds and restarts MT5 for:
- MT5 process/API failure
- Terminal disconnected for 2+ cycles
- Account mismatch
- Profile directory missing
- Log files unreadable for 3+ cycles
- Tick log frozen for 5+ minutes

Does **NOT** restart for stale ticks alone (avoids after-hours restarts).

### Testing

```powershell
python run_monitor.py autotrade1-soak --minutes 60
python run_monitor.py autotrade1-test-recovery
```

---

## NyaoScalper1

Isolated automation target for EURUSD M1 + nyao_scalper with aggressive preset.

### Commands

```powershell
python run_monitor.py launch-nyaoscalper1      # Cold launch
python run_monitor.py verify-nyaoscalper1      # Verify deployment
python run_monitor.py nyaoscalper1-monitor --once  # Single health check
```

No watchdog or recovery added yet -- first milestone is launch + verify +
one-shot monitor only. No trade placement, no EA input modification, no
profile changes.

---

## Live Dashboard

Read-only Streamlit dashboard showing real-time MT5 data.

### Start

```powershell
.venv\Scripts\streamlit run dashboard.py
```

### Sections

1. **Account Cards** -- Login, server, balance, equity, margin, free margin,
   margin level
2. **NyaoScalper1 Status** -- MT5 connection, algo trading, profile/chart
   integrity, EA log evidence, final status (PASS/WARNING/FAIL)
3. **Active Positions** -- Full table of open EURUSD positions with ticket,
   type, volume, prices, PnL, swap, magic, comment
4. **Position Summary** -- Counts, buy/sell volumes, floating PnL, best/worst
   PnL
5. **Market Data** -- EURUSD bid, ask, spread, tick time
6. **Recent Closed Deals** -- Last 20 EURUSD closed deals with profit, price,
   magic

Refreshes every 4 seconds. Read-only -- no trade actions, close buttons, or
restart controls.

---

## Health & Safety

### GUI Automation Guard

The codebase includes an AST scanner that enforces the no-GUI-automation rule:

```powershell
python run_monitor.py guard-no-gui
```

Banned: `pyautogui`, `keyboard`, `mouse`, `SendKeys`, `pyscreeze`,
`pygetwindow`, `win32api.mouse_event`, `ctypes.*keybd_event`, `ImageGrab.grab`

### Project Health

```powershell
python run_monitor.py project-health
```

Checks: syntax, GUI guard, required folders, profile, README, gitignore.

### AutoTrade1 Final Validation

```powershell
python run_monitor.py autotrade1-final-check
```

Full 9-step suite: health, launch, verify, logger verify, monitor, status,
summary, ticks, trades.

### Release Check

```powershell
python run_monitor.py release-check
```

Verifies `release_autotrade1/` folder integrity: 14 required files, no
credentials, no GUI automation, no syntax errors.

---

## All Commands

### AutoTrade1
| Command | Description |
|---------|-------------|
| `launch` | Cold-start MT5 with AutoTrade1 profile |
| `launch-autotrade1` | Launch + data summary |
| `verify-autotrade1` | Verify profile/chart/log evidence |
| `verify-logger-eurusd` | Verify tick/trade log files |
| `autotrade1-run` | Full workflow: launch -> verify -> logger -> monitor |
| `autotrade1-monitor` | Continuous monitoring |
| `autotrade1-watchdog` | Monitor + auto-restart |
| `autotrade1-start` | Launch + start watchdog in background |
| `autotrade1-stop` | Stop watchdog |
| `autotrade1-status` | Show runtime state |
| `autotrade1-soak` | Soak test for N minutes |
| `autotrade1-test-recovery` | Simulate MT5 crash + verify recovery |

### NyaoScalper1
| Command | Description |
|---------|-------------|
| `launch-nyaoscalper1` | Cold-start MT5 with NyaoScalper1 profile |
| `verify-nyaoscalper1` | Verify profile/chart/EA evidence |
| `nyaoscalper1-monitor` | Single health check |

### Logger
| Command | Description |
|---------|-------------|
| `logger-summary --days 7` | Market summary across all symbols |
| `logger-ticks --symbol EURUSD` | Recent tick data |
| `logger-trades --symbol EURUSD` | Recent trade events |

### Health
| Command | Description |
|---------|-------------|
| `guard-no-gui` | Scan for banned GUI automation |
| `project-health` | Full project health check |
| `autotrade1-final-check` | Full AutoTrade1 validation suite |
| `release-check` | Verify release folder integrity |

### Dashboard
| Command | Description |
|---------|-------------|
| `streamlit run dashboard.py` | Launch live dashboard |

---

## Requirements

```
MetaTrader5
psutil
pywin32
streamlit
pandas
```

Install with: `pip install -r requirements.txt`

---

## Security

- Credentials are read from environment variables (`MT5_LOGIN`,
  `MT5_PASSWORD`, `MT5_SERVER`) with fallback values in config files
- Launch INI files in `config/` contain credentials and are gitignored
- Release package `release_autotrade1/` is verified credential-free
- No secrets, API keys, or passwords are committed to the repository

---

## Project Structure

```
D:\MT5\
  .gitignore
  README.md
  requirements.txt
  *.py                          # 14 Python modules
  *.md                          # AutoTrade1 docs
  config/                       # Launch INI files (gitignored)
  runtime_state/                # State JSON, PID files
  runtime_reports/              # Status snapshots, soak test CSV/JSON
  release_autotrade1/           # Production release (14 files)
  archive/                      # Obsolete GUI scripts
  .venv/                        # Python virtual environment
```

---

## License

Private -- internal use.
