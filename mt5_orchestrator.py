"""
MT5 Backtest Orchestrator
=========================
Automates MT5 Strategy Tester via command-line config.ini.
Generates .set parameter files, config.ini, launches terminal64.exe,
and parses backtest reports (XML/HTML) to extract metrics.

Usage:
    from mt5_orchestrator import BacktestOrchestrator

    orchestrator = BacktestOrchestrator()
    result = orchestrator.run_backtest(
        ea_name="Architect_EA_v4_00",
        symbol="EURUSD",
        timeframe="H1",
        from_date="2024.01.01",
        to_date="2024.12.31",
        deposit=10000,
        leverage="1:100",
        set_params={"InpLotSize": 0.1, "InpStopLoss": 50},
    )
    print(result)
"""

import configparser
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Parsed backtest metrics from MT5 report."""
    symbol: str = ""
    timeframe: str = ""
    from_date: str = ""
    to_date: str = ""
    model: str = ""
    initial_deposit: float = 0.0
    leverage: str = ""
    total_trades: int = 0
    profit_trades: int = 0
    loss_trades: int = 0
    profit_trades_pct: float = 0.0
    loss_trades_pct: float = 0.0
    profit: float = 0.0
    profit_factor: float = 0.0
    expected_payoff: float = 0.0
    absolute_drawdown: float = 0.0
    maximal_drawdown: float = 0.0
    maximal_drawdown_pct: float = 0.0
    relative_drawdown: float = 0.0
    relative_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    recovery_factor: float = 0.0
    ahpr: float = 0.0
    lr_correlation: float = 0.0
    lr_standard_error: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_consecutive_profit: float = 0.0
    max_consecutive_loss: float = 0.0
    avg_consecutive_wins: float = 0.0
    avg_consecutive_losses: float = 0.0
    short_trades: int = 0
    short_profit_pct: float = 0.0
    long_trades: int = 0
    long_profit_pct: float = 0.0
    report_path: str = ""
    raw_html: str = ""
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v != "" and v != 0 and v != []}

    def score(self, method: str = "recovery") -> float:
        """Calculate a composite score for ranking."""
        if method == "recovery":
            return self.recovery_factor * (self.total_trades ** 0.5) * max(self.profit_factor, 0.01)
        elif method == "profit_dd":
            return self.profit / max(self.relative_drawdown_pct, 0.01)
        elif method == "sharpe":
            return self.sharpe_ratio * (self.total_trades ** 0.5)
        return self.profit


# ─────────────────────────────────────────────
# Set File Generator
# ─────────────────────────────────────────────

class SetFileGenerator:
    """Generates and modifies MT5 .set parameter files."""

    def __init__(self, testers_dir: Path):
        self.testers_dir = testers_dir
        self.testers_dir.mkdir(parents=True, exist_ok=True)

    def create_set_file(
        self,
        filename: str,
        parameters: dict[str, Any],
        optimization_flags: Optional[dict[str, bool]] = None,
    ) -> Path:
        """
        Create a .set file with parameters.

        Format: ParameterName=value||readonly||step||optimize||type
        - readonly: 0 or 1
        - step: step value for optimization (0 = no step)
        - optimize: 0 or 1 (whether to optimize this parameter)
        - type: 0=double, 1=int, 2=string, 3=bool, 4=enum
        """
        filepath = self.testers_dir / filename
        if not filename.endswith(".set"):
            filepath = filepath.with_suffix(".set")

        lines = []
        for name, value in parameters.items():
            opt_flag = optimization_flags.get(name, False) if optimization_flags else False
            vtype = self._infer_type(value)
            step = 0
            readonly = 0
            lines.append(f"{name}={value}||{readonly}||{step}||{int(opt_flag)}||{vtype}")

        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return filepath

    def modify_set_file(self, filename: str, updates: dict[str, Any]) -> Path:
        """Modify existing .set file with new parameter values."""
        filepath = self.testers_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f".set file not found: {filepath}")

        content = filepath.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        new_lines = []

        for line in lines:
            if "||" not in line:
                new_lines.append(line)
                continue
            param_name = line.split("=")[0].strip()
            if param_name in updates:
                parts = line.split("||")
                parts[0] = f"{param_name}={updates[param_name]}"
                new_lines.append("||".join(parts))
            else:
                new_lines.append(line)

        filepath.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return filepath

    def read_set_file(self, filename: str) -> dict[str, Any]:
        """Read parameters from an existing .set file."""
        filepath = self.testers_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f".set file not found: {filepath}")

        params = {}
        content = filepath.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            if "=" in line and "||" in line:
                name, rest = line.split("=", 1)
                value = rest.split("||")[0]
                params[name.strip()] = value
        return params

    @staticmethod
    def _infer_type(value: Any) -> int:
        """Infer MT5 parameter type from Python value."""
        if isinstance(value, bool):
            return 3
        elif isinstance(value, int):
            return 1
        elif isinstance(value, float):
            return 0
        else:
            return 2  # string/enum


# ─────────────────────────────────────────────
# Config Generator
# ─────────────────────────────────────────────

class ConfigGenerator:
    """Generates MT5 config.ini files for Strategy Tester."""

    TIMEFRAMES = {
        "M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12",
        "M15", "M20", "M30", "H1", "H2", "H3", "H4",
        "H6", "H8", "H12", "D1", "W1", "MN1",
    }

    def create_config(
        self,
        output_path: Path,
        ea_name: str,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        from_date: str = "",
        to_date: str = "",
        set_file: Optional[str] = None,
        deposit: float = 10000,
        currency: str = "USD",
        leverage: str = "1:100",
        model: int = 0,
        execution_mode: int = -1,
        optimization: int = 0,
        optimization_criterion: int = 0,
        forward_mode: int = 0,
        forward_date: str = "",
        report_name: str = "test_report",
        replace_report: int = 1,
        shutdown_terminal: int = 1,
        use_local: int = 1,
        use_remote: int = 0,
        use_cloud: int = 0,
        visual: int = 0,
        login: int = 0,
        port: int = 0,
    ) -> Path:
        """Create a config.ini file for MT5 Strategy Tester."""
        if timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {self.TIMEFRAMES}")

        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve key case (MT5 requires exact case)
        config["Tester"] = {
            "Expert": ea_name,
            "Symbol": symbol,
            "Period": timeframe,
            "Model": str(model),
            "ExecutionMode": str(execution_mode),
            "Optimization": str(optimization),
            "OptimizationCriterion": str(optimization_criterion),
            "Deposit": str(deposit),
            "Currency": currency,
            "Leverage": leverage,
            "ReplaceReport": str(replace_report),
            "ShutdownTerminal": str(shutdown_terminal),
            "UseLocal": str(use_local),
            "UseRemote": str(use_remote),
            "UseCloud": str(use_cloud),
            "Visual": str(visual),
        }

        if set_file:
            config["Tester"]["ExpertParameters"] = set_file
        if from_date:
            config["Tester"]["FromDate"] = from_date
        if to_date:
            config["Tester"]["ToDate"] = to_date
        if forward_mode:
            config["Tester"]["ForwardMode"] = str(forward_mode)
        if forward_date and forward_mode == 4:
            config["Tester"]["ForwardDate"] = forward_date
        if login:
            config["Tester"]["Login"] = str(login)
        if port:
            config["Tester"]["Port"] = str(port)

        # Report path -- no extension, MT5 adds .htm or .xml
        config["Tester"]["Report"] = report_name

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            config.write(f)

        return output_path


# ─────────────────────────────────────────────
# MT5 Launcher
# ─────────────────────────────────────────────

class MT5Launcher:
    """Launches MT5 terminal via subprocess with config.ini."""

    def __init__(
        self,
        terminal_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe",
        portable: bool = False,
        timeout: int = 600,
    ):
        self.terminal_path = terminal_path
        self.portable = portable
        self.timeout = timeout

        if not os.path.exists(terminal_path):
            raise FileNotFoundError(f"MT5 terminal not found: {terminal_path}")

    def launch(self, config_path: Path) -> subprocess.CompletedProcess:
        """
        Launch MT5 with the given config.ini.
        Blocks until MT5 exits (ShutdownTerminal=1 required).
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        args = [self.terminal_path]
        if self.portable:
            args.append("/portable")
        args.append(f"/config:{config_path}")

        print(f"[MT5] Launching: {' '.join(args)}")
        print(f"[MT5] Config: {config_path}")
        print(f"[MT5] Waiting for backtest to complete (timeout: {self.timeout}s)...")

        start = time.time()
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=os.path.dirname(self.terminal_path),
        )
        elapsed = time.time() - start
        print(f"[MT5] Process exited after {elapsed:.1f}s (return code: {result.returncode})")

        return result

    def launch_via_batch(self, batch_path: Path) -> subprocess.CompletedProcess:
        """Launch MT5 via a .bat wrapper (more reliable on some systems)."""
        if not batch_path.exists():
            raise FileNotFoundError(f"Batch file not found: {batch_path}")

        print(f"[MT5] Running batch: {batch_path}")
        start = time.time()
        result = subprocess.run(
            ["cmd", "/c", str(batch_path)],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=batch_path.parent,
        )
        elapsed = time.time() - start
        print(f"[MT5] Batch completed after {elapsed:.1f}s (return code: {result.returncode})")

        return result


# ─────────────────────────────────────────────
# Report Parser
# ─────────────────────────────────────────────

class ReportParser:
    """Parses MT5 backtest reports (HTML/XML) to extract metrics."""

    # Regex patterns for HTML report parsing
    PATTERNS = {
        "initial_deposit": r"Initial deposit[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "leverage": r"Leverage[\s\S]*?<td[^>]*>([\d:]+)",
        "total_trades": r"Total trades[\s\S]*?<td[^>]*>(\d+)",
        "profit_trades": r"Profit trades[\s\S]*?<td[^>]*>(\d+)",
        "loss_trades": r"Loss trades[\s\S]*?<td[^>]*>(\d+)",
        "profit_trades_pct": r"Profit trades[\s\S]*?<td[^>]*>\d+.*?\(([\d.]+)%",
        "loss_trades_pct": r"Loss trades[\s\S]*?<td[^>]*>\d+.*?\(([\d.]+)%",
        "profit": r"Profit[\s\S]*?<td[^>]*>(-?[\d,]+\.?\d*)",
        "profit_factor": r"Profit Factor[\s\S]*?<td[^>]*>([\d.]+)",
        "expected_payoff": r"Expected Payoff[\s\S]*?<td[^>]*>(-?[\d.]+)",
        "absolute_drawdown": r"Absolute Drawdown[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "maximal_drawdown": r"Maximal Drawdown[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "maximal_drawdown_pct": r"Maximal Drawdown[\s\S]*?<td[^>]*>[\d,]+\.?\d*\s*\(([\d.]+)%",
        "relative_drawdown": r"Relative Drawdown[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "relative_drawdown_pct": r"Relative Drawdown[\s\S]*?<td[^>]*>[\d,]+\.?\d*\s*\(([\d.]+)%",
        "sharpe_ratio": r"Sharpe Ratio[\s\S]*?<td[^>]*>(-?[\d.]+)",
        "recovery_factor": r"Recovery Factor[\s\S]*?<td[^>]*>(-?[\d.]+)",
        "ahpr": r"AHPR[\s\S]*?<td[^>]*>([\d.]+)",
        "lr_correlation": r"LR Correlation[\s\S]*?<td[^>]*>(-?[\d.]+)",
        "lr_standard_error": r"LR Standard Error[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "gross_profit": r"Gross Profit[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "gross_loss": r"Gross Loss[\s\S]*?<td[^>]*>(-?[\d,]+\.?\d*)",
        "max_consecutive_wins": r"Maximal consecutive win[\s\S]*?<td[^>]*>(\d+)",
        "max_consecutive_losses": r"Maximal consecutive loss[\s\S]*?<td[^>]*>(\d+)",
        "max_consecutive_profit": r"Maximal consecutive profit[\s\S]*?<td[^>]*>([\d,]+\.?\d*)",
        "max_consecutive_loss": r"Maximal consecutive loss[\s\S]*?<td[^>]*>(-?[\d,]+\.?\d*)",
        "avg_consecutive_wins": r"Average consecutive wins[\s\S]*?<td[^>]*>([\d.]+)",
        "avg_consecutive_losses": r"Average consecutive losses[\s\S]*?<td[^>]*>([\d.]+)",
        "short_trades": r"Short positions \(won %\)[\s\S]*?<td[^>]*>(\d+)",
        "short_profit_pct": r"Short positions \(won %\)[\s\S]*?<td[^>]*>\d+\s*\(([\d.]+)%",
        "long_trades": r"Long positions \(won %\)[\s\S]*?<td[^>]*>(\d+)",
        "long_profit_pct": r"Long positions \(won %\)[\s\S]*?<td[^>]*>\d+\s*\(([\d.]+)%",
    }

    def parse_html(self, report_path: Path) -> BacktestResult:
        """Parse an HTML (.htm) backtest report."""
        result = BacktestResult()
        result.report_path = str(report_path)

        if not report_path.exists():
            result.errors.append(f"Report file not found: {report_path}")
            return result

        html = report_path.read_text(encoding="utf-8", errors="replace")
        result.raw_html = html[:5000]  # Store first 5000 chars for debugging

        for key, pattern in self.PATTERNS.items():
            match = re.search(pattern, html)
            if match:
                value = match.group(1).replace(",", "")
                try:
                    if key in ("total_trades", "profit_trades", "loss_trades",
                               "max_consecutive_wins", "max_consecutive_losses",
                               "short_trades", "long_trades"):
                        setattr(result, key, int(value))
                    elif key in ("profit_trades_pct", "loss_trades_pct",
                                 "maximal_drawdown_pct", "relative_drawdown_pct",
                                 "short_profit_pct", "long_profit_pct"):
                        setattr(result, key, float(value))
                    else:
                        setattr(result, key, float(value))
                except ValueError:
                    result.errors.append(f"Could not parse {key}={value}")

        # Extract symbol/timeframe from report header if available
        symbol_match = re.search(r"Symbol[:\s]+(\w+)", html)
        if symbol_match:
            result.symbol = symbol_match.group(1)

        tf_match = re.search(r"Period[:\s]+(\w+)", html)
        if tf_match:
            result.timeframe = tf_match.group(1)

        return result

    def parse_xml(self, report_path: Path) -> list[dict]:
        """Parse an XML optimization report (returns list of passes)."""
        if not report_path.exists():
            return []

        tree = ET.parse(report_path)
        root = tree.getroot()

        passes = []
        for child in root:
            if child.tag == "Pass":
                pass_data = {}
                for attr in child.attrib:
                    pass_data[attr] = child.attrib[attr]
                passes.append(pass_data)

        return passes


# ─────────────────────────────────────────────
# Main Orchestrator
# ─────────────────────────────────────────────

class BacktestOrchestrator:
    """
    Main orchestrator for MT5 backtest automation.

    Example:
        orchestrator = BacktestOrchestrator()
        result = orchestrator.run_backtest(
            ea_name="Architect_EA_v4_00",
            symbol="EURUSD",
            timeframe="H1",
            from_date="2024.01.01",
            to_date="2024.12.31",
            deposit=10000,
            set_params={"InpLotSize": 0.1, "InpStopLoss": 50},
        )
        print(f"Profit: {result.profit}, Trades: {result.total_trades}")
    """

    def __init__(
        self,
        mt5_data_dir: Optional[Path] = None,
        terminal_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe",
        config_dir: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
        portable: bool = False,
        timeout: int = 600,
    ):
        # Auto-detect MT5 data directory if not provided
        if mt5_data_dir is None:
            appdata = os.environ.get("APPDATA", "")
            terminal_id = "D0E8209F77C8CF37AD8BF550E51FF075"  # Common default
            mt5_data_dir = Path(appdata) / "MetaQuotes" / "Terminal" / terminal_id
            if not mt5_data_dir.exists():
                # Try to find the actual instance ID
                mq_dir = Path(appdata) / "MetaQuotes" / "Terminal"
                if mq_dir.exists():
                    for d in mq_dir.iterdir():
                        if d.is_dir() and d.name != "Common" and d.name != "Community":
                            mt5_data_dir = d
                            break

        self.mt5_data_dir = Path(mt5_data_dir)
        self.config_dir = Path(config_dir) if config_dir else self.mt5_data_dir / "Config"
        self.reports_dir = Path(reports_dir) if reports_dir else self.mt5_data_dir / "Tester"

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        testers_dir = self.mt5_data_dir / "MQL5" / "Profiles" / "Tester"
        self.set_generator = SetFileGenerator(testers_dir)
        self.config_generator = ConfigGenerator()
        self.launcher = MT5Launcher(terminal_path, portable=portable, timeout=timeout)
        self.report_parser = ReportParser()

        # Enable DLL imports if required by EA
        self._ensure_dll_enabled()

        print(f"[Orchestrator] MT5 Data: {self.mt5_data_dir}")
        print(f"[Orchestrator] Config dir: {self.config_dir}")
        print(f"[Orchestrator] Reports dir: {self.reports_dir}")
        print(f"[Orchestrator] Testers dir: {testers_dir}")

    def _ensure_dll_enabled(self):
        """Enable DLL imports in common.ini if disabled."""
        common_ini = self.config_dir / "common.ini"
        if not common_ini.exists():
            return
        content = common_ini.read_text(encoding="utf-8")
        if "AllowDllImport=0" in content:
            content = content.replace("AllowDllImport=0", "AllowDllImport=1")
            common_ini.write_text(content, encoding="utf-8")
            print("[Orchestrator] Enabled DLL imports in common.ini")

    def run_backtest(
        self,
        ea_name: str,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        from_date: str = "",
        to_date: str = "",
        deposit: float = 10000,
        currency: str = "USD",
        leverage: str = "1:100",
        model: int = 0,
        optimization: int = 0,
        set_params: Optional[dict] = None,
        set_filename: Optional[str] = None,
        report_name: Optional[str] = None,
        forward_mode: int = 0,
        shutdown_terminal: int = 1,
    ) -> BacktestResult:
        """
        Run a complete backtest cycle:
        1. Generate .set file (if params provided)
        2. Generate config.ini
        3. Launch MT5
        4. Parse report
        5. Return results
        """
        # Step 1: Generate .set file
        set_file = None
        if set_params:
            if set_filename is None:
                set_filename = f"{ea_name}.set"
            set_path = self.set_generator.create_set_file(set_filename, set_params)
            set_file = set_filename
            print(f"[Orchestrator] Created .set file: {set_path}")

        # Step 2: Generate config.ini
        if report_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_name = f"reports\\{ea_name}_{symbol}_{timestamp}"

        # Ensure report subdirectory exists (MT5 requires it)
        report_path_normalized = report_name.replace("\\", os.sep).replace("/", os.sep)
        report_full_path = self.mt5_data_dir / report_path_normalized
        report_full_path.parent.mkdir(parents=True, exist_ok=True)

        config_path = self.config_dir / f"backtest_{ea_name}_{symbol}.ini"
        self.config_generator.create_config(
            output_path=config_path,
            ea_name=ea_name,
            symbol=symbol,
            timeframe=timeframe,
            from_date=from_date,
            to_date=to_date,
            set_file=set_file,
            deposit=deposit,
            currency=currency,
            leverage=leverage,
            model=model,
            optimization=optimization,
            forward_mode=forward_mode,
            report_name=report_name,
            shutdown_terminal=shutdown_terminal,
        )
        print(f"[Orchestrator] Created config: {config_path}")

        # Step 3: Launch MT5
        self.launcher.launch(config_path)

        # Step 4: Find and parse report
        # MT5 saves reports relative to the platform directory
        # If report_name contains path separators, it's relative to MT5 data dir
        report_base = report_name.replace("\\", os.sep).replace("/", os.sep)
        report_html = self.mt5_data_dir / f"{report_base}.htm"
        report_xml = self.mt5_data_dir / f"{report_base}.xml"

        # Check for report file
        if report_html.exists():
            print(f"[Orchestrator] Found HTML report: {report_html}")
            result = self.report_parser.parse_html(report_html)
        elif report_xml.exists():
            print(f"[Orchestrator] Found XML report: {report_xml}")
            passes = self.report_parser.parse_xml(report_xml)
            result = BacktestResult()
            result.report_path = str(report_xml)
            result.raw_html = str(passes)
            if passes:
                result.total_trades = len(passes)
        else:
            # Try to find the most recent report
            print(f"[Orchestrator] Report not found at expected path, searching...")
            result = self._find_latest_report()

        result.symbol = symbol
        result.timeframe = timeframe
        result.from_date = from_date
        result.to_date = to_date

        return result

    def run_batch_backtests(
        self,
        ea_name: str,
        symbols: list[str],
        timeframe: str = "H1",
        from_date: str = "",
        to_date: str = "",
        deposit: float = 10000,
        set_params: Optional[dict] = None,
        iterations: int = 1,
    ) -> list[BacktestResult]:
        """Run backtests for multiple symbols."""
        results = []
        for symbol in symbols:
            for i in range(iterations):
                print(f"\n{'='*60}")
                print(f"[Batch] Symbol: {symbol}, Iteration: {i+1}/{iterations}")
                print(f"{'='*60}")

                report_name = f"reports\\{ea_name}_{symbol}_iter{i+1}"
                result = self.run_backtest(
                    ea_name=ea_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    from_date=from_date,
                    to_date=to_date,
                    deposit=deposit,
                    set_params=set_params,
                    report_name=report_name,
                )
                results.append(result)

                print(f"[Batch] Result: Profit={result.profit}, "
                      f"Trades={result.total_trades}, "
                      f"DD={result.relative_drawdown_pct}%")

        return results

    def _find_latest_report(self) -> BacktestResult:
        """Find the most recent HTML report in the Tester directory."""
        tester_dir = self.mt5_data_dir / "Tester"
        if not tester_dir.exists():
            result = BacktestResult()
            result.errors.append("Tester directory not found")
            return result

        html_files = list(tester_dir.glob("*.htm")) + list(tester_dir.glob("*.html"))
        if not html_files:
            # Check subdirectories
            for subdir in tester_dir.rglob("*.htm"):
                html_files.append(subdir)

        if not html_files:
            result = BacktestResult()
            result.errors.append("No HTML report files found")
            return result

        latest = max(html_files, key=lambda f: f.stat().st_mtime)
        print(f"[Orchestrator] Using latest report: {latest}")
        return self.report_parser.parse_html(latest)


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MT5 Backtest Orchestrator")
    parser.add_argument("--ea", required=True, help="EA name (without .ex5)")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to test")
    parser.add_argument("--timeframe", default="H1", help="Timeframe (M1-MN1)")
    parser.add_argument("--from-date", default="", help="Start date (YYYY.MM.DD)")
    parser.add_argument("--to-date", default="", help="End date (YYYY.MM.DD)")
    parser.add_argument("--deposit", type=float, default=10000, help="Initial deposit")
    parser.add_argument("--leverage", default="1:100", help="Leverage")
    parser.add_argument("--model", type=int, default=0, help="Tick model (0-4)")
    parser.add_argument("--param", action="append", nargs=2, metavar=("NAME", "VALUE"),
                        help="Set parameter (can be repeated)")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds")
    parser.add_argument("--mt5-data-dir", help="MT5 data directory")

    args = parser.parse_args()

    set_params = {}
    if args.param:
        for name, value in args.param:
            # Try to convert to number
            try:
                value = float(value)
                if value == int(value):
                    value = int(value)
            except ValueError:
                pass
            set_params[name] = value

    orchestrator = BacktestOrchestrator(
        mt5_data_dir=Path(args.mt5_data_dir) if args.mt5_data_dir else None,
        timeout=args.timeout,
    )

    result = orchestrator.run_backtest(
        ea_name=args.ea,
        symbol=args.symbol,
        timeframe=args.timeframe,
        from_date=args.from_date,
        to_date=args.to_date,
        deposit=args.deposit,
        leverage=args.leverage,
        model=args.model,
        set_params=set_params if set_params else None,
    )

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"Symbol:           {result.symbol}")
    print(f"Timeframe:        {result.timeframe}")
    print(f"Period:           {result.from_date} to {result.to_date}")
    print(f"Total Trades:     {result.total_trades}")
    print(f"Profit:           {result.profit}")
    print(f"Profit Factor:    {result.profit_factor}")
    print(f"Expected Payoff:  {result.expected_payoff}")
    print(f"Rel. Drawdown:    {result.relative_drawdown_pct}%")
    print(f"Recovery Factor:  {result.recovery_factor}")
    print(f"Sharpe Ratio:     {result.sharpe_ratio}")
    print(f"Score:            {result.score():.2f}")
    if result.errors:
        print(f"\nErrors: {result.errors}")
