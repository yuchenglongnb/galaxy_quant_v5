# -*- coding: utf-8 -*-
"""Evaluate auction signals with A-share T+1 executable return labels."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from config.settings import DBConfig, MarketConfig


TARGET_TYPE_MAP = {
    "ETF": "ETF",
    "etf": "ETF",
    "个股": "stock",
    "stock": "stock",
    "指数": "index",
    "index": "index",
    "行业": "industry",
    "industry": "industry",
}
INTRADAY_FILES = {
    "ETF": "etf_1min.csv",
    "stock": "stocks_1min.csv",
    "index": "indices_1min.csv",
}


@dataclass(frozen=True)
class T1BacktestConfig:
    validation_path: str = os.path.join("reports", "validation", "auction_signal_validation.csv")
    store_root: str = DBConfig.STORE_PATH
    output_root: str = os.path.join("reports", "t1_backtest")
    entry_mode: str = "open_proxy"
    actionable_only: bool = True


class T1BacktestRunner:
    """Build T+1 labels without leaking post-close outcomes into signal generation."""

    def __init__(self, config: T1BacktestConfig | None = None):
        self.config = config or T1BacktestConfig()
        self._quote_cache: dict[tuple[str, str], pd.DataFrame] = {}
        self._calendar = self._load_store_calendar()
        self._next_day = {
            date: self._calendar[index + 1]
            for index, date in enumerate(self._calendar[:-1])
        }
        self._name_code = {
            "ETF": {name: code for code, name in MarketConfig.THEME_ETFS.items()},
            "index": {name: code for code, name in MarketConfig.MAIN_INDICES.items()},
        }

    def run(self, start_date=None, end_date=None):
        detail = self._load_detail(start_date, end_date)
        if detail.empty:
            raise ValueError("No closed actionable auction signals found for the requested range.")
        outcomes = pd.DataFrame([self._build_outcome(row) for _, row in detail.iterrows()])
        outcomes = outcomes[outcomes["t1_date"].notna()].copy()
        start_date = str(detail["date"].min())
        end_date = str(detail["date"].max())
        output_dir = os.path.join(
            self.config.output_root,
            f"{start_date}_{end_date}",
            self.config.entry_mode,
        )
        os.makedirs(output_dir, exist_ok=True)

        trade_samples = outcomes[outcomes["trade_eligible"] & outcomes["quote_complete"]].copy()
        diagnostic_samples = outcomes[outcomes["quote_complete"]].copy()
        summary = self._summarize(trade_samples, ["signal_category", "universe_type"])
        by_scenario = self._summarize(trade_samples, ["signal_category", "universe_type", "scenario"])
        by_regime = self._summarize(trade_samples, ["signal_category", "universe_type", "market_regime"])
        by_layer = self._summarize(trade_samples, ["strategy_layer", "signal_category", "universe_type"])
        monthly = self._summarize_monthly(trade_samples)
        coverage = self._coverage(outcomes)

        paths = {
            "outcomes": os.path.join(output_dir, "t1_signal_outcomes.csv"),
            "trades": os.path.join(output_dir, "t1_trade_samples.csv"),
            "summary": os.path.join(output_dir, "t1_trade_summary.csv"),
            "by_scenario": os.path.join(output_dir, "t1_trade_by_scenario.csv"),
            "by_regime": os.path.join(output_dir, "t1_trade_by_regime.csv"),
            "by_layer": os.path.join(output_dir, "t1_trade_by_layer.csv"),
            "monthly": os.path.join(output_dir, "t1_trade_monthly.csv"),
            "coverage": os.path.join(output_dir, "t1_data_coverage.csv"),
            "metadata": os.path.join(output_dir, "t1_backtest_metadata.json"),
        }
        outcomes.to_csv(paths["outcomes"], index=False, encoding="utf-8-sig")
        trade_samples.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
        summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
        by_scenario.to_csv(paths["by_scenario"], index=False, encoding="utf-8-sig")
        by_regime.to_csv(paths["by_regime"], index=False, encoding="utf-8-sig")
        by_layer.to_csv(paths["by_layer"], index=False, encoding="utf-8-sig")
        monthly.to_csv(paths["monthly"], index=False, encoding="utf-8-sig")
        coverage.to_csv(paths["coverage"], index=False, encoding="utf-8-sig")
        with open(paths["metadata"], "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "entry_mode": self.config.entry_mode,
                    "actionable_only": self.config.actionable_only,
                    "entry_model_warning": self._entry_model_warning(),
                    "trade_rule": "Only reversal/trend ETF and stock samples are long-trade eligible.",
                    "diagnostic_rule": "CP, index and industry samples remain diagnostic only.",
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        return {"paths": paths, "outcomes": outcomes, "trades": trade_samples, "summary": summary}

    def _load_detail(self, start_date, end_date):
        if not os.path.exists(self.config.validation_path):
            return pd.DataFrame()
        df = pd.read_csv(self.config.validation_path, encoding="utf-8-sig", dtype={"date": str})
        if "date" in df.columns:
            df["date"] = df["date"].map(self._normalize_date_str)
        if "validation_scope" in df.columns:
            df = df[df["validation_scope"] == "post_close_final"]
        if self.config.actionable_only and "actionable" in df.columns:
            df = df[df["actionable"].astype(str).str.lower() == "true"]
        start_date = self._normalize_date_str(start_date) if start_date else ""
        end_date = self._normalize_date_str(end_date) if end_date else ""
        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]
        df = df.copy()
        df["universe_type"] = df["target_type"].map(TARGET_TYPE_MAP).fillna(df["target_type"])
        return df

    def _build_outcome(self, row):
        date = self._normalize_date_str(row["date"])
        t1_date = self._next_day.get(date)
        universe = str(row.get("universe_type", ""))
        code = self._resolve_code(universe, str(row.get("name", "")), date)
        t_quote = self._lookup_quote(date, universe, code, str(row.get("name", "")))
        t1_quote = self._lookup_quote(t1_date, universe, code, str(row.get("name", ""))) if t1_date else None
        entry_price, entry_source = self._entry_price(date, universe, code, t_quote)
        quote_complete = bool(entry_price and t_quote is not None and t1_quote is not None)
        result = row.to_dict()
        result.update({
            "universe_type": universe,
            "code": code,
            "t1_date": t1_date,
            "entry_mode": self.config.entry_mode,
            "entry_source": entry_source,
            "entry_price": entry_price,
            "quote_complete": quote_complete,
            "trade_eligible": self._trade_eligible(row, universe),
            "trade_role": self._trade_role(row, universe),
            "strategy_layer": self._strategy_layer(row, universe),
        })
        for prefix, quote in (("t", t_quote), ("t1", t1_quote)):
            for field in ("open", "high", "low", "close"):
                result[f"{prefix}_{field}"] = self._number(quote.get(field)) if quote is not None else None
        if quote_complete:
            result.update({
                "t_close_return_pct": self._pct(result["t_close"], entry_price),
                "t1_open_return_pct": self._pct(result["t1_open"], entry_price),
                "t1_close_return_pct": self._pct(result["t1_close"], entry_price),
                "t1_gap_vs_t_close_pct": self._pct(result["t1_open"], result["t_close"]),
                "holding_mae_pct": self._pct(min(result["t_low"], result["t1_low"]), entry_price),
                "holding_mfe_pct": self._pct(max(result["t_high"], result["t1_high"]), entry_price),
            })
        else:
            for field in (
                "t_close_return_pct", "t1_open_return_pct", "t1_close_return_pct",
                "t1_gap_vs_t_close_pct", "holding_mae_pct", "holding_mfe_pct",
            ):
                result[field] = None
        return result

    def _entry_price(self, date, universe, code, daily_quote):
        if self.config.entry_mode == "open_proxy":
            return (
                (self._number(daily_quote.get("open")) if daily_quote is not None else None),
                "daily_open_proxy",
            )
        time_int = {"intraday_0935": 935, "intraday_0945": 945}.get(self.config.entry_mode)
        if time_int is None:
            raise ValueError(f"Unsupported entry mode: {self.config.entry_mode}")
        price = self._intraday_price(date, universe, code, time_int)
        return price, f"snapshot_at_or_after_{time_int}" if price else "intraday_snapshot_missing"

    def _intraday_price(self, date, universe, code, time_int):
        filename = INTRADAY_FILES.get(universe)
        if not filename or not code:
            return None
        path = os.path.join(self.config.store_root, str(date), "intraday", filename)
        if not os.path.exists(path):
            return None
        df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        if df.empty or "time_int" not in df.columns or "last" not in df.columns:
            return None
        df["time_int"] = pd.to_numeric(df["time_int"], errors="coerce")
        rows = df[(df["code"] == code) & (df["time_int"] >= time_int)].sort_values("time_int")
        return self._number(rows.iloc[0]["last"]) if not rows.empty else None

    def _lookup_quote(self, date, universe, code, name):
        if not date or universe == "industry":
            return None
        df = self._load_quotes(date, universe)
        if df.empty:
            return None
        if code and "code" in df.columns:
            rows = df[df["code"] == code]
            if not rows.empty:
                return rows.iloc[0]
        if name and "name" in df.columns:
            rows = df[df["name"] == name]
            if not rows.empty:
                return rows.iloc[0]
        return None

    def _load_quotes(self, date, universe):
        date = self._normalize_date_str(date)
        source = "stocks.csv" if universe == "stock" else "indices.csv"
        key = (str(date), source)
        if key in self._quote_cache:
            return self._quote_cache[key]
        path = os.path.join(self.config.store_root, str(date), source)
        if not os.path.exists(path):
            df = pd.DataFrame()
        else:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
            if "code" in df.columns:
                df["code"] = df["code"].astype(str)
        self._quote_cache[key] = df
        return df

    def _resolve_code(self, universe, name, date):
        if universe in self._name_code:
            return self._name_code[universe].get(name, "")
        if universe != "stock":
            return ""
        df = self._load_quotes(date, universe)
        if df.empty or "name" not in df.columns:
            return ""
        rows = df[df["name"] == name]
        return str(rows.iloc[0]["code"]) if not rows.empty else ""

    @staticmethod
    def _trade_eligible(row, universe):
        return row.get("signal_category") in {"reversal", "trend"} and universe in {"ETF", "stock"}

    @staticmethod
    def _normalize_date_str(value):
        text = str(value or "").strip()
        if not text:
            return ""
        if text.endswith(".0"):
            text = text[:-2]
        if text.isdigit():
            return text
        try:
            number = int(float(text))
            return str(number)
        except Exception:
            return text

    @staticmethod
    def _trade_role(row, universe):
        if row.get("signal_category") == "trap":
            return "avoidance_diagnostic"
        if universe in {"index", "industry"}:
            return "market_diagnostic"
        return "long_candidate"

    @staticmethod
    def _strategy_layer(row, universe):
        if (
            row.get("signal_category") == "reversal"
            and row.get("market_regime") == "risk_off"
            and row.get("scenario") == "REVERSAL_OVERSOLD"
            and universe in {"ETF", "index"}
        ):
            return "high_confidence_reversal"
        if row.get("signal_category") == "reversal":
            return "ordinary_reversal"
        if row.get("signal_category") == "trend":
            return "trend_observation"
        return "avoidance_diagnostic"

    def _load_store_calendar(self):
        if not os.path.isdir(self.config.store_root):
            return []
        return sorted(
            name for name in os.listdir(self.config.store_root)
            if name.isdigit() and len(name) == 8
            and os.path.exists(os.path.join(self.config.store_root, name, "indices.csv"))
        )

    @staticmethod
    def _summarize(samples, dimensions):
        if samples.empty:
            return pd.DataFrame()
        return (
            samples.groupby(dimensions, dropna=False)
            .agg(
                trade_count=("date", "size"),
                trading_days=("date", "nunique"),
                avg_t_close_return_pct=("t_close_return_pct", "mean"),
                avg_t1_open_return_pct=("t1_open_return_pct", "mean"),
                median_t1_open_return_pct=("t1_open_return_pct", "median"),
                t1_open_win_rate=("t1_open_return_pct", lambda values: (values > 0).mean() * 100),
                avg_t1_close_return_pct=("t1_close_return_pct", "mean"),
                t1_close_win_rate=("t1_close_return_pct", lambda values: (values > 0).mean() * 100),
                avg_holding_mae_pct=("holding_mae_pct", "mean"),
                avg_holding_mfe_pct=("holding_mfe_pct", "mean"),
            )
            .reset_index()
            .round(4)
        )

    def _summarize_monthly(self, samples):
        if samples.empty:
            return pd.DataFrame()
        work = samples.copy()
        work["month"] = work["date"].astype(str).str[:6]
        return self._summarize(work, ["month", "signal_category", "universe_type"])

    @staticmethod
    def _coverage(outcomes):
        if outcomes.empty:
            return pd.DataFrame()
        return (
            outcomes.groupby(["signal_category", "universe_type", "trade_role"], dropna=False)
            .agg(
                sample_count=("date", "size"),
                quote_complete_count=("quote_complete", "sum"),
                trade_eligible_count=("trade_eligible", "sum"),
            )
            .reset_index()
        )

    def _entry_model_warning(self):
        if self.config.entry_mode == "open_proxy":
            return "Daily open is an optimistic auction-entry proxy, not a guaranteed fill. Validate with intraday_0935 snapshots."
        return "Intraday mode requires persisted monitor snapshots; missing snapshots are excluded without fallback."

    @staticmethod
    def _number(value):
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _pct(value, base):
        return round((float(value) / float(base) - 1.0) * 100.0, 4) if value and base else None


def run_t1_backtest(start_date=None, end_date=None, entry_mode="open_proxy", actionable_only=True):
    runner = T1BacktestRunner(T1BacktestConfig(entry_mode=entry_mode, actionable_only=actionable_only))
    result = runner.run(start_date=start_date, end_date=end_date)
    print(f"[t1] Trades: {os.path.abspath(result['paths']['trades'])}")
    print(f"[t1] Summary: {os.path.abspath(result['paths']['summary'])}")
    return result
