"""
Example: Run backtest for Architect_EA_v4_00.ex5
================================================
This script demonstrates how to use the MT5 Backtest Orchestrator
to run backtests on your Architect EA.

Usage:
    python run_architect_backtest.py

Or customize the parameters below before running.
"""

from pathlib import Path
from mt5_orchestrator import BacktestOrchestrator


def main():
    # ─────────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────────

    EA_NAME = "Architect_EA_v4_00"  # Without .ex5 extension
    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]
    TIMEFRAME = "H1"
    FROM_DATE = "2024.01.01"
    TO_DATE = "2024.12.31"
    DEPOSIT = 10000
    LEVERAGE = "1:100"
    MODEL = 0  # 0=Every tick, 1=1-min OHLC, 2=Open price, 3=Math, 4=Real ticks

    # EA Parameters to set (match your EA's input parameters)
    # These will be written to a .set file
    # NOTE: Architect EA uses 'i' prefix for all inputs
    SET_PARAMS = {
        "iMagicNumber": 20210600,
        "iStrategyName": "Default",
        "iMaxRetries": 5,
        "iMaxSlippage": 10,
        "iCheckConfirmation": "true",
        "iMaxTrades": 100,
        "iAutoStart": "true",
        "iAutoStartMode": 0,
        "iSingleEntrySignal": "false",
        "iAsyncMode": "true",
        "iTimeFilter": "true",
        "iSpreadMax": 0,
        "iATRPeriod": 14,
        "iATRTF": 16408,
        "iVTStartReal": 1,
        "iInvertSignal": "false",
        "iAroonSEnabled": "false",
        "iEngCandlesEnabled": "false",
        "iRMISEnabled": "false",
        "iRMIRangerEnabled": "false",
        "iPivotsSEnabled": "false",
        "iCCEnabled": "false",
        "iAMARSIEnabled": "false",
    }

    # ─────────────────────────────────────────────
    # Initialize Orchestrator
    # ─────────────────────────────────────────────

    orchestrator = BacktestOrchestrator(
        # Optional: specify paths explicitly
        # mt5_data_dir=Path(r"C:\Users\kali6\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"),
        timeout=600,  # 10 minutes max per backtest
    )

    # ─────────────────────────────────────────────
    # Option 1: Single backtest
    # ─────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("SINGLE BACKTEST: EURUSD")
    print("=" * 60)

    result = orchestrator.run_backtest(
        ea_name=EA_NAME,
        symbol="EURUSD",
        timeframe=TIMEFRAME,
        from_date=FROM_DATE,
        to_date=TO_DATE,
        deposit=DEPOSIT,
        leverage=LEVERAGE,
        model=MODEL,
        set_params=SET_PARAMS,
    )

    print_results(result)

    # ─────────────────────────────────────────────
    # Option 2: Batch backtest (multiple symbols)
    # ─────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("BATCH BACKTEST: Multiple Symbols")
    print("=" * 60)

    results = orchestrator.run_batch_backtests(
        ea_name=EA_NAME,
        symbols=SYMBOLS,
        timeframe=TIMEFRAME,
        from_date=FROM_DATE,
        to_date=TO_DATE,
        deposit=DEPOSIT,
        set_params=SET_PARAMS,
        iterations=1,  # Run each symbol once
    )

    # Print summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)
    print(f"{'Symbol':<12} {'Profit':>12} {'Trades':>8} {'DD%':>8} {'Score':>12}")
    print("-" * 55)
    for r in results:
        print(f"{r.symbol:<12} {r.profit:>12.2f} {r.total_trades:>8} "
              f"{r.relative_drawdown_pct:>7.2f}% {r.score():>12.2f}")

    # Best result
    best = max(results, key=lambda r: r.score())
    print(f"\nBest: {best.symbol} (Score: {best.score():.2f})")


def print_results(result):
    """Pretty-print a single backtest result."""
    print(f"""
Symbol:           {result.symbol}
Timeframe:        {result.timeframe}
Period:           {result.from_date} to {result.to_date}

--- Trades ---
Total Trades:     {result.total_trades}
Profit Trades:    {result.profit_trades} ({result.profit_trades_pct}%)
Loss Trades:      {result.loss_trades} ({result.loss_trades_pct}%)
Long Trades:      {result.long_trades} ({result.long_profit_pct}% win)
Short Trades:     {result.short_trades} ({result.short_profit_pct}% win)

--- Profit ---
Net Profit:       {result.profit}
Gross Profit:     {result.gross_profit}
Gross Loss:       {result.gross_loss}
Profit Factor:    {result.profit_factor}
Expected Payoff:  {result.expected_payoff}

--- Drawdown ---
Absolute DD:      {result.absolute_drawdown}
Maximal DD:       {result.maximal_drawdown} ({result.maximal_drawdown_pct}%)
Relative DD:      {result.relative_drawdown} ({result.relative_drawdown_pct}%)

--- Metrics ---
Sharpe Ratio:     {result.sharpe_ratio}
Recovery Factor:  {result.recovery_factor}
AHPR:             {result.ahpr}
LR Correlation:   {result.lr_correlation}

--- Consecutive ---
Max Wins:         {result.max_consecutive_wins} (${result.max_consecutive_profit})
Max Losses:       {result.max_consecutive_losses} (${result.max_consecutive_loss})
Avg Wins:         {result.avg_consecutive_wins}
Avg Losses:       {result.avg_consecutive_losses}

--- Score ---
Recovery Score:   {result.score():.2f}
""")

    if result.errors:
        print(f"Errors: {result.errors}")


if __name__ == "__main__":
    main()
