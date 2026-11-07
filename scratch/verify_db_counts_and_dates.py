import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))
from database.connection import get_db_client

db = get_db_client()

tables = [
    'index_candles_daily',
    'market_features_daily',
    'regime_inference_daily',
    'portfolio_allocations_daily',
    'portfolio_simulations_daily',
    'benchmark_simulations_daily',
    'macro_events'
]

print("=== VERIFYING NEON DATABASE ROW COUNTS AND DATE RANGES ===")
for t in tables:
    c = db.query(f"SELECT COUNT(*) as c FROM {t};")[0]["c"]
    if t != 'macro_events':
        d = db.query(f"SELECT MIN(date)::text as min_d, MAX(date)::text as max_d FROM {t};")[0]
        print(f"{t:30s}: {int(c):6d} rows | Min: {d['min_d']} | Max: {d['max_d']}")
    else:
        print(f"{t:30s}: {int(c):6d} rows")

print("\n=== VERIFYING SOURCE PROVENANCE IN index_candles_daily ===")
for r in db.query("SELECT data_source, COUNT(*) as c, MIN(date)::text as min_d, MAX(date)::text as max_d FROM index_candles_daily GROUP BY data_source ORDER BY data_source;"):
    print(f"  Source: {r['data_source']:25s} | Count: {int(r['c']):6d} | Range: {r['min_d']} -> {r['max_d']}")

print("\n=== VERIFYING PERIODS IN regime_inference_daily ===")
for r in db.query("SELECT period, COUNT(*) as c, MIN(date)::text as min_d, MAX(date)::text as max_d FROM regime_inference_daily GROUP BY period ORDER BY min_d;"):
    print(f"  Period: {r['period']:12s} | Count: {int(r['c']):5d} | Range: {r['min_d']} -> {r['max_d']}")

print("\n=== LATEST 3 INFERENCE ROWS ===")
for r in db.query("SELECT date, prob_0, prob_1, prob_2, prob_3, prob_4, prob_5, accepted_regime FROM regime_inference_daily ORDER BY date DESC LIMIT 3;"):
    print(r)

print("\n=== LATEST 4 SIMULATION ROWS ===")
for r in db.query("SELECT variant, date, rebalance_executed, gross_return, net_return, net_nav, accepted_regime FROM portfolio_simulations_daily ORDER BY date DESC, variant ASC LIMIT 4;"):
    print(r)
