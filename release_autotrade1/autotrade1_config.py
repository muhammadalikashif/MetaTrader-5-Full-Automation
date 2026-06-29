"""
autotrade1_config.py

Central configuration for the AutoTrade1 production runtime.
All AutoTrade1 constants live here. Change a value once to update the entire system.
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Profile
PROFILE_NAME = "AutoTrade1"
SYMBOL = "EURUSD"
TIMEFRAME_NAME = "M5"
TIMEFRAME = 5
EA_NAME = "tradeCorelogger_v2.2"

# Account
ACCOUNT_LOGIN = 5051817950
SERVER_NAME = "MetaQuotes-Demo"
FALLBACK_PASSWORD = "7gAuQw-g"

# MT5 paths
MT5_INSTALL_DIR = r"C:\Program Files\MetaTrader 5"
TERMINAL_EXE = os.path.join(MT5_INSTALL_DIR, "terminal64.exe")
DATA_DIR = (
    r"C:\Users\kali6\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)
COMMON_FILES_DIR = (
    r"C:\Users\kali6\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
)
CONFIG_DIR = os.path.join(SCRIPT_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "launch_autotrade1.ini")

# Derived MT5 paths
TERMINAL_LOG_DIR = os.path.join(DATA_DIR, "logs")
MQL5_LOG_DIR = os.path.join(DATA_DIR, "MQL5", "Logs")
PROFILE_DIR = os.path.join(DATA_DIR, "MQL5", "Profiles", "Charts", PROFILE_NAME)

# Runtime artifacts
RUNTIME_REPORT_DIR = os.path.join(SCRIPT_DIR, "runtime_reports")
RUNTIME_STATE_DIR = os.path.join(SCRIPT_DIR, "runtime_state")
PID_FILE = os.path.join(RUNTIME_STATE_DIR, "autotrade1_watchdog.pid")
STATE_FILE = os.path.join(RUNTIME_STATE_DIR, "autotrade1_state.json")

# Thresholds
STALE_WARN_SEC = 120
STALE_CRIT_SEC = 300
FILE_STALE_SEC = 300
MT5_RECONNECT_CYCLES = 2
RESTART_COOLDOWN_SEC = 600
MAX_RESTARTS_PER_HOUR = 3
