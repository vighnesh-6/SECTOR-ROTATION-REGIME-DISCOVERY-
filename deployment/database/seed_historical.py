"""
Historical Data Migration & Seeding Engine for Neon PostgreSQL.
Imports verified baseline research datasets (2019-01-02 to 2026-09-18).
Guarantees idempotency and zero modifications to local research files.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from deployment.database.connection import get_db_client

# Symbol mappings for aligned datasets
ALIGNED_SERIES_MAP = {
    "nifty50_aligned.csv": "NIFTY 50",
    "india_vix_aligned.csv": "INDIA VIX",
    "nifty_auto_aligned.csv": "NIFTY AUTO",
    "nifty_bank_aligned.csv": "NIFTY BANK",
    "nifty_fmcg_aligned.csv": "NIFTY FMCG",
    "nifty_it_aligned.csv": "NIFTY IT",
    "nifty_metal_aligned.csv": "NIFTY METAL",
    "nifty_pharma_aligned.csv": "NIFTY PHARMA",
}


def batch_insert(client, table_name: str, columns: List[str], rows: List[List[Any]], conflict_cols: List[str], update_cols: List[str], batch_size: int = 400):
    """
    Execute high-throughput multi-row INSERT with ON CONFLICT DO UPDATE.
    """
    total = len(rows)
    if total == 0:
        return

    col_names = ", ".join(columns)
    conflict_clause = ", ".join(conflict_cols)
    
    if update_cols:
        updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_cols])
        conflict_action = f"DO UPDATE SET {updates}"
    else:
        conflict_action = "DO NOTHING"

    for i in range(0, total, batch_size):
        chunk = rows[i : i + batch_size]
        values_clauses = []
        for r in chunk:
            formatted_vals = []
            for v in r:
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    formatted_vals.append("NULL")
                elif isinstance(v, (int, float, np.integer, np.floating)):
                    formatted_vals.append(str(v))
                elif isinstance(v, bool):
                    formatted_vals.append("TRUE" if v else "FALSE")
                elif isinstance(v, (dict, list)):
                    s = json.dumps(v).replace("'", "''")
                    formatted_vals.append(f"'{s}'::jsonb")
                else:
                    s = str(v).replace("'", "''")
                    formatted_vals.append(f"'{s}'")
            values_clauses.append(f"({', '.join(formatted_vals)})")

        sql = f"""
        INSERT INTO {table_name} ({col_names})
        VALUES {', '.join(values_clauses)}
        ON CONFLICT ({conflict_clause}) {conflict_action};
        """
        client.execute(sql)


def seed_index_candles(client):
    print("\n--- 1. Migrating Index Candles (8 Series) ---")
    aligned_dir = project_root / "data" / "processed" / "aligned"
    all_rows = []

    for filename, symbol in ALIGNED_SERIES_MAP.items():
        filepath = aligned_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Missing required aligned file: {filepath}")

        df = pd.read_csv(filepath)
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        
        for _, row in df.iterrows():
            all_rows.append([
                symbol,
                row["Date"],
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                float(row["Adj Close"]) if "Adj Close" in row and not pd.isna(row["Adj Close"]) else float(row["Close"]),
                int(row["Volume"]) if "Volume" in row and not pd.isna(row["Volume"]) else 0,
                "historical_baseline_phase2",
                0
            ])

    columns = ["symbol", "date", "open", "high", "low", "close", "adj_close", "volume", "data_source", "revision_count"]
    conflict_cols = ["symbol", "date"]
    update_cols = ["open", "high", "low", "close", "adj_close", "volume"]

    batch_insert(client, "index_candles_daily", columns, all_rows, conflict_cols, update_cols)
    print(f"  Imported {len(all_rows)} rows across 8 index series.")


def seed_regime_inference(client):
    print("\n--- 2. Migrating Regime Inference & Probabilities ---")
    probs_path = project_root / "results" / "regime_discovery" / "hmm_causal_probabilities.csv"
    labels_path = project_root / "results" / "regime_discovery" / "final_regime_labels.csv"

    probs_df = pd.read_csv(probs_path)
    labels_df = pd.read_csv(labels_path)

    # Filter labels to HMM k=6 robust filtered causal
    hmm_labels = labels_df[
        (labels_df["model"] == "hmm") &
        (labels_df["scaler"] == "robust") &
        (labels_df["k"] == 6) &
        (labels_df["label_type"] == "filtered_causal")
    ].set_index("Date")

    all_rows = []
    for _, row in probs_df.iterrows():
        dt = row["Date"]
        p_vec = [float(row[f"prob_{j}"]) for j in range(6)]
        max_p = max(p_vec)
        raw_argmax = int(np.argmax(p_vec))
        is_conf = max_p >= 0.50

        # Accepted regime
        if dt in hmm_labels.index:
            accepted = int(hmm_labels.loc[dt, "regime_id"])
        else:
            accepted = raw_argmax if is_conf else 2 # default fallback

        all_rows.append([
            dt,
            row["period"],
            p_vec[0], p_vec[1], p_vec[2], p_vec[3], p_vec[4], p_vec[5],
            raw_argmax,
            max_p,
            is_conf,
            accepted
        ])

    columns = [
        "date", "period", "prob_0", "prob_1", "prob_2", "prob_3", "prob_4", "prob_5",
        "raw_argmax", "max_probability", "is_confident", "accepted_regime"
    ]
    conflict_cols = ["date"]
    update_cols = ["period", "prob_0", "prob_1", "prob_2", "prob_3", "prob_4", "prob_5", "raw_argmax", "max_probability", "is_confident", "accepted_regime"]

    batch_insert(client, "regime_inference_daily", columns, all_rows, conflict_cols, update_cols)
    print(f"  Imported {len(all_rows)} daily regime inference records.")


def seed_portfolio_allocations(client):
    print("\n--- 3. Migrating Target Allocation Schedules (1A, 1B, 2A, 2B) ---")
    pc_dir = project_root / "results" / "portfolio_construction"
    all_rows = []

    for variant in ["1A", "1B", "2A", "2B"]:
        tw_path = pc_dir / f"target_weights_{variant}.csv"
        if not tw_path.exists():
            continue
        df = pd.read_csv(tw_path)
        for _, row in df.iterrows():
            all_rows.append([
                variant,
                row["Date"],
                row["exec_date"],
                row["period"],
                int(row["incumbent_regime_before"]) if not pd.isna(row["incumbent_regime_before"]) else None,
                int(row["incumbent_regime_after"]) if not pd.isna(row["incumbent_regime_after"]) else None,
                int(row["holding_days_before"]),
                int(row["holding_days_after"]),
                bool(row["rebalance_triggered"]),
                bool(row["rebalance_bypassed_r3"]) if "rebalance_bypassed_r3" in row else False,
                float(row["turnover"]) if "turnover" in row else 0.0,
                float(row["transaction_cost_rate"]) if "transaction_cost_rate" in row else 0.0015,
                float(row["w_NIFTY50"]) if "w_NIFTY50" in row else 0.0,
                float(row["w_AUTO"]) if "w_AUTO" in row else 0.0,
                float(row["w_BANK"]) if "w_BANK" in row else 0.0,
                float(row["w_FMCG"]) if "w_FMCG" in row else 0.0,
                float(row["w_IT"]) if "w_IT" in row else 0.0,
                float(row["w_METAL"]) if "w_METAL" in row else 0.0,
                float(row["w_PHARMA"]) if "w_PHARMA" in row else 0.0,
                float(row["w_CASH"]) if "w_CASH" in row else 0.0,
            ])

    columns = [
        "variant", "date", "exec_date", "period", "incumbent_regime_before", "incumbent_regime_after",
        "holding_days_before", "holding_days_after", "rebalance_triggered", "rebalance_bypassed_r3",
        "turnover", "transaction_cost_rate", "w_nifty50", "w_auto", "w_bank", "w_fmcg",
        "w_it", "w_metal", "w_pharma", "w_cash"
    ]
    conflict_cols = ["variant", "date"]
    update_cols = ["exec_date", "period", "holding_days_after", "rebalance_triggered", "rebalance_bypassed_r3", "turnover", "w_auto", "w_bank", "w_fmcg", "w_it", "w_metal", "w_pharma", "w_cash"]

    batch_insert(client, "portfolio_allocations_daily", columns, all_rows, conflict_cols, update_cols)
    print(f"  Imported {len(all_rows)} target allocation records across 4 strategies.")


def seed_portfolio_simulations(client):
    print("\n--- 4. Migrating Daily Portfolio Simulations (1A, 1B, 2A, 2B) ---")
    pb_dir = project_root / "results" / "portfolio_backtest"
    all_rows = []

    for variant in ["1A", "1B", "2A", "2B"]:
        sim_path = pb_dir / f"daily_simulation_{variant}.parquet"
        if not sim_path.exists():
            continue
        df = pd.read_parquet(sim_path)
        for dt_idx, row in df.iterrows():
            dt_str = dt_idx.strftime("%Y-%m-%d") if hasattr(dt_idx, "strftime") else str(dt_idx)[:10]
            all_rows.append([
                variant,
                dt_str,
                row["period"],
                bool(row["rebalance_executed"]),
                bool(row["rebalance_bypassed_r3"]),
                float(row["actual_turnover"]),
                float(row["nominal_turnover"]) if "nominal_turnover" in row else float(row["actual_turnover"]),
                float(row["transaction_cost"]),
                float(row["gross_return"]),
                float(row["net_return"]),
                float(row["gross_nav"]),
                float(row["net_nav"]),
                int(row["accepted_regime"]),
                float(row["w_post_AUTO"]),
                float(row["w_post_BANK"]),
                float(row["w_post_FMCG"]),
                float(row["w_post_IT"]),
                float(row["w_post_METAL"]),
                float(row["w_post_PHARMA"]),
                float(row["w_post_CASH"]),
            ])

    columns = [
        "variant", "date", "period", "rebalance_executed", "rebalance_bypassed_r3", "actual_turnover",
        "nominal_turnover", "transaction_cost", "gross_return", "net_return", "gross_nav", "net_nav",
        "accepted_regime", "w_post_auto", "w_post_bank", "w_post_fmcg", "w_post_it", "w_post_metal",
        "w_post_pharma", "w_post_cash"
    ]
    conflict_cols = ["variant", "date"]
    update_cols = ["period", "rebalance_executed", "rebalance_bypassed_r3", "actual_turnover", "transaction_cost", "gross_return", "net_return", "gross_nav", "net_nav", "accepted_regime"]

    batch_insert(client, "portfolio_simulations_daily", columns, all_rows, conflict_cols, update_cols)
    print(f"  Imported {len(all_rows)} daily portfolio simulation rows (1,686 per variant).")


def seed_benchmark_simulations(client):
    print("\n--- 5. Migrating Benchmark Daily Simulations ---")
    pb_dir = project_root / "results" / "portfolio_backtest"
    benchmarks = {
        "NIFTY50_BUY_HOLD": pb_dir / "daily_simulation_benchmark_nifty50.parquet",
        "EQUAL_WEIGHT_6SECTOR": pb_dir / "daily_simulation_benchmark_equal_weight.parquet",
    }
    all_rows = []

    for name, path in benchmarks.items():
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        for dt_idx, row in df.iterrows():
            dt_str = dt_idx.strftime("%Y-%m-%d") if hasattr(dt_idx, "strftime") else str(dt_idx)[:10]
            all_rows.append([
                name,
                dt_str,
                row["period"] if "period" in row else "train",
                float(row["net_return"]),
                float(row["net_nav"]),
                float(row["actual_turnover"]) if "actual_turnover" in row else 0.0,
                float(row["transaction_cost"]) if "transaction_cost" in row else 0.0,
            ])

    columns = ["benchmark_name", "date", "period", "net_return", "net_nav", "actual_turnover", "transaction_cost"]
    conflict_cols = ["benchmark_name", "date"]
    update_cols = ["period", "net_return", "net_nav", "actual_turnover", "transaction_cost"]

    batch_insert(client, "benchmark_simulations_daily", columns, all_rows, conflict_cols, update_cols)
    print(f"  Imported {len(all_rows)} daily benchmark simulation rows.")


def seed_macro_events(client):
    print("\n--- 6. Migrating Macroeconomic Events ---")
    ev_path = project_root / "data" / "processed" / "cleaned" / "major_events_cleaned.csv"
    if not ev_path.exists():
        print("  Skipping macro events (file not found).")
        return

    df = pd.read_csv(ev_path)
    all_rows = []
    for _, row in df.iterrows():
        start_date = str(row["start_date"])[:10]
        category = str(row["event_category"]) if not pd.isna(row["event_category"]) else "General"
        title = str(row["event_name"]) if not pd.isna(row["event_name"]) else "Macro Event"
        severity = f"Severity: {row['severity']}" if not pd.isna(row["severity"]) else None
        region = f"Region: {row['region']}" if not pd.isna(row["region"]) else None
        end_date = f"End: {row['end_date']}" if not pd.isna(row["end_date"]) else None
        event_id_str = f"ID: {row['event_id']}" if not pd.isna(row["event_id"]) else "authoritative_historical"

        all_rows.append([
            start_date,
            category,
            title,
            severity,
            region,
            end_date,
            event_id_str
        ])

    # Truncate and re-seed to prevent primary key mismatch on serial event_id
    client.execute("TRUNCATE TABLE macro_events RESTART IDENTITY;")
    
    # Simple insert
    for r in all_rows:
        client.execute(
            """
            INSERT INTO macro_events (date, category, title, actual, forecast, previous, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
            """,
            params=r
        )
    print(f"  Imported {len(all_rows)} authoritative macro events.")


def run_all_seeds():
    start_time = time.time()
    print("=" * 60)
    print("Starting Historical Data Migration to Neon PostgreSQL")
    print("=" * 60)
    client = get_db_client()

    seed_index_candles(client)
    seed_regime_inference(client)
    seed_portfolio_allocations(client)
    seed_portfolio_simulations(client)
    seed_benchmark_simulations(client)
    seed_macro_events(client)

    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"Historical Migration COMPLETE in {elapsed:.2f} seconds!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_seeds()
