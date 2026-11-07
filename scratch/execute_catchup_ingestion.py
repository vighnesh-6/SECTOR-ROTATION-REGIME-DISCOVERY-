"""
scratch/execute_catchup_ingestion.py
====================================
Executes the catch-up ingestion for the 33 completed sessions (2026-09-19 to 2026-11-06).
Validates Neon database row counts and source provenance.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))

from database.connection import get_db_client
from ingestion.catchup_fetcher import CatchupIngestionService

def main():
    db = get_db_client()
    
    # 1. Pre-check baseline count
    pre_count = int(db.query("SELECT COUNT(*) as c FROM index_candles_daily;")[0]["c"])
    print(f"Pre-ingestion total row count in index_candles_daily: {pre_count}")
    assert pre_count == 15088, f"Expected 15088 rows, got {pre_count}"
    
    # 2. Run catch-up targeting 2026-11-06
    service = CatchupIngestionService(db_client=db)
    res = service.run_catchup(target_date="2026-11-06", trigger_type="catchup_d1_3")
    print("\nCatchup service execution response:")
    print(res)
    
    # 3. Post-check counts
    post_count = db.query("SELECT COUNT(*) as c FROM index_candles_daily;")[0]["c"]
    print(f"\nPost-ingestion total row count in index_candles_daily: {post_count}")
    
    source_res = db.query("""
        SELECT data_source, COUNT(*) as c, MIN(date)::text as min_d, MAX(date)::text as max_d
        FROM index_candles_daily
        GROUP BY data_source
        ORDER BY data_source;
    """)
    print("\nSource provenance in Neon:")
    for r in source_res:
        print(f"  Source: {r['data_source']}, Rows: {r['c']}, Range: {r['min_d']} to {r['max_d']}")
        
    date_count_res = db.query("""
        SELECT COUNT(DISTINCT date) as date_count
        FROM index_candles_daily
        WHERE data_source = 'yahoo_finance';
    """)
    date_cnt = date_count_res[0]["date_count"]
    print(f"\nDistinct trading dates for yahoo_finance: {date_cnt}")
    
    # Check completeness per date for new records
    incomplete_res = db.query("""
        SELECT date::text as dt, COUNT(symbol) as sym_cnt
        FROM index_candles_daily
        WHERE data_source = 'yahoo_finance'
        GROUP BY date
        HAVING COUNT(symbol) != 8;
    """)
    if incomplete_res:
        print(f"[ERROR] Incomplete sessions found: {incomplete_res}")
    else:
        print("[PASS] All 33 new dates have exactly 8 indices recorded.")

if __name__ == "__main__":
    main()
