---
name: weekly-reminder
description: Remind to run cost analysis if it's been 7+ days since the last run
event: SessionStart
tools: Read, Bash
---

Check if `${CLAUDE_PLUGIN_DATA}/run-history.jsonl` exists. If it does, read the last line and check the `date` field. If the last run was 7 or more days ago, output a brief message:

"It's been {N} days since your last cost analysis (${last_total_cost} across {last_session_count} sessions). Run `/cost-analysis:analyze --days 7` for an update."

If the file doesn't exist or is empty, do nothing — the user hasn't run the skill yet.

Do NOT run the analysis automatically. Just suggest it.
