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

```
/plugin marketplace add ChintanTurakhia/cost-analysis
```

```
/plugin install cost-analysis@cost-analysis
```

```
/reload-plugins
```

Then run `/cost-analysis:analyze` in any session.

## Usage

Basic cost analysis:

```
/cost-analysis:analyze                                   # all sessions, full breakdown
/cost-analysis:analyze --days 7                          # last 7 days only
/cost-analysis:analyze --days 30                         # last 30 days
/cost-analysis:analyze --project my-project              # filter to one project
/cost-analysis:analyze --days 7 --top 5                  # last week, top 5 sessions
/cost-analysis:analyze --model opus                      # only Opus sessions
```

MCP overhead analysis:

```
/cost-analysis:analyze --mcp                             # full MCP overhead report
/cost-analysis:analyze --mcp --days 30                   # MCP analysis for last 30 days
/cost-analysis:analyze --mcp --mcp-server glean-hosted   # filter to one MCP server
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

Reads directly from `~/.claude/projects/**/*.jsonl` — the same session files Claude Code writes locally. Uses hardcoded pricing from [Anthropic's official pricing page](https://platform.claude.com/docs/en/about-claude/pricing), covering all current Claude models including Opus 4.6, Sonnet 4.6, and Haiku 4.5.

**Important**: Cache write tokens (`cache_creation_input_tokens`) are the dominant cost driver in most Claude Code sessions and are often 10-100x the size of regular input tokens. This tool always includes them.

## Example output

### Standard report (`/cost-analysis:analyze --days 7`)

```
Claude Code Cost Analysis
=========================
Pricing source: platform.claude.com
Period: 2026-03-06 to 2026-03-12  |  Sessions: 36  |  Total: $718.38
Filter: --days 7

PROJECT BREAKDOWN
Project              Sessions    Cost      Cache Write   Cache Read
────────────────────────────────────────────────────────────────────
web-dashboard              18   $312.45       55.2M       102.4M
agent-control              12   $287.03       48.1M        89.7M
docs-site                   6   $118.90       19.3M        34.6M
────────────────────────────────────────────────────────────────────
TOTAL                      36   $718.38      122.6M       226.7M

TOP SESSIONS
Date         Project              Min       Cost  Prompt
──────────────────────────────────────────────────────────────────────
2026-03-11   agent-control         142m   $52.37  Implement multi-agent orchestration with...
2026-03-10   web-dashboard         98m    $41.23  Redesign dashboard layout and add real-t...
2026-03-08   web-dashboard         76m    $38.91  Build settings page with form validation...

MODEL BREAKDOWN
Model                                 Cost
─────────────────────────────────────────
claude-opus-4-6                   $694.12
claude-sonnet-4-6                  $18.76
claude-haiku-4-5-20251001           $5.50

DAILY SPEND
  2026-03-12  ████████████████████████  $198.42  (8 sessions)
  2026-03-11  █████████████████████░░░  $172.36  (7 sessions)
  2026-03-10  ███████████████████░░░░░  $156.89  (9 sessions)
  2026-03-09  ██████████████░░░░░░░░░░  $114.23  (6 sessions)

TOKEN COST BREAKDOWN
  Cache Write Tokens:  63,412,850  →  $482.17  (67%)   ← usually the biggest cost
  Cache Read Tokens:  477,733,333  →  $143.32  (20%)
  Output Tokens:        4,310,000  →   $64.65   (9%)
  Input Tokens:         2,353,333  →   $28.24   (4%)
  ──────────────────────────────────────────────────
  TOTAL:                           →  $718.38

MODEL RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════

  ✅ OPUS JUSTIFIED
  agent-control   $287.03  Multi-agent orchestration, complex refactoring

  ❌ DIDN'T NEED OPUS — Sonnet would save ~80%
  web-dashboard   $312.45  Updating HTML, pushing branches, CSS changes   → saves ~$281
  docs-site       $118.90  Writing markdown, basic git operations          → saves ~$107

  💰 ESTIMATED SAVINGS IF SONNET USED: $388.00 (54% of total spend)

MCP USAGE DETECTED
══════════════════
10 of 36 sessions used MCP servers  |  MCP sessions avg cost: $15.84  |  Non-MCP avg: $21.54
Top MCP tools: mcp__glean-hosted__search (42 calls), mcp__glean-hosted__chat (5 calls)

Run /cost-analysis:analyze --mcp for detailed MCP overhead analysis.
```

### MCP report (`/cost-analysis:analyze --mcp --days 7`)

```
Claude Code Cost Analysis — MCP Overhead Report
═══════════════════════════════════════════════════════════════════════════
Pricing source: platform.claude.com
Period: 2026-03-06 to 2026-03-12  |  Sessions: 36  |  Total: $718.38
Mode: --mcp --days 7

MCP SERVER CONFIGURATION
═══════════════════════════════════════════════════════════════════════════
  Source       Server              Type     Used?
  ─────────────────────────────────────────────────────────────────────
  user         excalidraw          stdio    No
  user         custom-tools        sse      No
  user         glean-hosted        stdio    Yes (10 sessions)
  user         pencil              stdio    No
  user         sourcegraph         stdio    No

  Configured: 5 servers  |  Actually used: 1 server

MCP TOOL USAGE BREAKDOWN
═══════════════════════════════════════════════════════════════════════════

  Server: glean-hosted
  Tool                                   Calls    Avg Result    Total Result
  ──────────────────────────────────────────────────────────────────────────
  mcp__glean-hosted__search                42       29.5K         1.2M
  mcp__glean-hosted__chat                   5       45.2K         226K
  mcp__glean-hosted__read_document          3       91.3K         274K
  ──────────────────────────────────────────────────────────────────────────
  Subtotal                                 50       34.4K         1.7M

CONTEXT OVERHEAD ANALYSIS
═══════════════════════════════════════════════════════════════════════════

  RESULT SIZE COMPARISON
  ────────────────────────────────────────────────────────────────────────
  Avg MCP tool result:       34.4K chars
  Avg non-MCP tool result:    4.1K chars
  MCP results are 8.4x larger than non-MCP results

  COST IMPACT
  ────────────────────────────────────────────────────────────────────────
  MCP sessions avg cost:       $15.84  (10 sessions)
  Non-MCP sessions avg cost:   $21.54  (26 sessions)

MCP OPTIMIZATION RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════════════
- You have 5 configured MCP servers but only use 1. Remove unused servers
  (excalidraw, custom-tools, pencil, sourcegraph) to reduce
  schema overhead — each unused server still loads its full tool schema
  into context.
- MCP tool results average 34.4K chars — that's large context consumption.
  Use more specific queries to reduce result sizes.
```

## Cost of running this skill

Running `/cost-analysis:analyze` itself consumes tokens. Switch to Sonnet first (`/model sonnet`) — the analysis doesn't require Opus-level reasoning.

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

## Limitations

- **Claude Code only.** Cursor and OpenCode don't store per-session token usage or cost data locally — their billing is server-side. Without local token counts, there's nothing to analyze. If either tool starts writing session-level usage data to disk, support could be added.
- **30-day data retention.** Claude Code only keeps session data in `~/.claude/projects/` for approximately 30 days. Analysis beyond that window will show incomplete data.
