import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))
from database.connection import get_db_client

db = get_db_client()
for tbl in [
    'regime_inference_daily',
    'portfolio_allocations_daily',
    'portfolio_simulations_daily',
    'benchmark_simulations_daily',
    'market_features_daily'
]:
    cols = db.query(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position;")
    print(f"=== {tbl} ===")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")

tbl = 'pipeline_execution_logs'
cols = db.query(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position;")
print(f"=== {tbl} ===")
for c in cols:
    print(f"  {c['column_name']} ({c['data_type']})")
