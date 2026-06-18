# autoclaw — Python SDK

```bash
pip install autoclaw
```

## Usage

```python
import asyncio
from autoclaw import AutoclawClient

async def main():
    async with AutoclawClient("http://localhost:8080") as c:
        await c.start()
        async for exp in c.stream_experiments():
            print(f"{exp.id} → {exp.score:.4f} ({exp.status})")
            if exp.score > 0.9:
                await c.stop()
                break

asyncio.run(main())
```

## CLI

```bash
autoclaw status
autoclaw stream
autoclaw context get > context.md
```

## API

| Method | Endpoint |
|--------|----------|
| `status()` | `GET /api/status` |
| `experiments()` | `GET /api/results` |
| `best()` | derived from `experiments()` |
| `get_context()` / `set_context()` | `GET/POST /api/context` |
| `start()` / `stop()` / `reset()` | `POST /api/{start,stop,reset}` |
| `stream_experiments()` | SSE `/events` |
| `stream_ws()` | WebSocket `/ws` |

MIT.
