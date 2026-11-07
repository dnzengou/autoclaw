# prompt-tune

See the [examples README](../README.md) for the common flow and contract.

## Run
```bash
cd examples/prompt-tune
autoclaw server --work-dir . --budget 300 --no-dashboard &
curl -X POST localhost:8080/api/start
```

Read [`context.md`](./context.md) for the mission. Edit it to retarget the
loop (different dataset, different constraints, different seed hypotheses).
