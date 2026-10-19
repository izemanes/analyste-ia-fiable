"""Accès base : lecture seule, un seul ordre SELECT, accès fichiers désactivé, délai maximum."""
from __future__ import annotations

import os
import threading
from typing import Any

import duckdb

DB_PATH = os.environ.get("WAREHOUSE_PATH", "warehouse.duckdb")
MAX_ROWS = 1000


class QueryRejected(ValueError):
    """Requête refusée avant exécution (pas un SELECT, plusieurs ordres, etc.)."""


def connect(path: str | None = None) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path or DB_PATH, read_only=True, config={"enable_external_access": False})


def run_select(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None,
               timeout_s: float = 20.0) -> list[tuple]:
    """Exécute une requête de lecture et renvoie au plus MAX_ROWS lignes."""
    try:
        stmts = con.extract_statements(sql)
    except duckdb.Error as e:
        raise QueryRejected(f"SQL illisible : {e}") from e
    if len(stmts) != 1 or stmts[0].type != duckdb.StatementType.SELECT:
        raise QueryRejected("Un seul ordre SELECT est autorisé")
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        cur = con.execute(sql, params or [])
        return cur.fetchmany(MAX_ROWS)
    finally:
        timer.cancel()
