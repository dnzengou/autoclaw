"""Thin CLI — talks to a running Autoclaw server."""
from __future__ import annotations
import asyncio
import json
import sys

from autoclaw.client import AutoclawClient


HELP = """\
autoclaw — Python SDK CLI

Usage:
  autoclaw status                       Show server status
  autoclaw experiments                  List all experiments
  autoclaw best                         Best experiment so far
  autoclaw start                        Start the loop
  autoclaw stop                         Stop the loop
  autoclaw reset                        Reset state
  autoclaw stream                       Stream live experiment results (Ctrl-C to exit)
  autoclaw context get                  Print context.md
  autoclaw context set < file.md        Replace context.md from stdin

Env:
  AUTOCLAW_URL                          Server base URL (default http://localhost:8080)
"""


async def _run(argv: list[str]) -> int:
    import os
    url = os.environ.get("AUTOCLAW_URL", "http://localhost:8080")

    if not argv or argv[0] in ("-h", "--help"):
        print(HELP)
        return 0

    cmd, *rest = argv
    async with AutoclawClient(url) as c:
        if cmd == "status":
            print(json.dumps((await c.status()).model_dump(), indent=2))
        elif cmd == "experiments":
            print(json.dumps([e.model_dump() for e in await c.experiments()], indent=2))
        elif cmd == "best":
            b = await c.best()
            print(json.dumps(b.model_dump() if b else None, indent=2))
        elif cmd == "start":
            print(json.dumps(await c.start()))
        elif cmd == "stop":
            print(json.dumps(await c.stop()))
        elif cmd == "reset":
            print(json.dumps(await c.reset()))
        elif cmd == "stream":
            async for e in c.stream_experiments():
                print(json.dumps(e.model_dump()))
        elif cmd == "context" and rest:
            if rest[0] == "get":
                print(await c.get_context())
            elif rest[0] == "set":
                await c.set_context(sys.stdin.read())
                print("ok")
            else:
                print(HELP)
                return 2
        else:
            print(HELP)
            return 2
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
