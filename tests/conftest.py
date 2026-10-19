import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("WAREHOUSE_PATH", str(ROOT / "warehouse.duckdb"))


@pytest.fixture(scope="session")
def con():
    from aia import db

    if not Path(os.environ["WAREHOUSE_PATH"]).exists():
        pytest.skip("warehouse.duckdb absent : lancer `make data dbt` d'abord")
    c = db.connect()
    yield c
    c.close()
