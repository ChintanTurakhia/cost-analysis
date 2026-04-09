# Cost Savings Recommendations

Detection rules, thresholds, and output templates for the "COST SAVINGS OPPORTUNITIES" report section. This section appears after Cache Efficiency and before Model Recommendations. Show the section only when at least one recommendation triggers.

## How It Works

1. Evaluate each recommendation category against session data
2. Compute estimated savings for each triggered recommendation
3. Sort by estimated savings descending
4. Show TOP 3 ACTIONS summary + up to 8 detailed recommendations
5. Skip recommendations with < $1 estimated savings

## Output Template

```
COST SAVINGS OPPORTUNITIES
================================================================
Estimated total savings: $XX.XX/month (based on your usage patterns)

TOP 3 ACTIONS
1. [Highest savings action] — saves ~$XX
2. [Second highest] — saves ~$XX
3. [Third highest] — saves ~$XX

[Detailed recommendation blocks below, sorted by savings]
```

---

## Recommendation Categories

### A1. Context Bloat Detection

**Priority:** HIGH

**Trigger:** At least 3 sessions where `cost_second_half > 2.5 * cost_first_half`

**Data needed:** `cost_first_half`, `cost_second_half`, `context_growth_ratio`, `turns`, `first_prompt` per session

**Savings formula:** `sum(cost_second_half - cost_first_half) * 0.3` for sessions with >2.5x ratio

**Template:**
```
CONTEXT GROWTH
Your sessions show accelerating costs as context grows:
- N sessions had second-half costs 2.5x+ higher than first-half
- Average context growth ratio: X.Xx (last turn vs first turn cache size)
- Worst: "PROMPT..." grew from $X.XX/turn to $X.XX/turn over NN turns

ACTION:
  1. Run /compact every 20 turns to compress context
  2. If your session exceeds 25 turns, start a new one — paste a 2-3 line
     summary of where you left off instead of carrying all prior context
  3. Use /clear between unrelated tasks in the same session
  4. Check turn count with /cost — if it's climbing, compress or restart

Estimated savings: ~$XX.XX
```

---

### A2. Session Fragmentation

**Priority:** HIGH

**Trigger:** Any (project, date) group with 3+ sessions AND average turns < 5

**Data needed:** Group sessions by `project` + `date`. Per group: session count, average `turns`, `first_cache_write` per session

**Savings formula:** For each flagged group: `(session_count - 1) * avg(first_cache_write) * cache_write_rate / 1_000_000`. Sum across all groups.

**Template:**
```
SESSION FRAGMENTATION
You opened multiple short sessions for the same project on the same day:
- PROJECT: N sessions on DATE (avg M turns each), N-1 redundant cold starts = ~$X.XX wasted
[repeat for each flagged group, max 5]

ACTION:
  1. Before opening Claude Code, list all related tasks you need done
  2. Open one session and work through them sequentially
  3. Use /clear between subtasks instead of quitting and reopening
  4. Each new session pays a cold-start tax (~$X.XX) — staying in one
     session avoids paying it repeatedly

Estimated savings: ~$XX.XX
```

---

### A3. Idle Gap Cache Expiry

**Priority:** MEDIUM

**Trigger:** Total `inter_turn_gaps` across all sessions > 3 AND total `rewrite_cost` > $5

**Data needed:** `inter_turn_gaps` per session (list of gaps with `gap_seconds`, `rewrite_cost`)

**Savings formula:** `sum(all rewrite_cost across all gaps) * 0.5`

**Template:**
```
IDLE GAP CACHE EXPIRY
Cache expires after 5 minutes of inactivity. Resuming pays a full context
re-write. Detected N idle gaps (>5 min) across M sessions:
- Total estimated re-write cost from idle gaps: $XX.XX
- Worst: "PROMPT..." had N gaps totaling Xm -> $X.XX in re-writes

ACTION:
  1. If stepping away for >5 minutes, run /compact first — this preserves
     key context at a fraction of the re-cache cost
  2. If stepping away for >30 minutes, finish your current task and close
     the session — starting fresh is cheaper than re-caching 100K+ tokens
  3. When returning after a break, start a new session with a focused prompt
     ("continue implementing X in file Y") rather than resuming stale context

Estimated savings: ~$XX.XX
```

---

### A4. Optimal Session Length

**Priority:** LOW

**Trigger:** 3+ sessions with > 30 turns

**Data needed:** `turns`, `avg_turn_cost`, `max_turn_cost` per session

**Template:**
```
SESSION LENGTH
Your longest sessions show diminishing returns:
- N sessions exceeded 30 turns
- Before turn 20: avg $X.XX/turn | After turn 20: avg $X.XX/turn
- Longest session: NN turns, $XX.XX total

ACTION:
  1. Run /compact after completing each subtask (not just at the end)
  2. After 25-30 turns, start a new session — paste a 2-3 line summary
     of where you left off. This is cheaper than carrying 30 turns of context.
  3. Check your running cost with /cost — if $/turn is climbing, it's time
     to compress or restart
```

No explicit savings formula — this is informational. Reference savings from A1.

---

### B1. Conversation Tennis

**Priority:** HIGH

**Trigger:** 3+ sessions where `user_text_turns > 8` AND `total_cost > $5`

**Data needed:** `user_text_turns`, `total_cost`, `turns`, `first_prompt` per session. Also compute across all sessions: average `user_text_turns`.

**Savings formula:** For flagged sessions: `(user_text_turns - 4) * avg_turn_cost * 0.5`. Sum across all flagged sessions.

**Template:**
```
PROMPTING EFFICIENCY
Some sessions have many back-and-forth exchanges:
- Avg user messages per session: X.X (all sessions)
- Sessions with 10+ user messages cost X.Xx more than sessions with <5
- High-interaction: "PROMPT..." (N user turns, $XX), "PROMPT..." (N turns, $XX)

ACTION: Invest 30 seconds in a detailed first prompt. Include:
  - Specific outcome (not general direction)
  - Constraints ("use existing auth middleware", "match pattern in user.ts")
  - File paths if known
  - What NOT to do ("don't refactor surrounding code")
A clear prompt can cut session cost by 50%+ by eliminating correction turns.

Estimated savings: ~$XX.XX
```

---

### B2. Output Verbosity

**Priority:** MEDIUM

**Trigger:** 3+ sessions where output token cost > 25% of total session cost

**Data needed:** Per session: `output_tokens`, `total_cost`. Compute `output_cost` using per-model output rate. Compute `output_cost_ratio = output_cost / total_cost`.

**Savings formula:** For flagged sessions: `(output_cost - total_cost * 0.15) * 0.4`. Sum across flagged sessions.

**Template:**
```
OUTPUT VERBOSITY
Output tokens cost 5x more than input ($25/M vs $5/M for Opus):
- N sessions had output costs > 25% of total session cost
- Avg output per turn: X,XXX tokens (all sessions)
- Highest: "PROMPT..." — X,XXX tokens/turn avg

ACTION: Add to your prompts or CLAUDE.md:
  - "Be concise — skip explanations unless asked"
  - "Don't add comments unless logic is non-obvious"
  - "Don't summarize what you just did"

Estimated savings: ~$XX.XX
```

---

### B3. CLAUDE.md Impact

**Priority:** LOW

**Trigger:** At least 2 projects with sessions AND measurable difference (>20%) in avg cost-per-session between projects with/without CLAUDE.md

**Data needed:** Per project: check if CLAUDE.md exists at the project path. Group sessions by has_claude_md / no_claude_md. Compare avg cost, avg turns.

**Note:** This requires checking the filesystem. The LLM should check for CLAUDE.md at the `cwd` path of each project using Bash.

**Template:**
```
PROJECT SETUP
Projects with CLAUDE.md files show more efficient sessions:
- With CLAUDE.md: avg $X.XX/session, X turns
- Without: avg $X.XX/session, X turns (XX% more expensive)

ACTION: Add a CLAUDE.md to projects without one. Start with this template:

  # Project
  Brief description of what this project does

  # Stack
  Language, framework, package manager

  # Conventions
  Naming patterns, file organization, key abstractions

  # Key Files
  Entry points, config locations, important modules

  Even 5 lines reduces exploration and correction turns significantly.
```

---

### C1. Repeated File Reads

**Priority:** HIGH

**Trigger:** 3+ sessions with `duplicate_reads > 0`, OR any session with a file read 4+ times

**Data needed:** `read_file_counts` (files read 2+ times), `duplicate_reads` per session

**Savings formula:** Estimate 2K tokens per duplicate read (conservative file size). `total_duplicate_reads * 2000 * cache_write_rate / 1_000_000`. Use the dominant model's cache write rate.

**Template:**
```
REPEATED FILE READS
Some sessions re-read the same files, inflating context:
- N sessions had duplicate file reads
- Total duplicate reads: M across all sessions
- Top repeated: FILE (read Nx), FILE (read Nx)

ACTION: Reference files by name instead of re-reading — Claude remembers
files from earlier in the session. Say "in the handler.ts you read earlier"
instead of asking to read it again. Use /compact if context feels stale.

Estimated savings: ~$XX.XX
```

---

### C2. Large Tool Outputs

**Priority:** MEDIUM

**Trigger:** 5+ total `large_tool_results` across all sessions (results > 20K chars)

**Data needed:** `large_tool_results` per session (list of {tool, size})

**Savings formula:** Estimate that 50% of large output could have been avoided. `sum(size for all large results) * 0.5 / 4 * cache_write_rate / 1_000_000` (divide by 4 for chars-to-tokens approximation).

**Template:**
```
LARGE TOOL OUTPUTS
Large tool results inflate context and cache write costs:
- N tool results exceeded 20K characters across M sessions
- Largest: TOOL — XXK chars | TOOL — XXK chars
- By tool: Bash avg XXK, Read avg XXK

ACTION:
  - Bash: pipe through "| head -50" or "| tail -20"
  - Read: use specific line ranges instead of whole files
  - Grep: use targeted patterns, avoid broad searches
  - Add to CLAUDE.md: "Limit bash output to relevant lines"

Estimated savings: ~$XX.XX
```

---

### C3. Exploration Storms

**Priority:** LOW

**Trigger:** 3+ sessions where the tool_calls list contains a streak of 10+ consecutive Read/Grep/Glob calls (tool names matching Read, Grep, Glob, Bash with grep-like commands)

**Note:** Detection requires analyzing the `tool_calls` array order. Count consecutive exploration tools (Read, Grep, Glob) without an Edit, Write, or the session ending.

**Template:**
```
EXPLORATION OVERHEAD
Some sessions spent many turns exploring before acting:
- N sessions had 10+ consecutive Read/Grep/Glob calls
- Avg exploration streak: NN calls

ACTION: Help Claude find what it needs faster:
  - Provide file paths in your prompt when you know them
  - Use "the function is in src/api/handler.ts around line 50"
  - Use plan mode (/plan) for read-only exploration
  - Use /clear after exploration to shed context before implementing
```

---

### D1. Cost Concentration (Pareto)

**Priority:** HIGH — always show if there are 10+ sessions

**Trigger:** 10+ sessions total

**Data needed:** All sessions sorted by `total_cost` descending

**Template:**
```
COST CONCENTRATION
- Top 10% of sessions (N) account for XX% of total cost ($XXX)
- Your most expensive session: $XX.XX (XX% of total)
- Optimizing your top 5 sessions alone could save ~$XX

ACTION:
  1. Re-run with --project PROJECT for your most expensive project to
     get targeted recommendations specific to that project
  2. Review the top sessions table — identify which ones were avoidably
     expensive (wrong model, too many turns, idle gaps)
  3. Apply the other recommendations in this report to your top 5 sessions
     first for maximum impact
```

**Savings formula:** `sum(top_10_pct_session_costs) * 0.3` — assumes 30% reduction possible on concentrated expensive sessions.

---

### D2. Cost-Per-Turn Efficiency

**Priority:** MEDIUM

**Trigger:** 3+ projects with 3+ sessions each AND > 2x spread in $/turn

**Data needed:** Per project: `total_cost / total_turns` across all sessions

**Template:**
```
EFFICIENCY BY PROJECT
Cost per turn varies across your projects:
  Project                 $/turn    Sessions    Avg Turns
  PROJECT                  $X.XX        NN         NN
  [sorted by $/turn descending, max 8 rows]

ACTION: Compare your most and least efficient projects:
  - Common differences: model choice (Opus vs Sonnet), CLAUDE.md presence,
    prompt specificity, session length
  - Your most efficient project costs Xx less per turn — check if it uses
    Sonnet, has a CLAUDE.md, or uses shorter sessions
  - Apply the same patterns to your most expensive projects
```

---

### E1. Session Management Commands

**Priority:** HIGH — always show unless the user has evidence of /compact usage

**Trigger:** Always show if no sessions contain `compact_boundary` system messages (detected by the `compacted` field if available). If unsure, always show.

**Template:**
```
SESSION MANAGEMENT COMMANDS
Claude Code has built-in tools to manage context and costs:

  /clear    — Wipe conversation history. Use between unrelated tasks. Free.
  /compact  — Compress conversation, keeping key context. Reduces tokens 50-70%.
  /model    — Switch models mid-session. Opus for complex work, Sonnet for
              follow-ups, Haiku for quick checks.
  /cost     — Check running token usage for the current session.

Regular /compact usage in long sessions could save an estimated $XX.XX/month.
```

**Savings formula for /compact estimate:** For sessions with > 15 turns: `cost_second_half * 0.4`. Sum across those sessions, divide by period in months.

---

### E2. First-Prompt Patterns

**Priority:** LOW

**Trigger:** 10+ sessions with `first_prompt` data AND measurable correlation between prompt length and cost

**Data needed:** Group sessions by `first_prompt` length: short (< 30 chars), medium (30-100 chars), long (> 100 chars). Compare avg cost and avg turns.

**Template:**
```
PROMPT LENGTH vs SESSION COST
- Short prompts (<30 chars): avg $X.XX/session, avg NN turns
- Detailed prompts (>100 chars): avg $X.XX/session, avg NN turns

Detailed first prompts correlate with XX% lower session costs.

ACTION:
  1. Before starting a session, draft your prompt in a text editor first
  2. Include: what you want built, which files to modify, constraints,
     and what NOT to change
  3. Example of a good first prompt:
     "Add pagination to the /api/users endpoint in src/routes/users.ts.
     Use cursor-based pagination matching the pattern in orders.ts.
     Don't modify the database schema."
  4. This eliminates 3-5 correction turns that each cost $X.XX+
```

---

### F1. Static Context Overhead

**Priority:** HIGH — one-time fix with compounding returns on every future turn

**Trigger:** Median `first_cache_write` > 30,000 tokens across 5+ sessions

**Data needed:** `first_cache_write` from every session. Compute the median. Also need `total_turns` (sum across all sessions) and the dominant model's `cache_write_rate`.

**Savings formula:** `(median_first_cache_write - 20000) * total_turns * cache_write_rate / 1_000_000`

The 20K baseline is roughly what a lean Claude Code session loads (system prompt + minimal tool definitions). Anything above that is likely tool schema or skill/plugin bloat that gets re-processed on every turn.

**Template:**
```
STATIC CONTEXT OVERHEAD
Your sessions start with a high baseline context before you even type anything:
- Median first-turn cache write: XX,XXX tokens (healthy baseline: ~20K)
- Estimated excess: XX,XXX tokens × N total turns = XXM tokens wasted
- Estimated cost of excess context: $XX.XX

This typically means tool schemas and plugin/skill definitions are being loaded
into every turn whether you use them or not.

ACTION:
  1. Enable tool search — add to settings.json:
     "ENABLE_TOOL_SEARCH": "true"
     This defers tool schema loading until needed, cutting baseline context
     from ~45K to ~20K tokens instantly.
  2. Audit installed plugins — run: claude plugins list
     Uninstall plugins you rarely use. Each unused plugin adds its skill
     schemas to every turn.

Estimated savings: ~$XX.XX
```

---

### G1. Quadratic Session Detection

**Priority:** HIGH

**Trigger:** At least 1 session with `turns > 500` AND `cache_write_tokens > 50_000_000` (50M tokens)

**Data needed:** `turns`, `cache_write_tokens`, `total_cost`, `avg_turn_cost`, `first_prompt` per session

**Savings formula:** For each flagged session: `total_cost * (1 - sqrt(turns) / turns)`. Sum across all flagged sessions.

This estimates the quadratic overhead: in a session with N turns, each turn re-sends all prior context, so total cost scales as O(N²). If the same work were split into sqrt(N) independent sessions of sqrt(N) turns each, total cost would scale as O(N). The formula captures the difference.

**Template:**
```
QUADRATIC SESSION GROWTH
Some sessions have so many turns that costs grow quadratically — each turn
re-sends all prior context, so total cost scales as O(N²) with turn count:
- N sessions exceeded 500 turns with 50M+ cache write tokens
- Worst: "PROMPT..." — NNN turns, $XX.XX total, $X.XX avg/turn
- Estimated quadratic overhead: $XX.XX (cost beyond linear scaling)

These sessions may contain independent or parallelizable work packed into a
single conversation. Consider whether subtasks could run as separate sessions
or subagents — if each page, component, or test is independent, there's no
reason to carry prior context forward.

ACTION: Ask yourself: does step 50 need to know about step 1? If not,
split the work:
  1. Batch into independent sessions — e.g., "Process files 1-20" in one
     session, "21-40" in another. Each starts with fresh, cheap context.
  2. Use subagents for parallel work — tell Claude: "spawn a subagent for
     each component" so each gets its own context window
  3. If work must be sequential, run /compact every 20-30 turns to reset
     the growth curve before it gets expensive
  4. Use /cost to monitor — if $/turn exceeds $1, it's time to split

Estimated savings: ~$XX.XX
```

---

## Priority Ordering

When multiple recommendations trigger, sort by estimated savings. If savings are equal, use this priority:

1. E1 (Session Management Commands) — always high value, educational
2. A1 (Context Bloat)
3. G1 (Quadratic Session Detection) — architectural fix, highest per-session savings
4. F1 (Static Context Overhead) — one-time fix, compounding returns
5. A2 (Session Fragmentation)
6. B1 (Conversation Tennis)
7. D1 (Cost Concentration)
8. C1 (Repeated File Reads)
9. A3 (Idle Gap Cache Expiry)
10. B2 (Output Verbosity)
11. C2 (Large Tool Outputs)
12. D2 (Cost-Per-Turn Efficiency)
13. A4 (Session Length)
14. C3 (Exploration Storms)
15. B3 (CLAUDE.md Impact)
16. E2 (First-Prompt Patterns)

## Notes

- All savings estimates use a conservative discount factor (0.3-0.5) to avoid overpromising
- Show at most 8 recommendations to avoid overwhelming the user
- Skip any recommendation with < $1 estimated savings
- The TOP 3 ACTIONS summary should be actionable and specific, not generic
- Use actual session data (prompts, costs, projects) in examples — don't use placeholder names
