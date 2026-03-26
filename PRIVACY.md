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

The plugin makes a read-only HTTP request to Anthropic's public pricing page to fetch current model pricing:

- `https://platform.claude.com/docs/en/about-claude/pricing` — Anthropic's official model pricing page

No user data is included in this request.

## Contact

For questions, open an issue at https://github.com/ChintanTurakhia/cost-analysis/issues
