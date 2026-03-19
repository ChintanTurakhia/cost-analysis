---
name: analyze
description: Analyze Claude Code token usage and costs from local session data. Use when asking about token usage, API costs, spending patterns, Claude budget, how much sessions cost, which projects are most expensive, any breakdown of Claude Code usage by project/date/model, MCP server overhead, MCP tool result sizes, MCP context bloat, or MCP optimization.
user-invocable: true
tools: Bash, Read
---

# Cost Analysis

Analyzes Claude Code token usage and cost from local session data stored in `~/.claude/projects/`. Reads raw conversation files to extract per-turn model and token data, then computes costs using Anthropic's current pricing — including prompt caching tokens. Outputs a clean summary with totals, trends, and model recommendations. With `--mcp`, provides deep analysis of MCP server overhead including tool result sizes, schema bloat, and optimization recommendations.

## Arguments

`$ARGUMENTS` is an optional filter string. Supported flags:

- `--project <name>` — Filter to sessions whose working directory matches `<name>` (case-insensitive substring match on the project path)
- `--days <N>` — Only include sessions from the last N days (default: all time)
- `--model <name>` — Filter to sessions that used a specific model (e.g., `opus`, `sonnet`, `haiku`)
- `--top <N>` — Show only the top N most expensive sessions (default: 10)
- `--mcp` — Focus analysis on MCP (Model Context Protocol) server overhead: tool result sizes, schema bloat, cost impact, and optimization recommendations
- `--mcp-server <name>` — Filter MCP analysis to a specific server (e.g., `glean-hosted`, `pencil`). Implies `--mcp`

If no arguments are given, analyze all sessions and show a full breakdown.

### Examples

```
/cost-analysis
/cost-analysis --days 30
/cost-analysis --project my-project
/cost-analysis --days 7 --top 5
/cost-analysis --model opus
/cost-analysis --mcp
/cost-analysis --mcp --days 30
/cost-analysis --mcp --mcp-server glean-hosted
```

## Pricing

See `references/pricing.md` for the full pricing table, model ID mapping, and fallback behavior.

## Data Sources

### Primary: `~/.claude/projects/**/*.jsonl`

Authoritative source for token counts and model information. Every Claude Code session writes a `.jsonl` file under `~/.claude/projects/<encoded-project-path>/<session-uuid>.jsonl`. Subagent sessions are nested under `<session-uuid>/subagents/agent-<id>.jsonl`.

Each line is a JSON object. Relevant lines have `"type": "assistant"` with a `message` containing `model`, `usage` (with `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`), and tool_use content blocks. Sum all four token fields across every assistant turn per session.

### Secondary: `~/.claude/usage-data/session-meta/*.json`

Provides human-readable context: `first_prompt`, `start_time`, `duration_minutes`, `tool_counts`. Note: session-meta does **not** store cache tokens — always use project jsonl for cost data.

### Tertiary: `~/.claude/history.jsonl`

Maps user messages to projects and sessions. Used to enrich session data with original prompts and classify task types for model recommendations.

## Known Edge Cases

Review `references/gotchas.md` for known failure modes before running the analysis.

## Steps

### 1. Fetch Live Pricing

Before doing anything else, fetch current pricing from Anthropic's pricing page using `WebFetch`:

- **URL**: `https://platform.claude.com/docs/en/about-claude/pricing`
- **Prompt**: "Extract the model pricing table. For each model, return the model name, Base Input Tokens price, 5m Cache Writes price, Cache Hits & Refreshes price, and Output Tokens price. Return as a structured list."

Parse the fetched results to build a pricing dict. Map human-readable model names to API model IDs using the mapping in `references/pricing.md`.

For each model, extract the four rates (all per 1M tokens):
- **Input** = Base Input Tokens price
- **Output** = Output Tokens price
- **Cache Write** = 5m Cache Writes price
- **Cache Read** = Cache Hits & Refreshes price

If the fetch succeeds and you can extract at least 3 model prices, use the fetched pricing and set `pricing_source = "platform.claude.com (live)"`. Build a JSON object to pass to the Python script via `--pricing-json`.

If the fetch fails, times out, or the page structure is unrecognizable, use the hardcoded fallback rates from `references/pricing.md` and set `pricing_source = "hardcoded fallback"`.

### 2. Parse Arguments

Parse `$ARGUMENTS` for optional filters:
- `--days N` → compute cutoff date as today minus N days
- `--project name` → case-insensitive substring match against `cwd` or `project_path`
- `--model name` → match any model ID containing the substring (e.g., `opus` matches `claude-opus-4-6`)
- `--top N` → limit session table to N rows (still compute full totals)
- `--mcp` → enable MCP-focused analysis sections
- `--mcp-server name` → filter MCP analysis to a specific server name (implies `--mcp`)

### 3. Collect and Aggregate Session Data

Run the Python analysis script at `scripts/analyze.py` using Bash. If live pricing was fetched in Step 1, pass the rates via the `--pricing-json` CLI argument:

```bash
python3 scripts/analyze.py --pricing-json '{"claude-opus-4-6": [5.0, 25.0, 6.25, 0.5], ...}'
```

If live pricing was not available, run without `--pricing-json` to use hardcoded defaults:

```bash
python3 scripts/analyze.py
```

The script outputs JSON with two keys: `sessions` (list of session objects) and `mcp_config` (configured MCP servers). Save stdout and parse it. If the script writes to stderr, surface that warning verbatim. If it fails entirely, report the error and stop.

### 4. Apply Filters

Filter the results list based on parsed arguments:

- **`--days N`**: Keep only entries where `date >= (today - N days)`.
- **`--project name`**: Keep only entries where `name.lower()` is a substring of `cwd.lower()`.
- **`--model name`**: Keep only entries where at least one model in `models` contains `name.lower()`.

### 5. Compute Aggregates

Before computing aggregates, check if `${CLAUDE_PLUGIN_DATA}/run-history.jsonl` exists. If it does, read the last entry and include a comparison line in the report header:

```
vs last run (2026-03-11): $718.38 -> $502.15 (-30%)
```

Only compare if the filters match (same `--days`, `--project`, etc.) to avoid misleading comparisons.

From the filtered results, compute:

**By project** (group by `project` field): total cost, session count, token totals, date range.

**By date** (group by `date` field, YYYY-MM-DD): total cost, session count.

**By model** (aggregate across all sessions): total cost per model, total tokens.

**Grand totals**: total cost, token counts, session count, most expensive session, most active project.

### 6. Present Results

Format the report following the templates in `references/output-format.md`. Read it before generating output.

When `--mcp` is set, read `references/mcp-analysis.md` for the MCP-specific report sections.

### 7. Save Run Summary

After presenting results, append a single JSON line to `${CLAUDE_PLUGIN_DATA}/run-history.jsonl`:

```json
{
  "date": "2026-03-18",
  "total_cost": 718.38,
  "session_count": 36,
  "top_project": "web-dashboard",
  "top_project_cost": 312.45,
  "pricing_source": "platform.claude.com (live)",
  "filters": "--days 7",
  "period_start": "2026-03-11",
  "period_end": "2026-03-18"
}
```

Create the file if it doesn't exist. Use Bash to append.

## Error Handling

- **No session data found**: Report "No Claude Code session data found in ~/.claude/projects/." and stop.
- **Filter matches zero sessions**: Report "No sessions matched the given filters." and list filters applied.
- **Python unavailable**: Fall back to `bash` + `jq`, note cache token extraction may be incomplete.
- **Partial data**: Continue and note "Warning: N files could not be parsed and were skipped."
- **Unknown model IDs**: Apply Opus pricing as conservative default and note it in output.
- **`--mcp` with no MCP sessions**: Show MCP Server Configuration (if servers are configured) and report "No sessions used MCP tools in the selected period." Skip sections B-E.
- **`--mcp-server` with unknown server**: Report "No MCP tools found for server 'X'. Available servers: A, B, C." and list servers actually used.
- **Missing MCP config files**: Still show MCP analysis based on session data — note "MCP config not found — showing usage data only."

## Notes on Data Accuracy

- **Cache tokens dominate costs**: `cache_creation_input_tokens` can be orders of magnitude larger than `input_tokens`. Always sum all four token types.
- **Session-meta vs project jsonl**: session-meta does not store cache token counts. Always read from project jsonl for accurate cost data.
- **Subagent sessions**: Subagent jsonl files under `<session>/subagents/agent-*.jsonl` contribute to the same `sessionId` and are attributed to the parent session's `cwd`.
