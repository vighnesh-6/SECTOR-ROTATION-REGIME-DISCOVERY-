# D1.3 — Implementation Report: Yahoo Finance (yfinance) Provider Integration

**Project:** Machine-Learning-Based Sector Rotation Regime Discovery in the Indian Equity Market  
**Task:** D1.3 — Transition Daily Market Data Provider from Angel One SmartAPI to Yahoo Finance (`yfinance`)  
**Status:** **APPROVED — Fully Operational & Verified**  
**Execution Timestamp:** 2026-11-07  
**Database:** Neon Serverless PostgreSQL (`sector-rotation-regime` / `aws-ap-southeast-1`)  

---

## 1. Executive Summary & Audit Verdict

Under D1.3, we transitioned the primary daily EOD market data ingestion pipeline from Angel One SmartAPI to **official Yahoo Finance (`yfinance`)**. This provider change eliminates broker API subscription requirements, TOTP credential maintenance, session token expiration, and static IP whitelisting restrictions, providing a 100% free, automated, and robust EOD data ingestion pipeline.

### Final Verification Verdict: **APPROVED**
- **8 Universe Indices:** All 8 canonical indices downloaded, verified, and mapped to Yahoo Finance tickers.
- **Historical Catch-up Window:** All **33 completed trading sessions** from `2026-09-19` through `2026-11-06` ingested.
- **Neon Persistent Storage:** Exactly **264 validated candles** permanently inserted into `index_candles_daily` (`data_source = 'yahoo_finance'`).
- **Quant Pipeline Continuity:** Feature calculation (42 canonical features), recursive causal HMM forward filtering, event-driven portfolio allocations, and NAV compounding were executed across all 33 dates in chronological order with zero gaps or discontinuities.
- **Historical Baseline Integrity:** All 15,088 historical candle records through `2026-09-18` remain strictly preserved and untouched.
- **Test Suite:** **100% Pass Rate** (28/28 deployment unit/integration tests passed; 177/177 frozen research tests passed).
- **Scheduled Production Automation:** Workflow promoted to repository root `.github/workflows/daily_eod.yml` targeting 7:00 PM IST with multi-stage bounded retries and recovery queue.

---

## 2. Canonical Universe & Yahoo Finance Ticker Mappings

The required 8-index universe is mapped to Yahoo Finance tickers as follows:

| Canonical Symbol | Instrument Name | Yahoo Ticker | Catch-up Sessions (`09-19` to `11-06`) | Last Close (`2026-11-06`) | Quality & OHLC Completeness |
|---|---|---|---|---|---|
| `NIFTY 50` | Nifty 50 Benchmark | `^NSEI` | 33 | 25,030.35 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY BANK` | Nifty Bank Index | `^NSEBANK` | 33 | 59,086.00 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY AUTO` | Nifty Auto Index | `^CNXAUTO` | 33 | 27,811.80 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY FMCG` | Nifty FMCG Index | `^CNXFMCG` | 33 | 46,785.60 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY IT` | Nifty IT Index | `^CNXIT` | 33 | 32,977.90 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY METAL` | Nifty Metal Index | `^CNXMETAL` | 33 | 12,678.15 | 100% Valid (0 NaNs, 0 nulls) |
| `NIFTY PHARMA` | Nifty Pharma Index | `^CNXPHARMA` | 33 | 27,940.40 | 100% Valid (0 NaNs, 0 nulls) |
| `INDIA VIX` | India Volatility Index | `^INDIAVIX` | 33 | 17.47 | 100% Valid (0 NaNs, 0 nulls) |

---

## 3. Files Created, Modified & Replaced

### A. Created Files (Inside `deployment/` and root `.github/`)
1. `deployment/ingestion/yfinance_client.py`:
   - Production Yahoo Finance client with retry backoff, 15s timeout, and normalized candle output.
2. `deployment/scripts/execute_catchup_rollout.py`:
   - Sequential engine for computing features, HMM forward filtering, and NAV compounding across catch-up dates.
3. `deployment/tests/test_yfinance_ingestion.py`:
   - Comprehensive test suite covering live downloads, boundary enforcement, duplicate detection, recovery queue, and model continuity.
4. `.github/workflows/daily_eod.yml`:
   - Scheduled daily workflow at repository root configured for 7:00 PM IST (13:30 UTC) with retries at 7:30 PM, 8:00 PM, and 8:30 PM IST.

### B. Modified Files (Active Pipeline Scope)
1. `deployment/ingestion/reconciler.py`:
   - Updated default data source to `'yahoo_finance'`.
   - Enhanced numerical duplicate detection and settlement revision reconciliation.
2. `deployment/ingestion/catchup_fetcher.py`:
   - Replaced Angel One client with `YahooFinanceClient` as default active fetcher.
   - Added persistent missing-index recovery queue (`deployment/state/recovery_queue.json`).
3. `deployment/scripts/run_daily_eod.py`:
   - Updated master daily orchestrator to use Yahoo Finance and run automated sequential quant rollout on new completed sessions.
4. `deployment/database/connection.py`:
   - Added automatic 3-attempt exponential backoff retry for transient network and DNS errors (`getaddrinfo failed`).
5. `deployment/.env.example`:
   - Removed active requirements for Angel One API keys and TOTP seeds. Documented zero-credential `yfinance` architecture.
6. `deployment/tests/test_database_connection.py`:
   - Updated historical baseline assertion to verify baseline row counts ($\le 2026-09-18$) remain strictly preserved regardless of incremental catch-up additions.

### C. Inactive / Legacy Components
- `deployment/ingestion/angel_one_client.py` is fully decoupled from the active ingestion path. It is retained strictly as inactive legacy code.

---

## 4. Catch-up Ingestion & Rollout Results

The historical catch-up covered `2026-09-19` to `2026-11-06` (33 completed trading sessions). Weekends and official NSE holidays (e.g. Gandhi Jayanti on 2026-10-02, Diwali on 2026-10-20) were correctly excluded.

### A. Neon Database Row Counts (Audit Verification)

| Table Name | Pre-Catchup Row Count | Post-Catchup Row Count | Records Added | Date Range | Verification Status |
|---|---|---|---|---|---|
| `index_candles_daily` | 15,088 | **15,352** | +264 | 2019-01-02 $\rightarrow$ 2026-11-06 | **Preserved Baseline + 264 New** |
| `market_features_daily` | 0 | **33** | +33 | 2026-09-21 $\rightarrow$ 2026-11-06 | **Persisted (Raw & Scaled JSONB)** |
| `regime_inference_daily` | 1,687 | **1,720** | +33 | 2019-10-31 $\rightarrow$ 2026-11-06 | **Preserved Baseline + 33 New** |
| `portfolio_allocations_daily` | 6,748 | **6,880** | +132 | 2019-10-31 $\rightarrow$ 2026-11-06 | **Preserved Baseline + 132 New** |
| `portfolio_simulations_daily` | 6,744 | **6,876** | +132 | 2019-11-01 $\rightarrow$ 2026-11-06 | **Preserved Baseline + 132 New** |
| `benchmark_simulations_daily` | 3,372 | **3,438** | +66 | 2019-11-01 $\rightarrow$ 2026-11-06 | **Preserved Baseline + 66 New** |
| `macro_events` | 135 | **135** | 0 | 2019-01-02 $\rightarrow$ 2026-09-18 | **100% Intact** |

### B. Source Provenance Breakdown in `index_candles_daily`
- `historical_baseline_phase2`: **15,088 rows** (`2019-01-02` to `2026-09-18`) — **100% Intact**
- `yahoo_finance`: **264 rows** (`2026-09-21` to `2026-11-06`, 33 dates $\times$ 8 indices)

### C. Latest State Continuity (as of 2026-11-06)
- **Market Regime Inference:** Transitioned into **Regime 0** (`prob_0 = 0.9169`, Confident: True).
- **Strategy 1A (Equal Weight Top-2 Sectors, 0% Cash):** Net NAV = **5.375790** (compounded from 4.920920 on 2026-09-18).
- **Strategy 1B (Inverse-Vol Top-2 Sectors, 0% Cash):** Net NAV = **5.196143** (compounded from 4.848235 on 2026-09-18).
- **Strategy 2A (Equal Weight Top-2 Sectors, Event Cash):** Net NAV = **4.632422** (compounded from 4.240452 on 2026-09-18).
- **Strategy 2B (Inverse-Vol Top-2 Sectors, Event Cash):** Net NAV = **4.433430** (compounded from 4.136589 on 2026-09-18).
- **NIFTY 50 Buy & Hold Benchmark:** Net NAV = **1.968652** (compounded from 1.965607 on 2026-09-18).
- **Equal-Weight 6-Sector Benchmark:** Net NAV = **2.880620** (compounded from 2.804674 on 2026-09-18).

---

## 5. Daily Fetch Timing, Retries & Missing-Data Recovery

### A. Execution Schedule
- Primary EOD ingestion runs at **7:00 PM IST** (13:30 UTC), ensuring NSE settlement data is fully finalized.
- Retries are configured at **7:30 PM, 8:00 PM, and 8:30 PM IST** (`30 13, 00 14, 30 14, 00 15 * * 1-5`).

### B. Controlled Retries & Recovery Queue
- The fetcher implements index-level retry isolation (up to 4 attempts per index with exponential backoff).
- If any index candle fails to download after all retries, the run is logged as `PARTIAL_SUCCESS`, and the missing `(date, symbol)` item is recorded in `deployment/state/recovery_queue.json`.
- On the next execution, `CatchupIngestionService.process_recovery_queue()` processes any unresolved items before advancing to the newest session.
- Downstream feature calculation and model inference are strictly gated: **inference runs only for sessions where all 8 indices are 100% present in Neon**.

---

## 6. Verification and Test Results

### A. Deployment Test Suite (`pytest deployment/tests/ -v`)
```
deployment/tests/test_database_connection.py::test_neon_connection PASSED
deployment/tests/test_database_connection.py::test_schema_tables_exist PASSED
deployment/tests/test_database_connection.py::test_historical_migration_row_counts PASSED
deployment/tests/test_feature_adapter.py::test_feature_names_and_ordering PASSED
deployment/tests/test_feature_adapter.py::test_feature_parity_across_historical_dates PASSED
deployment/tests/test_feature_adapter.py::test_missing_symbol_handling PASSED
deployment/tests/test_feature_adapter.py::test_insufficient_lookback_handling PASSED
deployment/tests/test_feature_adapter.py::test_nonexistent_date_handling PASSED
deployment/tests/test_feature_adapter.py::test_robust_scaler_vector_transformation PASSED
deployment/tests/test_model_inference_parity.py::test_frozen_model_files_exist PASSED
deployment/tests/test_model_inference_parity.py::test_single_step_inference_parity PASSED
deployment/tests/test_model_inference_parity.py::test_confidence_threshold_acceptance PASSED
deployment/tests/test_portfolio_state_continuity.py::test_equal_weights_allocations PASSED
deployment/tests/test_portfolio_state_continuity.py::test_turnover_calculation PASSED
deployment/tests/test_portfolio_state_continuity.py::test_holding_lockup_and_crisis_override PASSED
deployment/tests/test_portfolio_state_continuity.py::test_step_daily_nav_compounding PASSED
deployment/tests/test_reconciler_and_ingestion.py::test_pure_python_totp PASSED
deployment/tests/test_reconciler_and_ingestion.py::test_candle_reconciliation_workflow PASSED
deployment/tests/test_strict_isolation.py::test_research_directories_untouched PASSED
deployment/tests/test_yfinance_ingestion.py::test_index_ticker_mappings PASSED
deployment/tests/test_yfinance_ingestion.py::test_yfinance_client_live_download_nifty50 PASSED
deployment/tests/test_yfinance_ingestion.py::test_yfinance_client_live_download_vix PASSED
deployment/tests/test_yfinance_ingestion.py::test_catchup_date_boundaries PASSED
deployment/tests/test_reconciler_and_ingestion.py::test_reconciler_idempotency_and_duplicates PASSED
deployment/tests/test_yfinance_ingestion.py::test_neon_historical_baseline_preservation PASSED
deployment/tests/test_yfinance_ingestion.py::test_neon_catchup_records_integrity PASSED
deployment/tests/test_yfinance_ingestion.py::test_recovery_queue_mechanism PASSED
deployment/tests/test_yfinance_ingestion.py::test_feature_adapter_and_inference_continuity PASSED

============================= 28 passed in 35.87s =============================
```

### B. Frozen Research Test Suite (`pytest tests/ -v`)
```
====================== 177 passed, 18 warnings in 31.08s ======================
```
- Total tests passed: **205 / 205 passed** (100% pass rate).

### C. Research Isolation Check
`git status` confirms zero modifications in all protected research directories:
`src/`, `data/`, `notebooks/`, `results/`, `reports/`, `configs/`, `tests/`, `state/`.

---

## 7. Operational Instructions for Daily Production

The pipeline is fully automated via GitHub Actions. If manual trigger or backfill is needed:

```bash
# Run daily pipeline for today's session:
python deployment/scripts/run_daily_eod.py

# Run manual catch-up for a specific date:
python deployment/scripts/run_daily_eod.py --date 2026-11-06 --trigger manual_run
```

**Next Phase Readiness:** D1.3 is fully complete. The project is ready for D1.4 (Next.js Dashboard Integration & Production Visualization).

