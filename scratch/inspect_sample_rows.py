import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))
from database.connection import get_db_client

db = get_db_client()

print("--- Last rows in regime_inference_daily ---")
r_inf = db.query("SELECT * FROM regime_inference_daily ORDER BY date DESC LIMIT 2;")
for r in r_inf:
    print(r)

print("\n--- Last rows in portfolio_allocations_daily ---")
p_alloc = db.query("SELECT * FROM portfolio_allocations_daily ORDER BY date DESC LIMIT 4;")
for r in p_alloc:
    print(r)

print("\n--- Last rows in portfolio_simulations_daily ---")
p_sim = db.query("SELECT * FROM portfolio_simulations_daily ORDER BY date DESC LIMIT 4;")
for r in p_sim:
    print(r)

print("\n--- Last rows in benchmark_simulations_daily ---")
b_sim = db.query("SELECT * FROM benchmark_simulations_daily ORDER BY date DESC LIMIT 2;")
for r in b_sim:
    print(r)

