# MT5 Python Ecosystem — Knowledge Base

## 1. Core Python API – MetaTrader5

| Feature | Details |
|---|---|
| Install | `pip install MetaTrader5` |
| Platform | Windows 64-bit (requires MT5 terminal) |
| Capabilities | Connect, real-time quotes, ticks, bars, positions, market/pending orders, account info, margin, symbol properties |
| Docs | https://www.mql5.com/en/docs/python_metatrader5 |
| PyPI | https://pypi.org/project/metatrader5/ |

```python
import MetaTrader5 as mt5
mt5.initialize()
data = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_M1, 0, 500)
mt5.shutdown()
```

## 2. Higher-Level Helper Libraries

| Library | What it adds | Install |
|---|---|---|
| `aiomql` | Async/await wrapper for concurrent strategies | `pip install aiomql` |
| `mt5-utils` | Backtesting, signal gen, CSV export, charting (pandas/numpy) | `pip install mt5-utils` |
| `pyMetaTrader5-wrapper` | OOP wrapper with risk management helpers | `pip install pymt5wrapper` |
| `mt5-backtester` | Batch backtests, .set parsing, 40+ metrics | `pip install mt5-backtester` |
| `mt5-chart-export` | Export chart images to PNG/JPEG via API | `pip install mt5-chart-export` |

## 3. Data Science & Reporting Stack (in use)

- `pandas` — bar/tick data, indicators, CSV/Excel reports
- `numpy` — vectorized calculations for custom indicators
- `jinja2` — HTML/markdown reports (daily summaries, backtest results)
- `requests` — external data (news, calendars, sentiment)

## 4. Community Open-Source Projects

| Project | Description | Features |
|---|---|---|
| MetaTrader-Python-Examples | Collection of scripts for order handling & data retrieval | Ready-to-run demos |
| MT5-AutoTrader | Configurable trading robot framework (JSON/YAML) | Strategy plugins, risk mgmt, CSV trade log |
| MQL-Python-Bridge | C++/Python bridge to call Python from MQL | Bidirectional, works with .ex5 |
| QuantConnect (Lean) MT5 Connector | Feed MT5 data into Lean engine | Backtest with Lean platform |
| Backtrader-MT5 | Adapter for Backtrader library | Live data & orders via MetaTrader5 |

## 5. Utilities & Scripts

| Utility | Purpose | Link |
|---|---|---|
| mt5-csv-logger | Real-time trade/tick CSV logging | https://github.com/sergei-d/mt5-csv-logger |
| mt5-risk-calculator | Lot size/SL/TP based on risk % | https://github.com/QuantNomad/mt5-risk-calculator |
| MT5-Telegram-Bot | Order confirmations & alerts to Telegram | https://github.com/Alfex4936/MT5-telegram-bot |
| mt5-cron-jobs | Schedule Python MT5 strategies | https://github.com/fnadh/mt5-cron |

## 6. Learning Resources

- Official MQL5 Python Docs — complete function reference
- MetaTrader5 Python Cookbook — practical recipes (GitHub)
- YouTube: Quantra, Orchard Forex, CodeTrading — bot building walkthroughs
- Stack Overflow: `metatrader5` tag
- Reddit: `r/MetaTrader`

## 7. Sample End-to-End Workflow

```python
import MetaTrader5 as mt5
import pandas as pd, numpy as np, jinja2, requests, json
from datetime import datetime
from pathlib import Path

# 1. Connect
mt5.initialize()

# 2. Pull bars
bars = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M5, 0, 2000)
df = pd.DataFrame(bars).set_index('time')
df.index = pd.to_datetime(df.index, unit='s')

# 3. Compute indicator
df['ema20'] = df['close'].ewm(span=20).mean()

# 4. Generate signal
signal = "buy" if df.iloc[-1].close > df.iloc[-1].ema20 else "sell"

# 5. Place order
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "EURUSD",
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_BUY if signal == "buy" else mt5.ORDER_TYPE_SELL,
    "price": mt5.symbol_info_tick("EURUSD").ask if signal == "buy" else mt5.symbol_info_tick("EURUSD").bid,
    "deviation": 10,
    "magic": 234567,
    "comment": f"auto_{signal}",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_FOK,
}
result = mt5.order_send(request)

# 6. Log to CSV
Path("logs").mkdir(exist_ok=True)
with open(f"logs/{datetime.now():%Y-%m-%d}.csv", "a") as f:
    f.write(f"{datetime.now()},EURUSD,{signal},{result.retcode}\n")

# 7. Render HTML report
template = jinja2.Environment().from_string("""<h2>EURUSD {{ now }}</h2><p>Signal: <b>{{ signal }}</b></p>""")
Path("report.html").write_text(template.render(now=datetime.now(), signal=signal))

mt5.shutdown()
```

## 8. Next Steps to Explore

- **Async trading** — `aiomql` for concurrent multi-symbol strategies
- **External data** — economic calendars via `requests`
- **Automated backtesting** — `mt5-backtester` with existing .set/config.ini generation
- **Deployment** — Windows Task Scheduler for 24/7 Python bots; MQL5 launch script for EA deployment
