---
name: cost-analysis
description: Analyze Claude Code token usage and costs from local session data. Use when asking about token usage, API costs, spending patterns, Claude budget, how much sessions cost, which projects are most expensive, any breakdown of Claude Code usage by project/date/model, MCP server overhead, MCP tool result sizes, or MCP context bloat.
user-invocable: true
tools: Bash, Read
---

# Cost Analysis

Analyzes Claude Code token usage and cost from local session data stored in `~/.claude/projects/`. Reads raw conversation files to extract per-turn model and token data, then computes costs using Anthropic's current pricing — including prompt caching tokens. Outputs a clean summary table with totals, trends, and model recommendations. With `--mcp`, provides deep analysis of MCP server overhead including tool result sizes, schema bloat, and optimization recommendations.

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

## Pricing Reference

Use the hardcoded rates below from [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing). Cache write = 1.25x input, cache read = 0.1x input.

| Model                         | Input    | Output   | Cache Write | Cache Read |
|-------------------------------|----------|----------|-------------|------------|
| claude-opus-4-6               | $5.00    | $25.00   | $6.25       | $0.50      |
| claude-opus-4-5-20251101      | $5.00    | $25.00   | $6.25       | $0.50      |
| claude-opus-4-1-20250805      | $15.00   | $75.00   | $18.75      | $1.50      |
| claude-opus-4-20250514        | $15.00   | $75.00   | $18.75      | $1.50      |
| claude-sonnet-4-6             | $3.00    | $15.00   | $3.75       | $0.30      |
| claude-sonnet-4-5-20250929    | $3.00    | $15.00   | $3.75       | $0.30      |
| claude-sonnet-4-20250514      | $3.00    | $15.00   | $3.75       | $0.30      |
| claude-haiku-4-5-20251001     | $1.00    | $5.00    | $1.25       | $0.10      |

Unknown models use prefix-based matching (`claude-opus-*` → Opus 4.6 rate, `claude-sonnet-*` → Sonnet rate, `claude-haiku-*` → Haiku rate). Truly unrecognized models default to Opus 4.6 pricing as a conservative estimate.

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
- `--mcp` → enable MCP-focused analysis sections
- `--mcp-server name` → filter MCP analysis to a specific server name (implies `--mcp`)

### 2. Collect and Aggregate Session Data

Run the following Python analysis script using `Bash`. This is the core data collection step — do it in a single script invocation to avoid repeated file I/O.

```python
#!/usr/bin/env python3
import json, os, glob, sys
from datetime import datetime, timedelta
from collections import defaultdict

# PRICING is injected by Claude from live-fetched data before running this script.
# Format: { 'model-id': (input_per_1M, output_per_1M, cache_write_per_1M, cache_read_per_1M) }
# Claude should replace the dict below with live-fetched prices, falling back to these defaults.
PRICING = {
    'claude-opus-4-6':            (5.00,  25.00, 6.25,  0.50),
    'claude-opus-4-5-20251101':   (5.00,  25.00, 6.25,  0.50),
    'claude-opus-4-1-20250805':   (15.00, 75.00, 18.75, 1.50),
    'claude-opus-4-20250514':     (15.00, 75.00, 18.75, 1.50),
    'claude-sonnet-4-6':          (3.00,  15.00, 3.75,  0.30),
    'claude-sonnet-4-5-20250929': (3.00,  15.00, 3.75,  0.30),
    'claude-sonnet-4-20250514':   (3.00,  15.00, 3.75,  0.30),
    'claude-haiku-4-5-20251001':  (1.00,  5.00,  1.25,  0.10),
}
PREFIX_PRICING = [
    ('claude-haiku',  (1.00,  5.00,  1.25,  0.10)),
    ('claude-sonnet', (3.00,  15.00, 3.75,  0.30)),
    ('claude-opus',   (5.00,  25.00, 6.25,  0.50)),
]
DEFAULT_PRICING = (5.00, 25.00, 6.25, 0.50)

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
    'first_cache_write': None,  # First cache_creation_input_tokens value (schema overhead proxy)
    'tool_calls': [],  # List of {'name': str, 'id': str, 'is_mcp': bool}
    'tool_results': {},  # tool_use_id -> content_length
    'uses_mcp': False,
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
                otype = obj.get('type')

                if otype == 'assistant':
                    msg = obj.get('message', {})
                    if not isinstance(msg, dict): continue
                    sid = obj.get('sessionId', 'unknown')
                    cwd = obj.get('cwd', 'unknown')
                    ts = obj.get('timestamp', '')
                    s = sessions[sid]
                    if not s['cwd'] or s['cwd'] == 'unknown': s['cwd'] = cwd
                    if not s['first_ts'] or ts < s['first_ts']: s['first_ts'] = ts
                    if ts > s['last_ts']: s['last_ts'] = ts

                    # Token/model tracking
                    if 'model' in msg and 'usage' in msg:
                        model = msg['model']
                        if model == '<synthetic>': continue
                        usage = msg['usage']
                        m = s['models'][model]
                        m['input']       += usage.get('input_tokens', 0)
                        m['output']      += usage.get('output_tokens', 0)
                        m['cache_write'] += usage.get('cache_creation_input_tokens', 0)
                        m['cache_read']  += usage.get('cache_read_input_tokens', 0)
                        m['turns']       += 1
                        # Track first cache_creation as schema overhead proxy
                        cw = usage.get('cache_creation_input_tokens', 0)
                        if cw > 0 and s['first_cache_write'] is None:
                            s['first_cache_write'] = cw

                    # Track tool_use blocks for MCP analysis
                    content = msg.get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_use':
                                tool_name = block.get('name', '')
                                is_mcp = tool_name.startswith('mcp__')
                                s['tool_calls'].append({
                                    'name': tool_name,
                                    'id': block.get('id', ''),
                                    'is_mcp': is_mcp,
                                })
                                if is_mcp:
                                    s['uses_mcp'] = True

                elif otype == 'user':
                    msg = obj.get('message', {})
                    if not isinstance(msg, dict): continue
                    sid = obj.get('sessionId', 'unknown')
                    content = msg.get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_result':
                                tuid = block.get('tool_use_id', '')
                                rc = block.get('content', '')
                                sessions[sid]['tool_results'][tuid] = len(str(rc))
    except Exception:
        parse_failures += 1

# Enrich from session-meta
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
                # Fallback MCP detection from session-meta
                if meta.get('uses_mcp') and not sessions[sid]['uses_mcp']:
                    sessions[sid]['uses_mcp'] = True
        except Exception:
            pass

# Build results
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

    # Compute per-session MCP tool stats
    mcp_tools = defaultdict(lambda: {'calls': 0, 'total_result_size': 0})
    non_mcp_tools = defaultdict(lambda: {'calls': 0, 'total_result_size': 0})
    for tc in s['tool_calls']:
        result_size = s['tool_results'].get(tc['id'], 0)
        if tc['is_mcp']:
            mcp_tools[tc['name']]['calls'] += 1
            mcp_tools[tc['name']]['total_result_size'] += result_size
        else:
            non_mcp_tools[tc['name']]['calls'] += 1
            non_mcp_tools[tc['name']]['total_result_size'] += result_size

    # Compute aggregate result sizes
    mcp_total_result_size = sum(t['total_result_size'] for t in mcp_tools.values())
    mcp_total_calls = sum(t['calls'] for t in mcp_tools.values())
    non_mcp_total_result_size = sum(t['total_result_size'] for t in non_mcp_tools.values())
    non_mcp_total_calls = sum(t['calls'] for t in non_mcp_tools.values())

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
        'uses_mcp': s['uses_mcp'],
        'first_cache_write': s['first_cache_write'],
        'mcp_tools': {k: dict(v) for k, v in mcp_tools.items()},
        'non_mcp_tools': {k: dict(v) for k, v in non_mcp_tools.items()},
        'mcp_total_result_size': mcp_total_result_size,
        'mcp_total_calls': mcp_total_calls,
        'non_mcp_total_result_size': non_mcp_total_result_size,
        'non_mcp_total_calls': non_mcp_total_calls,
    })

# Read MCP configuration
mcp_config = {'user_servers': {}, 'plugin_servers': {}}
user_mcp_path = os.path.expanduser('~/.claude/mcp.json')
if os.path.isfile(user_mcp_path):
    try:
        with open(user_mcp_path) as f:
            user_mcp = json.load(f)
        for name, details in user_mcp.get('mcpServers', {}).items():
            mcp_config['user_servers'][name] = {
                'command': details.get('command', ''),
                'type': 'stdio' if 'command' in details else details.get('type', 'unknown'),
            }
    except Exception:
        pass

plugins_dir = os.path.expanduser('~/.claude/plugins')
if os.path.isdir(plugins_dir):
    for mcp_file in glob.glob(os.path.join(plugins_dir, '**', '.mcp.json'), recursive=True):
        try:
            with open(mcp_file) as f:
                plugin_mcp = json.load(f)
            plugin_name = os.path.basename(os.path.dirname(mcp_file))
            for name, details in plugin_mcp.get('mcpServers', {}).items():
                mcp_config['plugin_servers'][name] = {
                    'plugin': plugin_name,
                    'command': details.get('command', ''),
                    'type': 'stdio' if 'command' in details else details.get('type', 'unknown'),
                }
        except Exception:
            pass

if parse_failures > 0:
    print(f'Warning: {parse_failures} session files could not be parsed and were skipped.', file=sys.stderr)
print(json.dumps({'sessions': results, 'mcp_config': mcp_config}))
```

The script outputs JSON with two keys: `sessions` (list of session objects) and `mcp_config` (configured MCP servers). Save the stdout to a variable and parse it. If the script writes to stderr, surface that warning verbatim in the output. If the script fails entirely, report the error and stop.

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

#### Brief MCP Summary (when `--mcp` is NOT set)

If `--mcp` is NOT set but there are sessions with `uses_mcp: true`, append a brief summary after Trends:

```
MCP USAGE DETECTED
══════════════════
N of M sessions used MCP servers  |  MCP sessions avg cost: $X.XX  |  Non-MCP avg: $X.XX
Top MCP tools: mcp__glean-hosted__search (N calls), mcp__pencil__batch_get (N calls)

Run /cost-analysis --mcp for detailed MCP overhead analysis.
```

If no sessions used MCP, skip this section entirely.

---

#### MCP Analysis Sections (when `--mcp` IS set)

When the `--mcp` flag is present, replace the standard Top Sessions, Daily Spend, Token Cost Breakdown, Trends, and Model Recommendations sections with the following MCP-specific sections. Keep the Header, Project Breakdown, and Model Breakdown sections.

If `--mcp-server <name>` is set, filter all MCP data to only tools whose name contains that server name (e.g., `--mcp-server glean-hosted` filters to tools starting with `mcp__glean-hosted__`).

##### Section A: MCP Server Configuration

List all configured MCP servers from `mcp_config` and whether they were actually used in any session.

```
MCP SERVER CONFIGURATION
═══════════════════════════════════════════════════════════════════════════

  Source       Server              Type     Used?
  ─────────────────────────────────────────────────────────────────────
  user         excalidraw          stdio    No
  plugin       glean-hosted        stdio    Yes (14 sessions)
  plugin       pencil              stdio    Yes (3 sessions)
  plugin       linear              stdio    No

  Configured: 4 servers  |  Actually used: 2 servers
```

To determine "Used?" — check if any session has tool calls with names starting with `mcp__<server-name>__`. Count how many sessions used each server.

##### Section B: MCP Tool Usage Breakdown

Table of every MCP tool with call count and avg result size, grouped by server. Aggregate across all filtered sessions.

```
MCP TOOL USAGE BREAKDOWN
═══════════════════════════════════════════════════════════════════════════

  Server: glean-hosted
  Tool                                   Calls    Avg Result    Total Result
  ────────────────────────────────────────────────────────────────────────
  mcp__glean-hosted__search                 42       29.5K         1.2M
  mcp__glean-hosted__chat                   18       45.2K         813K
  mcp__glean-hosted__read_document          11       91.3K         1.0M
  mcp__glean-hosted__employee_search         5       12.1K          61K
  ────────────────────────────────────────────────────────────────────────
  Subtotal                                  76       40.6K         3.1M

  Server: pencil
  Tool                                   Calls    Avg Result    Total Result
  ────────────────────────────────────────────────────────────────────────
  mcp__pencil__batch_get                    12        8.3K         100K
  mcp__pencil__get_editor_state              3        2.1K           6K
  ────────────────────────────────────────────────────────────────────────
  Subtotal                                  15        7.1K         106K
```

Format sizes with K suffix for thousands, M for millions of characters.

##### Section C: Context Overhead Analysis

The key analysis section showing how MCP impacts costs.

```
CONTEXT OVERHEAD ANALYSIS
═══════════════════════════════════════════════════════════════════════════

  SCHEMA OVERHEAD (first cache_creation_input_tokens per session)
  ────────────────────────────────────────────────────────────────────────
  MCP sessions avg first cache write:       X,XXX,XXX tokens
  Non-MCP sessions avg first cache write:   X,XXX,XXX tokens
  Estimated schema overhead:                +XXX,XXX tokens  (+XX%)

  RESULT SIZE COMPARISON
  ────────────────────────────────────────────────────────────────────────
  Avg MCP tool result:       XX.XK chars
  Avg non-MCP tool result:    X.XK chars
  MCP results are XXXx larger than non-MCP results

  COST IMPACT
  ────────────────────────────────────────────────────────────────────────
  MCP sessions avg cost:       $XX.XX  (N sessions)
  Non-MCP sessions avg cost:    $X.XX  (N sessions)
  MCP sessions cost X.Xx more on average
```

**Computation notes:**
- Schema overhead = avg `first_cache_write` in MCP sessions minus avg `first_cache_write` in non-MCP sessions. Only include sessions where `first_cache_write` is not null.
- Result size comparison = total MCP result chars / total MCP calls vs total non-MCP result chars / total non-MCP calls. Only include sessions where tool results were tracked (result size > 0).
- Cost impact = avg `total_cost` of MCP sessions vs avg `total_cost` of non-MCP sessions.

##### Section D: MCP Sessions Detail

Table of sessions that used MCPs with their MCP-specific stats.

```
MCP SESSIONS
═══════════════════════════════════════════════════════════════════════════
Date         Project              Cost     MCP Calls   MCP Result Data   Prompt
──────────────────────────────────────────────────────────────────────────────────
2026-03-08   my-frontend        $47.23          12          1.4M         Build a new dashboard...
2026-03-05   my-api-project     $38.91          28          3.1M         Implement plan: rede...
```

Sort by cost descending. Apply `--top N` limit.

##### Section E: Optimization Recommendations

Rule-based recommendations. Check each condition and output matching recommendations.

```
MCP OPTIMIZATION RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════════════
```

| Condition | Recommendation |
|---|---|
| Configured servers > actually used servers | "You have N configured MCP servers but only used M. Remove unused servers (X, Y) to reduce schema overhead — each unused server still loads its full tool schema into context." |
| Avg MCP result size > 20K chars | "MCP tool results average XXK chars — that's large context consumption. Use more specific queries to reduce result sizes (e.g., narrow Glean searches, request fewer fields)." |
| Any single tool avg result > 50K chars | "Tool `mcp__X__Y` averages XXK chars per result — consider whether you need all that data or can use a more targeted query." |
| MCP sessions cost > 1.5x non-MCP sessions | "MCP sessions cost X.Xx more than non-MCP sessions on average. Consider using dedicated sessions for MCP-heavy work to avoid bloating your context in regular coding sessions." |
| Sessions use < 30% of tools from a loaded server | "You loaded N tools from server `X` but only used M (NN%). Consider if you need this server for most sessions, or load it only when needed." |

Format each as a bullet point with the condition context and the actionable recommendation.

If no recommendations match (unlikely), output: "No significant MCP overhead issues detected."

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
- **`--mcp` with no MCP sessions**: Show the MCP Server Configuration section (if servers are configured) and report "No sessions used MCP tools in the selected period." Skip sections B-E.
- **`--mcp-server` with unknown server**: Report "No MCP tools found for server 'X'. Available servers: A, B, C." and list servers that were actually used.
- **Missing MCP config files**: If `~/.claude/mcp.json` or plugin `.mcp.json` files don't exist, still show MCP analysis based on session data — just note "MCP config not found — showing usage data only."

## Notes on Data Accuracy

- **Cache tokens dominate costs**: `cache_creation_input_tokens` can be orders of magnitude larger than `input_tokens`. Always sum all four token types.
- **Session-meta vs project jsonl**: session-meta does not store cache token counts. Always read from project jsonl for accurate cost data.
- **Subagent sessions**: Subagent jsonl files under `<session>/subagents/agent-*.jsonl` contribute to the same `sessionId` and are attributed to the parent session's `cwd`.
