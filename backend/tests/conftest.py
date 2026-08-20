import os
import tempfile
from pathlib import Path

# Cross-platform SQLite path for tests (Windows/macOS/Linux).
TEST_DB = (Path(tempfile.gettempdir()) / "weam_auth_child_test.db").resolve()
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["WEAM_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["WEAM_JWT_SECRET"] = "test-only-secret-32-bytes-minimum-123456"
os.environ["WEAM_CREATE_TABLES_ON_STARTUP"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()
