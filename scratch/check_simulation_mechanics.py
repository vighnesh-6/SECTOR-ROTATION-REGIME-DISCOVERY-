import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))
from database.connection import get_db_client

db = get_db_client()

print("=== ALLOCATIONS 2026-09-17 ===")
for r in db.query("SELECT variant, date, exec_date, incumbent_regime_after, holding_days_after, rebalance_triggered, w_it, w_pharma FROM portfolio_allocations_daily WHERE date = '2026-09-17' ORDER BY variant;"):
    print(r)

print("=== ALLOCATIONS 2026-09-18 ===")
for r in db.query("SELECT variant, date, exec_date, incumbent_regime_after, holding_days_after, rebalance_triggered, w_it, w_pharma FROM portfolio_allocations_daily WHERE date = '2026-09-18' ORDER BY variant;"):
    print(r)

print("=== SIMULATIONS 2026-09-17 ===")
for r in db.query("SELECT variant, date, rebalance_executed, gross_return, net_return, gross_nav, net_nav, w_post_it, w_post_pharma FROM portfolio_simulations_daily WHERE date = '2026-09-17' ORDER BY variant;"):
    print(r)

print("=== SIMULATIONS 2026-09-18 ===")
for r in db.query("SELECT variant, date, rebalance_executed, gross_return, net_return, gross_nav, net_nav, w_post_it, w_post_pharma FROM portfolio_simulations_daily WHERE date = '2026-09-18' ORDER BY variant;"):
    print(r)

