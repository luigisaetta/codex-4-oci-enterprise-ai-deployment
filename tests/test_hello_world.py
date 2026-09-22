"""
Author: L. Saetta
Date last modified: 2026-09-22
License: MIT
Description: Verify greeting behavior, validation, and service lifecycle.
"""

import pytest
from fastapi.testclient import TestClient

from demos.hello_world.app import app


def test_greetings_are_independent():
    """Execute the real graph for distinct names, including Unicode."""
    with TestClient(app) as client:
        for name, expected in [("Luigi", "Luigi"), ("  Zoë  ", "Zoë")]:
            response = client.post("/hello", json={"name": name})
            assert response.status_code == 200
            assert response.json() == {"message": f"Hello {expected}"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": 42},
        {"name": ""},
        {"name": " \t "},
        {"name": ["Luigi"]},
    ],
)
def test_invalid_names(payload):
    """Reject missing, non-string, and blank names at the API boundary."""
    with TestClient(app) as client:
        assert client.post("/hello", json=payload).status_code == 422


def test_readiness_tracks_lifecycle():
    """Distinguish liveness from readiness before, during, and after startup."""
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 503
    assert client.post("/hello", json={"name": "Luigi"}).status_code == 503
    with client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}
    assert client.get("/ready").status_code == 503
    assert client.post("/hello", json={"name": "Luigi"}).status_code == 503
