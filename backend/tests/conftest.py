import os
import shutil
import tempfile
from pathlib import Path

TEST_DB = (Path(tempfile.gettempdir()) / "weam_auth_child_test.db").resolve()
TEST_STORAGE = (Path(tempfile.gettempdir()) / "weam_report_test_storage").resolve()
if TEST_DB.exists():
    TEST_DB.unlink()
if TEST_STORAGE.exists():
    shutil.rmtree(TEST_STORAGE)

os.environ["WEAM_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["WEAM_JWT_SECRET"] = "test-only-secret-32-bytes-minimum-123456"
os.environ["WEAM_CREATE_TABLES_ON_STARTUP"] = "false"
os.environ["WEAM_STORAGE_ROOT"] = TEST_STORAGE.as_posix()
os.environ["WEAM_MAX_REPORT_UPLOAD_MB"] = "2"
os.environ["WEAM_MAX_VOICE_UPLOAD_MB"] = "2"
os.environ["WEAM_AI_PROVIDER"] = "mock"
os.environ["WEAM_STT_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if TEST_STORAGE.exists():
        shutil.rmtree(TEST_STORAGE)
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_STORAGE.exists():
        shutil.rmtree(TEST_STORAGE)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()
    if TEST_STORAGE.exists():
        shutil.rmtree(TEST_STORAGE)
