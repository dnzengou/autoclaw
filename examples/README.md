# Autoclaw examples

Three self-contained problems, each a `context.md` + `train.py` + `rubric.json`
you can drive from a Clone. Each one shows a different thing the loop is
good at. Every example runs in minutes on a laptop.

| Example | What the loop learns | API key needed? | Headroom |
|---|---|---|---|
| **[regex-evolve](./regex-evolve)** | A regex that extracts phone numbers from noisy text without matching dates, SKUs, IPs or credit cards. | No — pure Python `re`. | F1 ≈ 0.77 → 1.00 |
| **[prompt-tune](./prompt-tune)** | A spam-classifier system prompt that beats the one-liner baseline. | Yes (Claude, OpenAI, or DeepSeek). Runs with a heuristic without one. | F1 ≈ 0.43 → ≥ 0.95 |
| **[sql-speedup](./sql-speedup)** | A SQLite query rewrite + indexes that matches the baseline rows and runs faster. | No — SQLite is stdlib. | 1.0× → ≈ 1.8× |

## How to run one

Install the server (one-time), then point it at the example's folder:

```bash
go install github.com/dnzengou/autoclaw@latest    # or: docker run ghcr.io/dnzengou/autoclaw:latest
export ANTHROPIC_API_KEY=sk-ant-...               # optional for regex-evolve / sql-speedup
cd examples/prompt-tune
autoclaw server --work-dir . --budget 300 --no-dashboard &
curl -X POST localhost:8080/api/start
open http://localhost:8080                        # dashboard: Live → Evolution (key 4)
```

The server writes experiments into `experiments/` inside the working directory,
scores each against `rubric.json`, and commits the ones that improve. Open the
Evolution tab to watch which strategy genome is picking up fitness; export the
proven ones as a skill pack when you want to carry them into another project:

```bash
curl -s localhost:8080/api/evo/skills > hyperparameters.pack.json
cd ../sql-speedup
curl -X POST -d @../prompt-tune/hyperparameters.pack.json localhost:8080/api/evo/skills
```

## How to adapt one

A new experiment is three files. The contract is tiny:

- `context.md` — human-written. States the MISSION, the PARAMETERS
  `train.py` accepts, the CONSTRAINTS, and any seed HYPOTHESES.
- `train.py` — reads the hypothesis's parameters as CLI flags (underscores
  become dashes: `batch_size` → `--batch-size`), does the work, and prints
  one line of JSON metrics on stdout.
- `rubric.json` — `primary_metric`, `higher_is_better`, `weights`, and
  the `fail_threshold` below which a run is reverted.

That's it. The loop handles LLM calls, scoring, git commits, strategy
selection (EvoMetaClaw), and reverts.

## For AI agents

Every example is MCP-driveable. Once the server is running:

```bash
claude mcp add autoclaw -- autoclaw mcp
```

From Claude Code, Cursor, or any MCP client you can read `context.md`,
propose an edit, start a run, watch results, and export the winning
strategy without leaving the chat.
