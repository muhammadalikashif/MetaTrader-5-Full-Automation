"""
dashboard.py

Read-only Streamlit dashboard for MT5 automation project.
Displays account info, NyaoScalper1 status, positions, market data, recent deals.
No trade actions, no close buttons, no restart controls.
"""

import time
from datetime import datetime

import streamlit as st
import pandas as pd

from mt5_dashboard_service import MTSDashboardService
from nyaoscalper1_config import SYMBOL, PROFILE_NAME, TIMEFRAME_NAME, PRESET

st.set_page_config(
    page_title="MT5 Live Dashboard",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

st.title("MT5 Live Trading Dashboard")
st.caption(f"{PROFILE_NAME} / {SYMBOL} / {TIMEFRAME_NAME} / {PRESET}")

data = MTSDashboardService().fetch_all()

if not data.get("connected"):
    st.error("## MT5 Not Connected")
    st.warning("Start MT5 first using: `python run_monitor.py launch-nyaoscalper1`")
    st.stop()

account = data["account"]
terminal = data["terminal"]
tick = data["tick"]
positions = data["positions"]
deals = data["deals"]
status = data["status"]
summary = data["summary"]

# ---------------------------------------------------------------------------
# Account Cards
# ---------------------------------------------------------------------------
st.subheader("Account")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Login", account.get("login", "?"))
    st.metric("Balance", f"${account.get('balance', 0):,.2f}")
with col2:
    st.metric("Server", account.get("server", "?"))
    st.metric("Equity", f"${account.get('equity', 0):,.2f}")
with col3:
    st.metric("Currency", account.get("currency", "?"))
    st.metric("Margin", f"${account.get('margin', 0):,.2f}")
with col4:
    st.metric("Leverage", f"1:{account.get('leverage', 0)}")
    st.metric("Free Margin", f"${account.get('margin_free', 0):,.2f}")

ml = account.get("margin_level")
st.metric("Margin Level", f"{ml:.2f}%" if ml else "N/A")

# ---------------------------------------------------------------------------
# NyaoScalper1 Status
# ---------------------------------------------------------------------------
st.subheader("NyaoScalper1 Status")

ea_evidence = status.get("ea_log_evidence", False)
profile_ok = status.get("profile_folder", False)
chart_ok = status.get("chart_file", False)
algo_enabled = account.get("trade_allowed", False)
n_errors = len(status.get("errors", []))

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.metric("MT5 Connected", "Yes" if data["connected"] else "No")
    st.metric("Profile", PROFILE_NAME)
with s2:
    st.metric("Algo Trading", "Enabled" if algo_enabled else "Disabled")
    st.metric("Symbol", SYMBOL)
with s3:
    st.metric("Profile Folder", "Found" if profile_ok else "Missing")
    st.metric("Timeframe", TIMEFRAME_NAME)
with s4:
    st.metric("EA Evidence", "Found" if ea_evidence else "Not Found")
    st.metric("Chart File", "Found" if chart_ok else "Missing")

final = "PASS" if (data["connected"] and algo_enabled and profile_ok and chart_ok) else "FAIL" if not data["connected"] else "WARNING"
st.metric("Final Status", final)

if status.get("ea_log_lines"):
    with st.expander("EA Log Lines"):
        for line in status["ea_log_lines"][-5:]:
            st.code(line[:200])

# ---------------------------------------------------------------------------
# Active Positions
# ---------------------------------------------------------------------------
st.subheader("Active EURUSD Positions")

p1, p2, p3, p4 = st.columns(4)
with p1:
    st.metric("Open Positions", summary["count"])
    st.metric("Floating PnL", f"${summary['floating_pnl']:+.2f}")
with p2:
    st.metric("Buy Count", summary["buy_count"])
    st.metric("Sell Count", summary["sell_count"])
with p3:
    st.metric("Buy Volume", f"{summary['buy_volume']:.2f}")
    st.metric("Sell Volume", f"{summary['sell_volume']:.2f}")
with p4:
    best = summary["best_pnl"]
    worst = summary["worst_pnl"]
    st.metric("Best Position PnL", f"${best:+.2f}")
    st.metric("Worst Position PnL", f"${worst:+.2f}")

if not positions.empty:
    cols = ["ticket", "time", "type", "volume", "open_price", "current_price",
            "sl", "tp", "profit", "swap", "magic", "comment"]
    df = positions[cols].copy()
    df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["profit"] = df["profit"].apply(lambda x: f"{x:+.2f}")
    df["open_price"] = df["open_price"].apply(lambda x: f"{x:.5f}")
    df["current_price"] = df["current_price"].apply(lambda x: f"{x:.5f}")
    st.dataframe(df, use_container_width=True)
else:
    st.info("No active EURUSD positions")

# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------
st.subheader("Market Data")

if tick:
    m1, m2, m3, m4_c = st.columns(4)
    with m1:
        st.metric("EURUSD Bid", f"{tick.get('bid', 0):.5f}")
    with m2:
        st.metric("EURUSD Ask", f"{tick.get('ask', 0):.5f}")
    with m3:
        st.metric("Spread", f"{tick.get('spread', 0):.1f}")
    with m4_c:
        tt = tick.get("time")
        st.metric("Tick Time", tt.strftime("%H:%M:%S") if tt else "N/A")
else:
    st.warning("No tick data available")

# ---------------------------------------------------------------------------
# Recent Closed Deals
# ---------------------------------------------------------------------------
st.subheader("Recent EURUSD Closed Deals (Last 20)")

if not deals.empty:
    dcols = ["time", "ticket", "type", "volume", "price", "profit", "magic", "comment"]
    ddf = deals[dcols].copy()
    ddf["time"] = ddf["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    ddf["profit"] = ddf["profit"].apply(lambda x: f"{x:+.2f}")
    ddf["price"] = ddf["price"].apply(lambda x: f"{x:.5f}")
    st.dataframe(ddf, use_container_width=True)
else:
    st.info("No recent closed deals for EURUSD")

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
time.sleep(4)
st.rerun()
