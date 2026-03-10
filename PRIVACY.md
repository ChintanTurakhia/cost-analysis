# Privacy Policy

**Last updated: March 2026**

## Overview

The cost-analysis Claude Code plugin does not collect, store, or transmit any personal data.

## Data Access

This plugin reads local files on your own machine to analyze Claude Code session data:

- `~/.claude/projects/**/*.jsonl` — session token usage logs
- `~/.claude/usage-data/session-meta/*.json` — session metadata
- `~/.claude/history.jsonl` — session prompt history

All data remains on your machine. No data is sent to any external server.

## External Requests

The plugin makes read-only HTTP requests to public pricing websites to fetch current model pricing:

- `https://llmpricecheck.com/` — LLM pricing reference
- `https://sanand0.github.io/llmpricing/` — LLM pricing reference

No user data is included in these requests.

## Contact

For questions, open an issue at https://github.com/ChintanTurakhia/cost-analysis/issues
