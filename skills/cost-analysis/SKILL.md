---
name: cost-analysis
description: Analyze Claude Code token usage and costs from local session data. Use when asking about token usage, API costs, spending patterns, Claude budget, how much sessions cost, which projects are most expensive, or any breakdown of Claude Code usage by project/date/model.
user-invocable: true
tools: Bash, Read, WebFetch
---

# Cost Analysis

Analyzes Claude Code token usage and cost from local session data stored in `~/.claude/projects/`. Reads raw conversation files to extract per-turn model and token data, then computes costs using Anthropic's current pricing — including prompt caching tokens. Outputs a clean summary table with totals, trends, and model recommendations.

## Arguments

`$ARGUMENTS` is an optional filter string. Supported flags:

- `--project <name>` — Filter to sessions whose working directory matches `<name>` (case-insensitive substring match on the project path)
- `--days <N>` — Only include sessions from the last N days (default: all time)
- `--model <name>` — Filter to sessions that used a specific model (e.g., `opus`, `sonnet`, `haiku`)
- `--top <N>` — Show only the top N most expensive sessions (default: 10)

If no arguments are given, analyze all sessions and show a full breakdown.

### Examples

```
/cost-analysis
/cost-analysis --days 30
/cost-analysis --project my-project
/cost-analysis --days 7 --top 5
/cost-analysis --model opus
```

## Pricing Reference

**Always fetch live pricing before calculating costs.** Do not use hardcoded prices — models update frequently.

### Step 0: Fetch Current Pricing

Fetch pricing from both sources and merge, preferring the most specific/recent data:

1. **Primary**: `https://llmpricecheck.com/` — fetch with WebFetch, extract Anthropic model prices
2. **Fallback**: `https://sanand0.github.io/llmpricing/` — fetch with WebFetch, extract from the JSON/table data

Look for models matching the pattern `claude-*` and extract input price, output price per 1M tokens. Derive:
- **Cache write** = 1.25x input price
- **Cache read** = 0.1x input price

If both sources are unavailable, fall back to these hardcoded rates (note in output that prices may be outdated):

| Model                         | Input    | Output   | Cache Write | Cache Read |
|-------------------------------|----------|----------|-------------|------------|
| claude-opus-4-6               | $15.00   | $75.00   | $18.75      | $1.50      |
| claude-sonnet-4-6             | $3.00    | $15.00   | $3.75       | $0.30      |
| claude-haiku-4-5-20251001     | $0.80    | $4.00    | $1.00       | $0.08      |

Unknown models default to Opus pricing (conservative estimate). Always show which pricing source was used in the output header.

**Important**: The `cache_creation_input_tokens` field in usage data represents tokens written to the prompt cache. These are the dominant cost driver in long Claude Code sessions. Always include them in cost calculations.

## Data Sources

### Primary: `~/.claude/projects/**/*.jsonl`

This is the authoritative source for token counts and model information. Every Claude Code project session writes a `.jsonl` file under `~/.claude/projects/<encoded-project-path>/<session-uuid>.jsonl`. Subagent sessions are nested under `<session-uuid>/subagents/agent-<id>.jsonl`.

Each line is a JSON object. The relevant lines have `"type": "assistant"` and contain a `message` object with:

```json
{
  "type": "assistant",
  "sessionId": "cb82d5ba-d93e-4e01-a9f9-bee38e3cb50c",
  "cwd": "/home/user/projects/my-project",
  "timestamp": "2026-02-26T07:44:51.363Z",
  "message": {
    "model": "claude-opus-4-6",
    "role": "assistant",
    "usage": {
      "input_tokens": 471,
      "output_tokens": 241,
      "cache_creation_input_tokens": 2207379,
      "cache_read_input_tokens": 830467
    }
  }
}
```

Sum all four token fields across every assistant turn in a session to get the session total. A single session may use multiple models (e.g., Opus for main agent, Haiku for subagents). Track each model separately and compute costs independently.

### Secondary: `~/.claude/usage-data/session-meta/*.json`

Each session has a corresponding JSON file keyed by `<session-uuid>.json`. This provides human-readable context:

```json
{
  "session_id": "cb82d5ba-...",
  "project_path": "/home/user/projects/my-project",
  "start_time": "2026-02-26T07:44:28.829Z",
  "duration_minutes": 114,
  "first_prompt": "Implement the plan: Fix the auth bug...",
  "tool_counts": { "Bash": 19, "Read": 6, "Edit": 5 },
  "input_tokens": 471,
  "output_tokens": 241
}
```

Use `first_prompt` for a human-readable description of what the session did. Use `start_time` for date filtering. Note: `input_tokens` and `output_tokens` in meta match the non-cache token totals from the project jsonl, but **cache tokens are only in the project jsonl** — always use the project jsonl for complete cost data.

### Tertiary: `~/.claude/history.jsonl`

Each line maps a user message to a project and session:

```json
{
  "display": "fix the auth bug in send-v2",
  "timestamp": 1767849548438,
  "project": "/home/user/projects/my-project",
  "sessionId": "cb82d5ba-..."
}
```

Use this to enrich session data with the user's original prompts if session-meta doesn't have a `first_prompt`. Also used for the model recommendations section to classify task types.

## Steps

### 1. Parse Arguments

Parse `$ARGUMENTS` for optional filters:
- `--days N` → compute cutoff date as today minus N days
- `--project name` → case-insensitive substring match against `cwd` or `project_path`
- `--model name` → match any model ID containing the substring (e.g., `opus` matches `claude-opus-4-6`)
- `--top N` → limit session table to N rows (still compute full totals)

### 2. Collect and Aggregate Session Data

Run the following Python analysis script using `Bash`. This is the core data collection step — do it in a single script invocation to avoid repeated file I/O.

```python
#!/usr/bin/env python3
import json, os, glob
from datetime import datetime, timedelta
from collections import defaultdict

# PRICING is injected by Claude from live-fetched data before running this script.
# Format: { 'model-id': (input_per_1M, output_per_1M, cache_write_per_1M, cache_read_per_1M) }
# Claude should replace the dict below with live-fetched prices, falling back to these defaults.
PRICING = {
    'claude-opus-4-6':            (15.00, 75.00, 18.75, 1.50),
    'claude-opus-4-5-20251101':   (15.00, 75.00, 18.75, 1.50),
    'claude-sonnet-4-6':          (3.00,  15.00, 3.75,  0.30),
    'claude-sonnet-4-5-20250929': (3.00,  15.00, 3.75,  0.30),
    'claude-haiku-4-5-20251001':  (0.80,  4.00,  1.00,  0.08),
}
# Prefix-based fallbacks for unrecognized versioned model IDs.
# Checked in order — haiku first so 'claude-haiku-*' never hits the sonnet check.
PREFIX_PRICING = [
    ('claude-haiku',  (0.80,  4.00,  1.00,  0.08)),
    ('claude-sonnet', (3.00,  15.00, 3.75,  0.30)),
    ('claude-opus',   (15.00, 75.00, 18.75, 1.50)),
]
DEFAULT_PRICING = (15.00, 75.00, 18.75, 1.50)  # Opus as conservative default for truly unknown models

def get_pricing(model):
    if model in PRICING:
        return PRICING[model]
    m = model.lower()
    for prefix, pricing in PREFIX_PRICING:
        if m.startswith(prefix):
            return pricing
    return DEFAULT_PRICING

def token_cost(model, inp, out, cache_write, cache_read):
    p = get_pricing(model)
    return (inp * p[0] + out * p[1] + cache_write * p[2] + cache_read * p[3]) / 1_000_000

sessions = defaultdict(lambda: {
    'cwd': 'unknown', 'first_ts': '', 'last_ts': '',
    'models': defaultdict(lambda: {'input': 0, 'output': 0, 'cache_write': 0, 'cache_read': 0, 'turns': 0}),
    'first_prompt': '', 'duration_minutes': 0,
})

project_root = os.path.expanduser('~/.claude/projects')
all_jsonls = glob.glob(os.path.join(project_root, '**', '*.jsonl'), recursive=True)

parse_failures = 0
for fpath in all_jsonls:
    try:
        with open(fpath, 'r', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                obj = json.loads(line)
                if obj.get('type') != 'assistant': continue
                msg = obj.get('message', {})
                if not isinstance(msg, dict) or 'model' not in msg or 'usage' not in msg: continue
                sid = obj.get('sessionId', 'unknown')
                model = msg['model']
                if model == '<synthetic>': continue
                usage = msg['usage']
                cwd = obj.get('cwd', 'unknown')
                ts = obj.get('timestamp', '')
                s = sessions[sid]
                if not s['cwd'] or s['cwd'] == 'unknown': s['cwd'] = cwd
                if not s['first_ts'] or ts < s['first_ts']: s['first_ts'] = ts
                if ts > s['last_ts']: s['last_ts'] = ts
                m = s['models'][model]
                m['input']       += usage.get('input_tokens', 0)
                m['output']      += usage.get('output_tokens', 0)
                m['cache_write'] += usage.get('cache_creation_input_tokens', 0)
                m['cache_read']  += usage.get('cache_read_input_tokens', 0)
                m['turns']       += 1
    except Exception:
        parse_failures += 1

meta_dir = os.path.expanduser('~/.claude/usage-data/session-meta')
if os.path.isdir(meta_dir):
    for fname in os.listdir(meta_dir):
        if not fname.endswith('.json'): continue
        sid = fname[:-5]
        try:
            with open(os.path.join(meta_dir, fname)) as f:
                meta = json.load(f)
            if sid in sessions:
                if not sessions[sid]['first_ts'] and meta.get('start_time'):
                    sessions[sid]['first_ts'] = meta['start_time']
                if not sessions[sid]['cwd'] or sessions[sid]['cwd'] == 'unknown':
                    sessions[sid]['cwd'] = meta.get('project_path', 'unknown')
                sessions[sid]['first_prompt'] = meta.get('first_prompt', '')[:80]
                sessions[sid]['duration_minutes'] = meta.get('duration_minutes', 0)
        except Exception:
            pass

results = []
for sid, s in sessions.items():
    total_cost = 0
    total_input = total_output = total_cache_write = total_cache_read = total_turns = 0
    model_costs = {}
    for model, m in s['models'].items():
        c = token_cost(model, m['input'], m['output'], m['cache_write'], m['cache_read'])
        total_cost += c
        model_costs[model] = round(c, 4)
        total_input       += m['input']
        total_output      += m['output']
        total_cache_write += m['cache_write']
        total_cache_read  += m['cache_read']
        total_turns       += m['turns']
    results.append({
        'session_id': sid,
        'cwd': s['cwd'],
        'project': os.path.basename(s['cwd'].rstrip('/')),
        'date': s['first_ts'][:10] if s['first_ts'] else 'unknown',
        'timestamp': s['first_ts'],
        'duration_min': s['duration_minutes'],
        'first_prompt': s['first_prompt'],
        'models': list(s['models'].keys()),
        'model_costs': model_costs,
        'total_cost': round(total_cost, 4),
        'input_tokens': total_input,
        'output_tokens': total_output,
        'cache_write_tokens': total_cache_write,
        'cache_read_tokens': total_cache_read,
        'turns': total_turns,
    })

import sys
if parse_failures > 0:
    print(f'Warning: {parse_failures} session files could not be parsed and were skipped.', file=sys.stderr)
print(json.dumps(results))
```

Save the stdout to a variable. If the script writes to stderr, surface that warning verbatim in the output. If the script fails entirely, report the error and stop.

### 3. Apply Filters

Filter the results list based on parsed arguments:

- **`--days N`**: Keep only entries where `date >= (today - N days)`.
- **`--project name`**: Keep only entries where `name.lower()` is a substring of `cwd.lower()`.
- **`--model name`**: Keep only entries where at least one model in `models` contains `name.lower()`.

### 4. Compute Aggregates

From the filtered results, compute:

**By project** (group by `project` field):
- Total cost, session count, token totals, date range

**By date** (group by `date` field, YYYY-MM-DD):
- Total cost, session count

**By model** (aggregate across all sessions):
- Total cost per model, total tokens

**Grand totals**: total cost, token counts, session count, most expensive session, most active project.

### 5. Present Results

Display results in this order, using clean markdown tables and human-readable numbers. Format costs with `$` prefix. Use `K` suffix for thousands, `M` for millions of tokens.

#### Header

```
Claude Code Cost Analysis
========================
Pricing source: <source or "hardcoded fallback">
Period: <first date> to <last date>  |  Sessions: <N>  |  Total Cost: $<X.XX>
```

#### Summary by Project

Sort by total cost descending.

```
PROJECT BREAKDOWN
Project                      Sessions      Cost    Input   Output  Cache Write  Cache Read
──────────────────────────────────────────────────────────────────────────────────────────
my-api-project                      4   $47.23    823K    142K        2.1M        5.3M
my-frontend                         2   $12.10    201K     38K        0.6M        1.1M
──────────────────────────────────────────────────────────────────────────────────────────
TOTAL                               6   $59.33      ...     ...         ...         ...
```

#### Top Sessions by Cost

Apply `--top N` limit (default 10). Sort by cost descending.

```
TOP SESSIONS
Date         Project                 Min       Cost  Prompt
──────────────────────────────────────────────────────────────────────────────
2026-02-08   my-api-project         114m    $38.91  Implement plan: redesign...
2026-02-28   my-frontend             72m    $24.17  Build a new dashboard UI...
```

#### Cost by Model

```
MODEL BREAKDOWN
Model                                 Cost
─────────────────────────────────────────
claude-opus-4-6                  $XXX.XX
claude-haiku-4-5-20251001         $XX.XX
claude-sonnet-4-6                  $X.XX
```

#### Daily Spend

```
DAILY SPEND
  2026-02-26  ██████████████░░░░░░░░░░  $47.23  (3 sessions)
  2026-02-25  ████████░░░░░░░░░░░░░░░░  $28.41  (2 sessions)
```

ASCII bar chart scaled to the most expensive day. Each full block (`█`) = ~5% of max.

#### Token Cost Breakdown

```
TOKEN COST BREAKDOWN
  Cache Write Tokens:  X,XXX,XXX  →  $XX.XX  (XX%)   ← usually the biggest cost
  Cache Read Tokens:   X,XXX,XXX  →  $XX.XX  (XX%)
  Output Tokens:         XXX,XXX  →  $XX.XX  (XX%)
  Input Tokens:          XXX,XXX  →  $XX.XX  (XX%)
  ──────────────────────────────────────────────────
  TOTAL:                          →  $XX.XX
```

#### Trends and Observations

3-5 brief observations, e.g.:
- "Your most expensive project is `X`, accounting for 42% of total spend."
- "Cache write tokens are driving 78% of your costs — normal for large codebase sessions."
- "Sessions this week cost 2.4x more than last week."

---

#### Model Recommendations

For every project that used Opus, look at the actual prompts from `~/.claude/history.jsonl` (match by `sessionId`) and classify the work type. Give a verdict on whether Opus was justified.

**Task type classification:**

| Task type | Signals in prompts | Recommended model |
|---|---|---|
| Deep architecture / codebase reasoning | "assess", "implement spec", "analyze architecture", "how does X work across the repo" | **Opus** — justified |
| Complex multi-step implementation | "implement", "build from scratch", "refactor", long sessions with many turns | **Opus** — justified |
| Nuanced judgment / writing | feedback, perf reviews, strategic decisions, sensitive analysis | **Opus** — justified |
| Web/UI editing, simple fixes | "update", "push", "fix lint", "change the color", "update README" | **Sonnet** — Opus overkill |
| Research + summarization | "learn about X", "summarize", "find examples", "write a tweet thread" | **Sonnet** — Opus overkill |
| Git operations | "commit", "push", "create branch", "open PR" | **Sonnet** — Opus overkill |
| Writing docs / markdown | "write this to a file", "create a README", "document this" | **Sonnet** — Opus overkill |
| Browser automation | "fill out the form", "navigate to", "scrape this" | **Sonnet** — Opus overkill |
| Q&A / explanation | "what is X", "how do I", "explain" | **Sonnet** — Opus overkill |

**Format:**

```
MODEL RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════

  ✅ OPUS JUSTIFIED
  my-api-project  $47.23  Deep architecture analysis + multi-file refactor

  ⚠️  BORDERLINE — Sonnet likely sufficient
  research-tool   $21.10  Product research + summarization

  ❌ DIDN'T NEED OPUS — Sonnet would save ~80%
  my-frontend     $38.17  Web editing, pushing branches, updating README  → saves ~$31
  docs-project     $9.50  Writing markdown files, git push               → saves ~$8

  💰 ESTIMATED SAVINGS IF SONNET USED: $XX.XX (XX% of total spend)
```

**Rules:**
- Always check actual prompts from history — don't guess based on project name alone
- If no prompts are available for a session, mark as "unknown task — check manually"
- Estimated savings = `opus_cost_for_that_session * 0.80`
- If a session mixed Opus + Haiku subagents, only flag the Opus portion
- End with one actionable tip, e.g.: "Consider setting Sonnet as your default and using `/model opus` only for complex implementation sessions."

## Error Handling

- **No session data found**: Report "No Claude Code session data found in ~/.claude/projects/." and stop.
- **Filter matches zero sessions**: Report "No sessions matched the given filters." and list filters applied.
- **Python unavailable**: Fall back to `bash` + `jq`, note cache token extraction may be incomplete.
- **Partial data**: Continue and note "Warning: N files could not be parsed and were skipped."
- **Unknown model IDs**: Apply Opus pricing as conservative default and note it in output.

## Notes on Data Accuracy

- **Cache tokens dominate costs**: `cache_creation_input_tokens` can be orders of magnitude larger than `input_tokens`. Always sum all four token types.
- **Session-meta vs project jsonl**: session-meta does not store cache token counts. Always read from project jsonl for accurate cost data.
- **Subagent sessions**: Subagent jsonl files under `<session>/subagents/agent-*.jsonl` contribute to the same `sessionId` and are attributed to the parent session's `cwd`.
