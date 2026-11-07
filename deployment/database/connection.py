"""
Neon Serverless PostgreSQL Database Connection Client.
Executes queries via Neon's native HTTP SQL API (zero C-extension dependencies).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def load_env_file(env_path: Optional[Union[str, Path]] = None) -> None:
    """Load key-value pairs from an env file into os.environ if not already present."""
    if env_path is None:
        deployment_dir = Path(__file__).resolve().parent.parent
        possible_files = [
            deployment_dir / ".env.local",
            deployment_dir / ".env",
        ]
        for pf in possible_files:
            if pf.exists():
                env_path = pf
                break

    if env_path and Path(env_path).exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v


class NeonClient:
    """
    HTTP SQL Client for Neon Serverless PostgreSQL.
    Communicates directly with https://{host}/sql over TLS.
    """

    def __init__(self, connection_string: Optional[str] = None):
        load_env_file()
        raw_conn = connection_string or os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_UNPOOLED")
        if not raw_conn:
            raise ValueError(
                "DATABASE_URL is not set. Please populate .env.local or set the environment variable."
            )
        self.connection_string = raw_conn.strip()
        self.host = self._extract_host(self.connection_string)
        self.endpoint = f"https://{self.host}/sql"

    @staticmethod
    def _extract_host(conn_str: str) -> str:
        """Extract database hostname from postgresql connection URL."""
        m = re.search(r"@([^/:]+)", conn_str)
        if m:
            return m.group(1)
        raise ValueError(f"Could not parse host from connection string: {conn_str}")

    def query(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        timeout: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query against Neon and return rows as dictionaries.
        """
        payload_dict: Dict[str, Any] = {"query": sql}
        if params is not None:
            payload_dict["params"] = params

        data = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Neon-Connection-String": self.connection_string,
            },
        )

        last_err = None
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    rows: List[Dict[str, Any]] = result.get("rows", [])
                    return rows
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Neon HTTP SQL Error ({e.code}): {err_body}") from e
            except Exception as e:
                last_err = e
                if attempt < 3:
                    time.sleep(1.0 * attempt)
        raise RuntimeError(f"Neon Connection Error: {last_err}") from last_err

    def execute(self, sql: str, params: Optional[List[Any]] = None, timeout: int = 60) -> int:
        """
        Execute a DDL or DML statement and return the rowCount.
        """
        payload_dict: Dict[str, Any] = {"query": sql}
        if params is not None:
            payload_dict["params"] = params

        data = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Neon-Connection-String": self.connection_string,
            },
        )

        last_err = None
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    rc = result.get("rowCount")
                    return int(rc) if rc is not None else 0
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Neon HTTP SQL Error ({e.code}): {err_body}") from e
            except Exception as e:
                last_err = e
                if attempt < 3:
                    time.sleep(1.0 * attempt)
        raise RuntimeError(f"Neon Connection Error: {last_err}") from last_err

    def execute_batch_script(self, sql_script: str, timeout: int = 120) -> None:
        """
        Execute multiple semicolon-delimited SQL statements in order.
        """
        statements = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
        for stmt in statements:
            self.execute(stmt + ";", timeout=timeout)

    def ping(self) -> Dict[str, Any]:
        """Verify database connectivity."""
        rows = self.query("SELECT 1 as status, current_database() as db, version() as pg_version, current_timestamp as server_time;")
        if rows:
            return rows[0]
        raise RuntimeError("Ping query returned zero rows.")


# Module singleton accessor
def get_db_client() -> NeonClient:
    return NeonClient()
