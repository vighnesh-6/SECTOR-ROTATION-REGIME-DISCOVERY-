-- ==============================================================================
-- MIGRATION 001: Initial Production Schema for Sector Rotation Regime Discovery
-- Target: PostgreSQL 16+ (Neon Serverless)
-- ==============================================================================

-- 1. EOD Index Candles (8 Series: NIFTY 50, INDIA VIX, and 6 Sectors)
CREATE TABLE IF NOT EXISTS index_candles_daily (
    symbol VARCHAR(30) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(14, 4) NOT NULL,
    high NUMERIC(14, 4) NOT NULL,
    low NUMERIC(14, 4) NOT NULL,
    close NUMERIC(14, 4) NOT NULL,
    adj_close NUMERIC(14, 4),
    volume BIGINT DEFAULT 0,
    data_source VARCHAR(40) DEFAULT 'angel_one_smartapi',
    ingestion_timestamp TIMESTAMPTZ DEFAULT NOW(),
    revision_count INT DEFAULT 0,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_index_candles_date ON index_candles_daily(date DESC);

-- 2. Canonical 42 Features Daily (Leakage-Proof Features)
CREATE TABLE IF NOT EXISTS market_features_daily (
    date DATE PRIMARY KEY,
    period VARCHAR(20) NOT NULL DEFAULT 'live',
    features_raw JSONB,
    features_robust_scaled JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_features_period ON market_features_daily(period);

-- 3. Causal Regime Inference Daily (Gaussian HMM 6 States)
CREATE TABLE IF NOT EXISTS regime_inference_daily (
    date DATE PRIMARY KEY,
    period VARCHAR(20) NOT NULL DEFAULT 'live',
    prob_0 NUMERIC(10, 8) NOT NULL,
    prob_1 NUMERIC(10, 8) NOT NULL,
    prob_2 NUMERIC(10, 8) NOT NULL,
    prob_3 NUMERIC(10, 8) NOT NULL,
    prob_4 NUMERIC(10, 8) NOT NULL,
    prob_5 NUMERIC(10, 8) NOT NULL,
    raw_argmax INT NOT NULL,
    max_probability NUMERIC(10, 8) NOT NULL,
    is_confident BOOLEAN NOT NULL,
    accepted_regime INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_regime_accepted ON regime_inference_daily(accepted_regime);

-- 4. Target Portfolio Allocations & Rebalance Schedules
CREATE TABLE IF NOT EXISTS portfolio_allocations_daily (
    variant VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    exec_date DATE NOT NULL,
    period VARCHAR(20) NOT NULL DEFAULT 'live',
    incumbent_regime_before INT,
    incumbent_regime_after INT,
    holding_days_before INT NOT NULL,
    holding_days_after INT NOT NULL,
    rebalance_triggered BOOLEAN NOT NULL,
    rebalance_bypassed_r3 BOOLEAN NOT NULL DEFAULT FALSE,
    turnover NUMERIC(10, 6) DEFAULT 0.0,
    transaction_cost_rate NUMERIC(8, 6) DEFAULT 0.0015,
    w_nifty50 NUMERIC(8, 6) DEFAULT 0.0,
    w_auto NUMERIC(8, 6) DEFAULT 0.0,
    w_bank NUMERIC(8, 6) DEFAULT 0.0,
    w_fmcg NUMERIC(8, 6) DEFAULT 0.0,
    w_it NUMERIC(8, 6) DEFAULT 0.0,
    w_metal NUMERIC(8, 6) DEFAULT 0.0,
    w_pharma NUMERIC(8, 6) DEFAULT 0.0,
    w_cash NUMERIC(8, 6) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (variant, date)
);
CREATE INDEX IF NOT EXISTS idx_alloc_exec_date ON portfolio_allocations_daily(exec_date);

-- 5. Daily Portfolio Simulation & NAV Histories (Strategies 1A, 1B, 2A, 2B)
CREATE TABLE IF NOT EXISTS portfolio_simulations_daily (
    variant VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    period VARCHAR(20) NOT NULL DEFAULT 'live',
    rebalance_executed BOOLEAN NOT NULL DEFAULT FALSE,
    rebalance_bypassed_r3 BOOLEAN NOT NULL DEFAULT FALSE,
    actual_turnover NUMERIC(10, 6) DEFAULT 0.0,
    nominal_turnover NUMERIC(10, 6) DEFAULT 0.0,
    transaction_cost NUMERIC(10, 6) DEFAULT 0.0,
    gross_return NUMERIC(12, 8) NOT NULL,
    net_return NUMERIC(12, 8) NOT NULL,
    gross_nav NUMERIC(14, 6) NOT NULL,
    net_nav NUMERIC(14, 6) NOT NULL,
    accepted_regime INT NOT NULL,
    w_post_auto NUMERIC(8, 6) DEFAULT 0.0,
    w_post_bank NUMERIC(8, 6) DEFAULT 0.0,
    w_post_fmcg NUMERIC(8, 6) DEFAULT 0.0,
    w_post_it NUMERIC(8, 6) DEFAULT 0.0,
    w_post_metal NUMERIC(8, 6) DEFAULT 0.0,
    w_post_pharma NUMERIC(8, 6) DEFAULT 0.0,
    w_post_cash NUMERIC(8, 6) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (variant, date)
);
CREATE INDEX IF NOT EXISTS idx_sim_variant_date ON portfolio_simulations_daily(variant, date DESC);

-- 6. Benchmark Daily Simulations (NIFTY 50 and Equal-Weight)
CREATE TABLE IF NOT EXISTS benchmark_simulations_daily (
    benchmark_name VARCHAR(40) NOT NULL,
    date DATE NOT NULL,
    period VARCHAR(20) NOT NULL DEFAULT 'live',
    net_return NUMERIC(12, 8) NOT NULL,
    net_nav NUMERIC(14, 6) NOT NULL,
    actual_turnover NUMERIC(10, 6) DEFAULT 0.0,
    transaction_cost NUMERIC(10, 6) DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (benchmark_name, date)
);

-- 7. Macroeconomic Events Calendar
CREATE TABLE IF NOT EXISTS macro_events (
    event_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    actual VARCHAR(50),
    forecast VARCHAR(50),
    previous VARCHAR(50),
    source VARCHAR(50) DEFAULT 'authoritative_historical',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_macro_events_date ON macro_events(date);

-- 8. Pipeline Execution Logs
CREATE TABLE IF NOT EXISTS pipeline_execution_logs (
    log_id SERIAL PRIMARY KEY,
    session_date DATE,
    trigger_type VARCHAR(30) NOT NULL DEFAULT 'daily_cron',
    status VARCHAR(20) NOT NULL,
    step_reached VARCHAR(50) NOT NULL,
    records_processed INT DEFAULT 0,
    duration_ms INT,
    error_message TEXT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_exec_logs_date ON pipeline_execution_logs(created_at DESC);

-- 9. Reconciliation Audit Logs (Track Upstream Settlement Revisions)
CREATE TABLE IF NOT EXISTS reconciliation_audit_logs (
    audit_id SERIAL PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL,
    date DATE NOT NULL,
    field_name VARCHAR(30) NOT NULL,
    old_value NUMERIC(14, 4) NOT NULL,
    new_value NUMERIC(14, 4) NOT NULL,
    abs_delta NUMERIC(14, 4) NOT NULL,
    pct_delta NUMERIC(8, 4) NOT NULL,
    resolution VARCHAR(40) NOT NULL DEFAULT 'reconciled_update',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reconciliation_date ON reconciliation_audit_logs(date DESC);

