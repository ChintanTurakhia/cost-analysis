# cost-analysis — Claude Code Plugin

Analyze your Claude Code token usage and costs from local session data. See exactly what you spent, by project, model, and day — including which sessions didn't need Opus.

## What it does

- **Project breakdown** — cost, tokens, session count per project
- **Top sessions** — most expensive sessions with the prompts that triggered them
- **Model breakdown** — spend per model (Opus vs Sonnet vs Haiku)
- **Daily spend** — ASCII bar chart of spend over time
- **Token cost breakdown** — shows how much cache write vs cache read vs output vs input tokens cost (cache write is usually the dominant driver)
- **Model recommendations** — classifies each project's work type and tells you which ones didn't need Opus, with estimated savings

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

```
/cost-analysis:cost-analysis
/cost-analysis:cost-analysis --days 7
/cost-analysis:cost-analysis --days 30
/cost-analysis:cost-analysis --project my-project
/cost-analysis:cost-analysis --days 7 --top 5
/cost-analysis:cost-analysis --model opus
```

## Flags

| Flag | Description | Default |
|---|---|---|
| `--days N` | Only include sessions from the last N days | all time |
| `--project name` | Filter to sessions matching this project name | all projects |
| `--model name` | Filter to sessions that used this model | all models |
| `--top N` | Show only the top N most expensive sessions | 10 |

## How it works

Reads directly from `~/.claude/projects/**/*.jsonl` — the same session files Claude Code writes locally. Fetches live pricing from [llmpricecheck.com](https://llmpricecheck.com) before calculating costs, falling back to hardcoded rates if unavailable.

**Important**: Cache write tokens (`cache_creation_input_tokens`) are the dominant cost driver in most Claude Code sessions and are often 10-100x the size of regular input tokens. This tool always includes them.

## Example output

```
Claude Code Cost Analysis
=========================
Pricing source: llmpricecheck.com (live)
Period: 2026-03-02 to 2026-03-09  |  Sessions: 21  |  Total: $1,122.93
Filter: --days 7

PROJECT BREAKDOWN
Project              Sessions    Cost      Cache Write   Cache Read
────────────────────────────────────────────────────────────────────
my-api-project              2   $342.77       14.0M        54.7M
my-frontend                 4   $183.17       11.5M        18.8M
...

MODEL RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════

  ✅ OPUS JUSTIFIED
  my-api-project  $342.77  Implementing multi-agent spec against complex codebase

  ❌ DIDN'T NEED OPUS — Sonnet would save ~80%
  my-frontend     $183.17  Web editing, pushing branches, updating HTML  → saves ~$146

  💰 ESTIMATED SAVINGS IF SONNET USED: $307.00 (27% of total spend)
```

## Requirements

- Claude Code installed
- Python 3.7+ available as `python3` in PATH (standard on macOS/Linux)
- Session data in `~/.claude/projects/` (generated automatically by Claude Code)
