# Output Format

Report section templates. Each section describes its purpose, required data, and an example. Adapt the format to what the user asked for — if they only asked about a specific project or time range, skip sections that aren't relevant. If they asked a simple question, give a concise answer instead of the full report.

## Header

Shows pricing source, period, and grand totals at a glance.

**Required data:** pricing source, date range, session count, total cost.

```
Claude Code Cost Analysis
========================
Pricing source: platform.claude.com (live)
Period: 2026-03-11 to 2026-03-18  |  Sessions: 36  |  Total Cost: $718.38  |  $/hr: $24.61
vs last run (2026-03-11): $502.15 -> $718.38 (+43%)
Budget: $500/month | Pace: $612/month | Status: OVER (+22%)
```

The "vs last run" line is only shown when run history exists and the previous run used matching filters. See Step 7 in SKILL.md.

The `$/hr` metric is omitted if total session duration is zero.

The "Budget:" line is only shown when `--budget N` was given. See Step 5 in SKILL.md.

## Summary by Project

Breaks down spend by project directory. Sort by total cost descending.

**Required data per row:** project name, session count, cost, $/hr, input tokens, output tokens, cache write tokens, cache read tokens.

```
PROJECT BREAKDOWN
Project                      Sessions      Cost    $/hr    Input   Output  Cache Write  Cache Read
---------------------------------------------------------------------------------------------------
my-api-project                      4   $47.23  $28.40    823K    142K        2.1M        5.3M
my-frontend                         2   $12.10  $16.25    201K     38K        0.6M        1.1M
---------------------------------------------------------------------------------------------------
TOTAL                               6   $59.33  $24.61      ...     ...         ...         ...
```

Omit the `$/hr` column for individual projects if `duration_min` is 0 for all sessions in that project.

## Top Sessions by Cost

Shows the most expensive individual sessions. Apply `--top N` limit (default 10). Sort by cost descending.

**Required data per row:** date, project, duration (minutes), cost, first prompt (truncated).

```
TOP SESSIONS
Date         Project                 Min       Cost  Prompt
-------------------------------------------------------------------------------
2026-02-08   my-api-project         114m    $38.91  Implement plan: redesign...
2026-02-28   my-frontend             72m    $24.17  Build a new dashboard UI...
```

## Cost by Model

Aggregated cost per model across all filtered sessions.

**Required data per row:** model ID, total cost.

```
MODEL BREAKDOWN
Model                                 Cost
---------------------------------------------
claude-opus-4-6                  $XXX.XX
claude-haiku-4-5-20251001         $XX.XX
claude-sonnet-4-6                  $X.XX
```

## Daily Spend

ASCII bar chart of cost per day, scaled to the most expensive day.

**Required data per row:** date, cost, session count.

```
DAILY SPEND
  2026-02-26  ██████████████            $47.23  (3 sessions)
  2026-02-25  ████████                  $28.41  (2 sessions)
```

## Token Cost Breakdown

Shows how each token type contributes to total cost.

**Required data:** total tokens and cost for each type (cache write, cache read, output, input).

```
TOKEN COST BREAKDOWN
  Cache Write Tokens:  X,XXX,XXX  ->  $XX.XX  (XX%)
  Cache Read Tokens:   X,XXX,XXX  ->  $XX.XX  (XX%)
  Output Tokens:         XXX,XXX  ->  $XX.XX  (XX%)
  Input Tokens:          XXX,XXX  ->  $XX.XX  (XX%)
  ------------------------------------------------
  TOTAL:                          ->  $XX.XX
```

## Trends and Observations

3-5 brief observations based on the data. Examples:
- "Your most expensive project is `X`, accounting for 42% of total spend."
- "Cache write tokens are driving 78% of your costs — normal for large codebase sessions."
- "Sessions this week cost 2.4x more than last week."

## Brief MCP Summary (when `--mcp` is NOT set)

If sessions used MCP tools but `--mcp` was not requested, show a brief summary:

```
MCP USAGE DETECTED
==================
N of M sessions used MCP servers  |  MCP sessions avg cost: $X.XX  |  Non-MCP avg: $X.XX
Top MCP tools: mcp__glean-hosted__search (N calls), mcp__pencil__batch_get (N calls)

Run /cost-analysis --mcp for detailed MCP overhead analysis.
```

If no sessions used MCP, skip this section entirely.

## Model Recommendations

> Note: Classification is based on prompt text heuristics and may not reflect actual task complexity.

For every project, check actual prompts from `~/.claude/history.jsonl` and classify the work type — covering both **Opus sessions** (recommend Sonnet where appropriate) and **Sonnet sessions** (recommend Haiku where appropriate).

**Task type classification:**

| Task Type | Signals | Recommended Model |
|---|---|---|
| Deep architecture / codebase reasoning | "assess", "implement spec", "analyze architecture" | Opus — justified |
| Complex multi-step implementation | "implement", "build from scratch", "refactor" | Opus — justified |
| Nuanced judgment / writing | feedback, perf reviews, strategic decisions | Opus — justified |
| Web/UI editing, simple fixes | "update", "push", "fix lint", "change the color" | Sonnet — Opus overkill |
| Research + summarization | "learn about X", "summarize", "find examples" | Sonnet — Opus overkill |
| Git operations | "commit", "push", "create branch", "open PR" | Sonnet — Opus overkill |
| Writing docs / markdown | "write this to a file", "create a README" | Sonnet — Opus overkill |
| Browser automation | "fill out the form", "navigate to", "scrape this" | Sonnet — Opus overkill |
| Q&A / explanation | "what is X", "how do I", "explain" | Sonnet — Opus overkill |
| Single-file read / simple lookup | "what does X return", "show me line N", "what's in this file" | Haiku — Sonnet overkill |
| Format / data conversion | "convert this JSON to CSV", "reformat this list" | Haiku — Sonnet overkill |
| Simple one-step transformation | "rename this variable", "fix this typo", "add a blank line" | Haiku — Sonnet overkill |
| Short factual Q&A | "what's the flag for X", "what does this error mean" | Haiku — Sonnet overkill |
| Repetitive mechanical tasks | batch renames, simple regex, counting occurrences | Haiku — Sonnet overkill |

**Example output:**

```
MODEL RECOMMENDATIONS
=============================================================

  OPUS JUSTIFIED
  my-api-project  $47.23  Deep architecture analysis + multi-file refactor

  BORDERLINE — Sonnet likely sufficient
  research-tool   $21.10  Product research + summarization

  DIDN'T NEED OPUS — Sonnet would save ~80%
  my-frontend     $38.17  Web editing, pushing branches, updating README  -> saves ~$31
  docs-project     $9.50  Writing markdown files, git push               -> saves ~$8

  DIDN'T NEED SONNET — Haiku would save ~67%
  scripts-util     $8.40  Single-file lookups, format conversions         -> saves ~$6
  quick-checks     $3.20  Simple one-step renames, short factual Q&A      -> saves ~$2

  ESTIMATED SAVINGS: $39 (Opus→Sonnet) + $8 (Sonnet→Haiku) = $47 total (XX% of total spend)
```

**Rules:**
- Always check actual prompts from history — don't guess based on project name alone
- If no prompts are available for a session, mark as "unknown task — check manually"
- Opus→Sonnet estimated savings = `opus_session_cost * 0.80`
- Sonnet→Haiku estimated savings = `sonnet_session_cost * 0.67`
- Only flag Sonnet sessions where the **primary user model** was Sonnet — Haiku subagents spawned automatically by Claude Code are already optimal and should not be flagged
- If a session mixed Opus + Haiku subagents, only flag the Opus portion
- Skip the Sonnet→Haiku tier entirely if no Sonnet sessions qualify (don't show an empty section)
- End with one actionable tip covering both tiers, e.g.: "Consider setting Sonnet as your default and using `/model opus` only for complex implementation sessions. For quick lookups and simple edits, `/model haiku` cuts costs by another 67%."
