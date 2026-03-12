# Cost of Running /cost-analysis

Running `/cost-analysis` itself consumes tokens. This page breaks down where those tokens go and how to minimize the cost.

## Estimated cost per run

| Model  | Estimated Cost | Notes                                              |
|--------|---------------|----------------------------------------------------|
| Opus   | $0.50 – $1.50 | Cache writes dominate; grows with session history  |
| Sonnet | $0.25 – $0.60 | Slightly cheaper at same token volume              |
| Haiku  | $0.08 – $0.20 | Cheapest, but may struggle with complex formatting |

**Recommendation**: Switch to Sonnet before running (`/model sonnet`). The skill's formatting and analysis don't require Opus-level reasoning. Switch back to Opus afterward if needed.

## What consumes tokens

Each run involves ~4 model turns: fetch pricing, run the Python script, process results, and generate the report.

### Input / cache tokens (the big cost)

| Component                        | Estimated Size | Notes                                              |
|----------------------------------|---------------|----------------------------------------------------|
| SKILL.md loaded into context     | ~15K tokens   | 680 lines of instructions                          |
| WebFetch pricing (2 calls)       | ~2–3K tokens  | HTML-to-markdown results from pricing sites        |
| Python script JSON output        | ~25–35K tokens| ~104KB for 104 sessions — **scales with session count** |
| history.jsonl (model recs)       | ~5–15K tokens | Read to classify task types for recommendations    |
| Cumulative context across turns  | ~50–100K tokens| Each turn re-sends the growing conversation        |

### Output tokens

| Component                  | Estimated Size |
|----------------------------|---------------|
| Standard formatted report  | ~3–5K tokens  |
| MCP report (with `--mcp`)  | ~4–6K tokens  |

## What drives cost up

1. **Session count** — The Python script outputs one JSON object per session. At 100 sessions that's ~104KB; at 500 sessions it could be 500KB+. Claude processes all of it.
2. **Cache write tokens** — The SKILL.md instructions, Python output, and conversation context all get written to the prompt cache. This is the dominant cost at Opus pricing ($6.25/1M tokens).
3. **Model recommendations** — Reading `history.jsonl` to classify prompts adds tokens proportional to your history size.
4. **`--mcp` flag** — Adds ~20% more output but doesn't significantly increase input cost since the Python script already collects MCP data in every run.

## How to minimize cost

- **Use Sonnet** — `/model sonnet` before running. Saves ~40% vs Opus.
- **Use `--days N`** — Filtering to recent sessions reduces the Python output size. `--days 7` is much cheaper than analyzing all time.
- **Use `--project name`** — Narrowing to one project reduces the result set.
- **Don't run daily** — Weekly or on-demand is sufficient for most users.

## The irony

Running `/cost-analysis` on Opus daily for a month costs $15–45 just to monitor spending. On Sonnet daily, it's $8–18. Weekly on Sonnet is $1–3/month — a reasonable monitoring overhead.
