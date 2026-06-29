"""Smoke tests — verify the SDK contract against a mocked server.

Run: cd sdk/python && pip install -e .[dev] && pytest
"""
from __future__ import annotations
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from autoclaw import AutoclawClient
from autoclaw.models import Experiment, Status


FAKE_STATUS = {
    "running": True,
    "total_experiments": 3,
    "best_score": 0.87,
    "budget_remaining": 142.5,
    "uptime": 200.0,
}

FAKE_EXPERIMENTS = [
    {
        "id": "exp-001", "hypothesis": "lr=2e-5", "params": {"lr": 2e-5},
        "metrics": {"f1_score": 0.82}, "score": 0.82, "status": "completed",
        "timestamp": "2026-06-18T10:00:00Z", "git_hash": "abc1234",
        "duration_seconds": 12.3,
    },
    {
        "id": "exp-002", "hypothesis": "lr=3e-5", "params": {"lr": 3e-5},
        "metrics": {"f1_score": 0.87}, "score": 0.87, "status": "completed",
        "timestamp": "2026-06-18T10:01:00Z", "git_hash": "def5678",
        "duration_seconds": 14.1,
    },
]


class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            self._json(FAKE_STATUS)
        elif self.path == "/api/results":
            self._json(FAKE_EXPERIMENTS)
        elif self.path == "/api/context":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"# MISSION\nTest.\n")
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path in {"/api/start", "/api/stop", "/api/reset"}:
            self._json({"status": self.path.rsplit("/", 1)[-1]})
        elif self.path == "/api/context":
            self._json({"status": "updated"})
        else:
            self.send_response(404); self.end_headers()


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), FakeHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _run(coro):
    return asyncio.run(coro)


def test_status_round_trip(server):
    async def go():
        async with AutoclawClient(server) as c:
            s = await c.status()
            assert isinstance(s, Status)
            assert s.best_score == 0.87
            assert s.running is True
    _run(go())


def test_experiments_typed(server):
    async def go():
        async with AutoclawClient(server) as c:
            exps = await c.experiments()
            assert len(exps) == 2
            assert all(isinstance(e, Experiment) for e in exps)
            assert exps[1].score == 0.87
    _run(go())


def test_best_picks_highest(server):
    async def go():
        async with AutoclawClient(server) as c:
            best = await c.best()
            assert best is not None
            assert best.id == "exp-002"
    _run(go())


def test_context_round_trip(server):
    async def go():
        async with AutoclawClient(server) as c:
            text = await c.get_context()
            assert "MISSION" in text
            await c.set_context("# new\n")
    _run(go())


def test_lifecycle_endpoints(server):
    async def go():
        async with AutoclawClient(server) as c:
            assert (await c.start())["status"] == "start"
            assert (await c.stop())["status"] == "stop"
            assert (await c.reset())["status"] == "reset"
    _run(go())
