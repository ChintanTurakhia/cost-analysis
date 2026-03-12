# cost-analysis — Claude Code Plugin

Analyze your Claude Code token usage and costs from local session data. See exactly what you spent, by project, model, and day — including which sessions didn't need Opus and how much MCP servers are costing you.

## What it does

- **Project breakdown** — cost, tokens, session count per project
- **Top sessions** — most expensive sessions with the prompts that triggered them
- **Model breakdown** — spend per model (Opus vs Sonnet vs Haiku)
- **Daily spend** — ASCII bar chart of spend over time
- **Token cost breakdown** — shows how much cache write vs cache read vs output vs input tokens cost (cache write is usually the dominant driver)
- **Model recommendations** — classifies each project's work type and tells you which ones didn't need Opus, with estimated savings
- **MCP analysis** (`--mcp`) — deep dive into MCP server overhead: tool result sizes, schema bloat, cost impact, and optimization recommendations

## Installation

### Option 1: Plugin dir flag (no install needed)

```bash
git clone https://github.com/ChintanTurakhia/cost-analysis
claude --plugin-dir ./cost-analysis
```

Then run `/cost-analysis:cost-analysis` in any session.

### Option 2: Install via marketplace

```
/plugin install https://github.com/ChintanTurakhia/cost-analysis
```

## Usage

Basic cost analysis:

```
/cost-analysis                                   # all sessions, full breakdown
/cost-analysis --days 7                          # last 7 days only
/cost-analysis --days 30                         # last 30 days
/cost-analysis --project my-project              # filter to one project
/cost-analysis --days 7 --top 5                  # last week, top 5 sessions
/cost-analysis --model opus                      # only Opus sessions
```

MCP overhead analysis:

```
/cost-analysis --mcp                             # full MCP overhead report
/cost-analysis --mcp --days 30                   # MCP analysis for last 30 days
/cost-analysis --mcp --mcp-server glean-hosted   # filter to one MCP server
```

## Flags

| Flag                | Description                                                | Default      |
| ------------------- | ---------------------------------------------------------- | ------------ |
| `--days N`          | Only include sessions from the last N days                 | all time     |
| `--project name`    | Filter to sessions matching this project name              | all projects |
| `--model name`      | Filter to sessions that used this model                    | all models   |
| `--top N`           | Show only the top N most expensive sessions                | 10           |
| `--mcp`             | Show MCP server overhead analysis                          | off          |
| `--mcp-server name` | Filter MCP analysis to a specific server (implies `--mcp`) | all servers  |

## MCP analysis

MCP (Model Context Protocol) servers are a significant hidden cost driver. They load full tool schemas into context on session start (~15K+ tokens per server), and their tool results are often 100-300x larger than native tool results.

The `--mcp` flag reveals:

- **Server configuration** — which MCP servers are configured vs actually used
- **Tool usage breakdown** — call counts and result sizes per MCP tool, grouped by server
- **Context overhead** — schema overhead comparison (MCP vs non-MCP sessions), result size multipliers, cost impact
- **Optimization recommendations** — actionable suggestions like removing unused servers, reducing result sizes, or isolating MCP work into dedicated sessions

Even without `--mcp`, the standard report will show a brief "MCP USAGE DETECTED" summary if any sessions used MCP tools, with a pointer to run `--mcp` for details.

## How it works

Reads directly from `~/.claude/projects/**/*.jsonl` — the same session files Claude Code writes locally. Fetches live pricing from [llmpricecheck.com](https://llmpricecheck.com) before calculating costs, falling back to hardcoded rates if unavailable.

**Important**: Cache write tokens (`cache_creation_input_tokens`) are the dominant cost driver in most Claude Code sessions and are often 10-100x the size of regular input tokens. This tool always includes them.

## Example output

### Standard report (`/cost-analysis --days 7`)

```
Claude Code Cost Analysis
=========================
Pricing source: llmpricecheck.com (live)
Period: 2026-02-01 to 2026-02-07  |  Sessions: 36  |  Total: $718.38
Filter: --days 7

PROJECT BREAKDOWN
Project              Sessions    Cost      Cache Write   Cache Read
────────────────────────────────────────────────────────────────────
my-api-project             12   $172.10       30.7M        52.7M
my-frontend                 3   $161.09       24.8M        68.2M
...

MODEL RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════

  ✅ OPUS JUSTIFIED
  my-api-project  $172.10  Implementing multi-agent spec against complex codebase

  ❌ DIDN'T NEED OPUS — Sonnet would save ~80%
  my-frontend     $161.09  Web editing, pushing branches, updating HTML  → saves ~$146

  💰 ESTIMATED SAVINGS IF SONNET USED: $97.00 (14% of total spend)

MCP USAGE DETECTED
══════════════════
8 of 36 sessions used MCP servers  |  MCP sessions avg cost: $51.84  |  Non-MCP avg: $103.67
Top MCP tools: mcp__glean-hosted__search (42 calls), mcp__glean-hosted__chat (5 calls)

Run /cost-analysis --mcp for detailed MCP overhead analysis.
```

### MCP report (`/cost-analysis --mcp`)

```
Claude Code Cost Analysis — MCP Overhead Report
═══════════════════════════════════════════════════════════════════════════
Period: 2026-02-01 to 2026-02-07  |  Sessions: 36  |  Total: $723.61
Mode: --mcp --days 7

MCP SERVER CONFIGURATION
═══════════════════════════════════════════════════════════════════════════
  Source       Server              Type     Used?
  ─────────────────────────────────────────────────────────────────────
  user         linear              stdio    Yes (20 sessions)
  plugin       glean-hosted        stdio    Yes (16 sessions)
  plugin       snowflake           stdio    No
  plugin       sourcegraph         stdio    No

  Configured: 4 servers  |  Actually used: 2 servers

MCP TOOL USAGE BREAKDOWN
═══════════════════════════════════════════════════════════════════════════
  Server: glean-hosted
  Tool                                   Calls    Avg Result    Total Result
  ──────────────────────────────────────────────────────────────────────────
  mcp__glean-hosted__search                139       16.1K          2.2M
  mcp__glean-hosted__read_document          10        1.9K           19K
  mcp__glean-hosted__employee_search         9        5.6K           50K
  mcp__glean-hosted__chat                    3       30.5K           92K
  ──────────────────────────────────────────────────────────────────────────
  Subtotal                                 161       14.9K          2.4M

CONTEXT OVERHEAD ANALYSIS
═══════════════════════════════════════════════════════════════════════════
  SCHEMA OVERHEAD
  MCP sessions avg first cache write:          34,553 tokens
  Non-MCP sessions avg first cache write:      28,100 tokens
  Estimated schema overhead:                   +6,454 tokens  (+23%)

  RESULT SIZE COMPARISON
  Avg MCP tool result:          19.5K chars
  Avg non-MCP tool result:       4.4K chars
  MCP results are 4.4x larger than non-MCP results

MCP OPTIMIZATION RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════════════
- You have 4 configured MCP servers but only use 1. Remove unused servers
  to reduce schema overhead.
- MCP tool results average 19.5K chars — use more specific queries to
  reduce result sizes.
```

## Cost of running this skill

Running `/cost-analysis` itself consumes tokens. Switch to Sonnet first (`/model sonnet`) — the analysis doesn't require Opus-level reasoning.

| Model  | Estimated Cost Per Run |
| ------ | ---------------------- |
| Opus   | $0.50 – $1.50          |
| Sonnet | $0.25 – $0.60          |
| Haiku  | $0.08 – $0.20          |

Cost scales with session count — more sessions means a larger JSON payload for Claude to process. See [COST-OF-RUNNING.md](COST-OF-RUNNING.md) for a full breakdown of what drives the cost.

## Requirements

- Claude Code installed
- Python 3.7+ available as `python3` in PATH (standard on macOS/Linux)
- Session data in `~/.claude/projects/` (generated automatically by Claude Code)
