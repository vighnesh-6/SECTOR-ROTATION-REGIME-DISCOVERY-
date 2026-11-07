"""Event-only Neon transaction adapter; shared database code stays unchanged."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from deployment.database.connection import NeonClient


class EventDatabaseError(RuntimeError):
    pass


class EventDatabase(NeonClient):
    def query(self, sql, params=None, timeout=30):
        try:
            return super().query(sql, params, timeout)
        except Exception:
            raise EventDatabaseError("Event database query failed") from None

    def transaction(self, queries):
        """Serializable batch: retry the entire transaction, never individual inserts.

        Conditional inserts establish predicate reads. PostgreSQL SSI prevents
        concurrent transactions from both inserting the same absent event.
        Unknown network outcomes can safely be replayed through the predicates.
        """
        payload = json.dumps({"queries": queries}).encode()
        request = urllib.request.Request(self.endpoint, data=payload, headers={
            "Content-Type": "application/json",
            "Neon-Connection-String": self.connection_string,
            "Neon-Batch-Isolation-Level": "Serializable",
        })
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=45) as response:
                    result = json.loads(response.read())
                    if not isinstance(result.get("results"), list):
                        raise EventDatabaseError("Invalid Neon batch response")
                    return result["results"]
            except urllib.error.HTTPError as exc:
                try:
                    code = json.loads(exc.read()).get("code")
                except (ValueError, TypeError):
                    code = None
                retry = code in ("40001", "40P01") or exc.code in (429, 500, 502, 503, 504)
                if not retry:
                    raise EventDatabaseError("Event transaction rejected") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            if attempt < 3:
                time.sleep(2 ** attempt)
        raise EventDatabaseError("Event transaction failed after bounded retries")
