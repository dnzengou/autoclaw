"""HTTP + WebSocket client for the Autoclaw server."""
from __future__ import annotations
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets

from autoclaw.models import Experiment, Status


class AutoclawClient:
    """Async client for the Autoclaw REST + SSE/WS API.

    Why async: experiments stream in real time; blocking I/O would stall the loop.
    """

    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def __aenter__(self) -> AutoclawClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    # ─── REST ────────────────────────────────────────────────────────────

    async def status(self) -> Status:
        r = await self._http.get("/api/status")
        r.raise_for_status()
        return Status.model_validate(r.json())

    async def experiments(self) -> list[Experiment]:
        r = await self._http.get("/api/results")
        r.raise_for_status()
        return [Experiment.model_validate(e) for e in r.json()]

    async def best(self) -> Experiment | None:
        exps = await self.experiments()
        return max(exps, key=lambda e: e.score) if exps else None

    async def get_context(self) -> str:
        r = await self._http.get("/api/context")
        r.raise_for_status()
        return r.text

    async def set_context(self, content: str) -> None:
        r = await self._http.post("/api/context", content=content)
        r.raise_for_status()

    async def start(self) -> dict[str, Any]:
        r = await self._http.post("/api/start")
        r.raise_for_status()
        return r.json()

    async def stop(self) -> dict[str, Any]:
        r = await self._http.post("/api/stop")
        r.raise_for_status()
        return r.json()

    async def reset(self) -> dict[str, Any]:
        r = await self._http.post("/api/reset")
        r.raise_for_status()
        return r.json()

    # ─── Streaming ───────────────────────────────────────────────────────

    async def stream_experiments(self) -> AsyncIterator[Experiment]:
        """Stream experiments live via SSE. Yields each new result as it lands."""
        async with self._http.stream("GET", "/events") as r:
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "id" in data and "score" in data:
                    yield Experiment.model_validate(data)

    async def stream_ws(self) -> AsyncIterator[dict[str, Any]]:
        """Raw WebSocket stream — yields every event verbatim."""
        ws_url = self.base_url.replace("http", "ws", 1) + "/ws"
        async with websockets.connect(ws_url) as ws:
            async for raw in ws:
                yield json.loads(raw)
