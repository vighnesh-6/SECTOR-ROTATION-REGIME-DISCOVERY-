"""
Database Migration Runner for Neon Serverless PostgreSQL.
Applies pending SQL migrations in deployment/database/migrations/.
"""

import sys
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from deployment.database.connection import get_db_client


def run_migrations():
    client = get_db_client()
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        print("No migration files found.")
        return

    print(f"Connecting to Neon DB ({client.host})...")
    ping_info = client.ping()
    print(f"Connected to {ping_info['db']} ({ping_info['pg_version'].split()[0]} {ping_info['pg_version'].split()[1]}).")

    # Schema migrations table
    client.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name VARCHAR(100) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    applied_rows = client.query("SELECT migration_name FROM schema_migrations;")
    applied = {r["migration_name"] for r in applied_rows}

    for sf in sql_files:
        m_name = sf.name
        if m_name in applied:
            print(f"  [ALREADY APPLIED] {m_name}")
            continue

        print(f"  [APPLYING] {m_name}...")
        with open(sf, "r", encoding="utf-8") as f:
            sql_content = f.read()

        client.execute_batch_script(sql_content)
        client.execute(
            "INSERT INTO schema_migrations (migration_name) VALUES ($1);",
            params=[m_name]
        )
        print(f"  [SUCCESS] {m_name} applied.")

    print("\nAll database migrations complete!")


if __name__ == "__main__":
    run_migrations()
