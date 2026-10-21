import random

import pytest

from app.db import connect
from app.railway.seed import seed
from app.railway.service import RailwayService
from app.telemetry import Telemetry


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    monkeypatch.setenv("TODAY", "2026-10-21")  # a Wednesday


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    seed(c)
    yield c
    c.close()


@pytest.fixture
def svc(conn):
    return RailwayService(conn, rng=random.Random(42))


@pytest.fixture
def telemetry(conn):
    return Telemetry(conn)
