# Changelog

## v1.2.0

- Add `--since` / `--until` date range flags (filtering runs in the Python script before JSON output)
- Add `--max-sessions N` hard cap with truncation warning in JSON output
- Add `--save [path]` flag to export report to a markdown file
- Add `--budget N` flag for monthly spend tracking with pace and status line in header
- Add cost-per-hour (`$/hr`) metric to header and PROJECT BREAKDOWN table
- Add model recommendations disclaimer about heuristic classification
- Stronger evals with structural assertions (exact section headers, column names, negative assertions)
- Unit tests for `analyze.py` (8 test cases covering filtering, aggregation, and edge cases)
- Document `--max-sessions` in gotchas.md

## v1.1.0

- Run history with vs-last-run comparison in report header
- Weekly reminder hook (surfaces a prompt at session start if 7+ days since last analysis)
- Fix `CLAUDE_PLUGIN_DATA` fallback to `~/.claude/cost-analysis-data`

## v1.0.0

- Initial release
- Project breakdown, top sessions, model breakdown, daily spend chart
- Token cost breakdown (cache write / cache read / output / input)
- Model recommendations (Opus vs Sonnet classification by task type)
- MCP server overhead analysis (`--mcp`, `--mcp-server`)
- Live pricing fetch from Anthropic's pricing page with hardcoded fallback
- WebFetch-based pricing with structured extraction
