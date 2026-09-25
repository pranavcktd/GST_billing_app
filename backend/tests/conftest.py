import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings, to_sqlalchemy_url

# Tests run against TEST_DATABASE_URL (PostgreSQL, like production) when it is set in .env,
# otherwise against a throw-away SQLite file.
_TEST_URL = get_settings().test_database_url
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["DISABLE_SCHEDULER"] = "1"

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    url = to_sqlalchemy_url(_TEST_URL) if _TEST_URL else f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, connect_args={} if _TEST_URL else {"check_same_thread": False})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
