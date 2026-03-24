# Gotchas

Known failure modes and edge cases. Read this before generating output.

- **`<synthetic>` model entries**: Some session lines have `model: "<synthetic>"`. Always skip these — they have no real token usage and will cause pricing lookup failures.

- **Missing cache token fields**: Older Claude Code versions didn't write `cache_creation_input_tokens` or `cache_read_input_tokens`. Treat missing fields as 0, don't error.

- **Subagent double-counting**: Subagent jsonl files live under `<session>/subagents/`. The Python script already attributes them to the parent session's `sessionId`. Don't count them as separate sessions.

- **Empty or corrupt jsonl lines**: Session files can have blank lines or malformed JSON. The script uses `errors='replace'` and skips bad lines — surface the count as a warning but don't fail.

- **Large session counts (500+)**: The Python script output grows linearly with session count. At 500+ sessions, the JSON payload can exceed 500KB. Always recommend `--days N` to users with large histories. Use `--max-sessions N` as a hard cap — the script will truncate the oldest sessions and set `truncated: true` in the JSON root. Note that truncation may skew aggregates since it drops older (not random) sessions.

- **Session-meta missing cache tokens**: The `session-meta/*.json` files only have `input_tokens` and `output_tokens` — never use these for cost calculation. Always use the project jsonl files.

- **Live pricing fetch fragility**: The WebFetch → pricing page parsing depends on the page's HTML structure. If Anthropic redesigns the page, the fetch will succeed but extraction will fail. The fallback check (>= 3 models extracted) catches this.

- **Model ID format changes**: New Claude models may use different ID formats. The prefix-based fallback (`claude-opus-*`, etc.) handles this, but truly new families (e.g., `claude-nova-*`) will silently get Opus pricing. Flag unknown model families in output.
