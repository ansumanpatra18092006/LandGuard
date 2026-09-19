import os

import pytest

from app.db.verify_postgres import verify_postgres


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not configured; PostgreSQL runtime verification unavailable")
def test_postgres_crud_seed_analytics_and_postgis():
    assert verify_postgres(os.environ["TEST_POSTGRES_URL"])["status"] == "passed"
