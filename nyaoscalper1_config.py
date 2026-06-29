"""
nyaoscalper1_config.py

Central configuration for the NyaoScalper1 automation target.
Fully isolated from AutoTrade1 constants.
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Profile
PROFILE_NAME = "NyaoScalper1"
SYMBOL = "EURUSD"
TIMEFRAME_NAME = "M1"
TIMEFRAME = 1
EA_NAME = "nyao_scalper"
PRESET = "aggressive.set"

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
CONFIG_DIR = os.path.join(SCRIPT_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "launch_nyaoscalper1.ini")

# Derived MT5 paths
TERMINAL_LOG_DIR = os.path.join(DATA_DIR, "logs")
MQL5_LOG_DIR = os.path.join(DATA_DIR, "MQL5", "Logs")
PROFILE_DIR = os.path.join(DATA_DIR, "MQL5", "Profiles", "Charts", PROFILE_NAME)

# Thresholds
STALE_WARN_SEC = 120
STALE_CRIT_SEC = 300
