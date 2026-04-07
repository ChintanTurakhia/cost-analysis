# Output Format

Report section templates. Each section describes its purpose, required data, and an example. Adapt the format to what the user asked for — if they only asked about a specific project or time range, skip sections that aren't relevant. If they asked a simple question, give a concise answer instead of the full report.

**Important: Compute before rendering.** Evaluate all 14 recommendation categories (from `references/recommendations.md`) and all model classifications before writing any sections. The Executive Summary requires results from both Cost Savings and Model Recommendations analyses, so these must be computed first.

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

## Executive Summary

Surfaces the highest-impact actions and model switching savings in a scannable block. This is the "so what" of the report — users who only read this section should walk away with the key actions.

**Required data:** Results from evaluating all 14 recommendation categories (sorted by estimated savings), and model recommendation analysis (Opus-justified, didn't-need-Opus, didn't-need-Sonnet tiers with estimated savings).

**Rules:**
- Show the top 3 action items (or fewer if fewer than 3 recommendations trigger)
- Each action item is one line: the recommendation title + estimated savings
- Below the actions, show a one-line model recommendation summary with total model-switching savings
- End with a total estimated savings line combining both sources
- If no cost savings recommendations trigger AND no model recommendations trigger, replace with: "No significant optimization opportunities detected for this period."
- Keep this section to 10-15 lines maximum
- Add a forward-reference to the detailed analysis sections

**When `--mcp` is set:** Replace the cost savings actions with MCP optimization highlights. Omit the model switching line.

```
EXECUTIVE SUMMARY
================================================================
Estimated total savings: $404/month

TOP 3 ACTIONS
1. Switch to Sonnet for web-dashboard and docs-site — saves ~$388
2. Start new sessions when switching tasks (context bloat in 8 sessions) — saves ~$52
3. Batch same-project work into fewer sessions — saves ~$28

Models: 12 sessions didn't need Opus (save ~$388), 4 didn't need Sonnet (save ~$16)

See DETAILED ANALYSIS below for full breakdowns and recommendation details.
```

## Project Summary

Quick glance at where money is going, without token-level detail.

**Required data per row:** project name, session count, total cost.

**Rules:**
- Show top 5 projects by cost, one line each
- If there are more than 5 projects, add a line: "... and N more projects ($XX.XX total) — see full breakdown below"
- Omit $/hr and token columns — those belong in the detailed table
- Sort by cost descending

```
PROJECT SUMMARY
Project                      Sessions      Cost
--------------------------------------------------
web-dashboard                      18   $312.45
agent-control                      12   $287.03
docs-site                           6   $118.90
scripts-util                        8     $8.40
quick-checks                        6     $3.10
... and 2 more projects ($1.30 total)
```

---

## Detailed Analysis

Everything below this point contains full data tables and detailed recommendation blocks. The Executive Summary above covers the key actions.

```
================================================================
DETAILED ANALYSIS
================================================================
```

### Full Project Breakdown

Full spend breakdown by project directory. Sort by total cost descending.

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

### Top Sessions by Cost

Shows the most expensive individual sessions. Apply `--top N` limit (default 10). Sort by cost descending.

**Required data per row:** date, project, duration (minutes), cost, first prompt (truncated).

```
TOP SESSIONS
Date         Project                 Min       Cost  Prompt
-------------------------------------------------------------------------------
2026-02-08   my-api-project         114m    $38.91  Implement plan: redesign...
2026-02-28   my-frontend             72m    $24.17  Build a new dashboard UI...
```

### Cost by Model

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

### Daily Spend

ASCII bar chart of cost per day, scaled to the most expensive day.

**Required data per row:** date, cost, session count.

```
DAILY SPEND
  2026-02-26  ██████████████            $47.23  (3 sessions)
  2026-02-25  ████████                  $28.41  (2 sessions)
```

### Token Cost Breakdown

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

### Cache Efficiency

Shows how well prompt cache writes are being recouped through cache reads. A cache write costs ~1.25x a regular input token up front; if the same context is read back repeatedly, the writes pay off. If sessions are short or one-off, writes often go unrecouped.

**Required data:** per-project cache_write_tokens, cache_read_tokens; cold session counts; overall reuse ratio and savings.

```
CACHE EFFICIENCY
===================================================
Overall reuse ratio: 7.5x  (cache reads / cache writes — higher is better)
Cold sessions (writes with zero reads): 8 of 36 (22%)
Estimated savings vs no-cache: $143.32

By project:
  Project              Reuse    Cold     Cache Write Cost   Savings
  -------------------------------------------------------------------
  my-api-project        12.4x   0 / 4         $8.20          $6.80  ✓
  my-frontend            1.8x   3 / 6         $4.10          $1.10  ← low reuse
  scripts-util           0.0x   5 / 5         $1.20          $0.00  ← never reused

RECOMMENDATIONS
  my-frontend (reuse 1.8x): Cache writes aren't being recouped. Try fewer, longer
  sessions instead of many short ones. Batching related tasks into one session
  lets the cache warm up and pay for itself.

  scripts-util (0.0x reuse, all sessions cold): These appear to be short one-off
  tasks where no session ever resumed the same context. Consider using Haiku (lower
  cache write rate) or consolidating work into a single longer session.
```

**Rules:**
- Show this section in the standard report (not just `--mcp`).
- Only show the RECOMMENDATIONS sub-block if at least one project has `reuse_ratio < 1.5` or `cold_session_rate > 0.5`. If all projects have healthy reuse, replace with: "Cache reuse looks healthy across all projects."
- If `sum(cache_write_tokens) == 0` across all sessions, skip this section entirely.
- Savings estimate uses per-model rates. For sessions with mixed models, use the model that generated the most cache write tokens.
- A reuse ratio > 5x is healthy. 1–5x is marginal. < 1x means most writes were wasted.

### Cost Savings — Detailed Recommendations

Personalized, data-driven recommendations for reducing Claude Code costs. The TOP 3 ACTIONS summary appears in the Executive Summary above; this section contains the full detailed recommendation blocks.

**Required data:** All session-level fields including `cost_first_half`, `cost_second_half`, `context_growth_ratio`, `user_text_turns`, `inter_turn_gaps`, `read_file_counts`, `duplicate_reads`, `large_tool_results`, `avg_turn_cost`, `max_turn_cost`.

**Before generating this section**, read `references/recommendations.md` for the full list of 14 recommendation categories, their trigger conditions, savings formulas, and output templates.

**Rules:**
- Evaluate all 14 categories against the session data
- Only show recommendations that trigger (meet their threshold conditions)
- Sort by estimated savings descending
- Show at most 8 recommendations
- Skip recommendations with < $1 estimated savings
- Use real data from the user's sessions (project names, costs, prompts) — never use placeholder values
- If no recommendations trigger, skip this section entirely

```
COST SAVINGS — DETAILED RECOMMENDATIONS
================================================================
Top 3 actions summarized in Executive Summary above.

[Individual recommendation blocks from recommendations.md, sorted by savings]
```

### Model Recommendations

> Note: Classification is based on prompt text heuristics and may not reflect actual task complexity.

Model switching savings are summarized in the Executive Summary above. This section contains the full classification and per-project breakdown.

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

### Trends and Observations

3-5 brief observations based on the data. Examples:
- "Your most expensive project is `X`, accounting for 42% of total spend."
- "Cache write tokens are driving 78% of your costs — normal for large codebase sessions."
- "Sessions this week cost 2.4x more than last week."

### Brief MCP Summary (when `--mcp` is NOT set)

If sessions used MCP tools but `--mcp` was not requested, show a brief summary:

```
MCP USAGE DETECTED
==================
N of M sessions used MCP servers  |  MCP sessions avg cost: $X.XX  |  Non-MCP avg: $X.XX
Top MCP tools: mcp__glean-hosted__search (N calls), mcp__pencil__batch_get (N calls)

Run /cost-analysis --mcp for detailed MCP overhead analysis.
```

If no sessions used MCP, skip this section entirely.
