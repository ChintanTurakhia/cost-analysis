# Pricing Reference

Pricing is fetched live from Anthropic's pricing page before each run (see Step 1 in SKILL.md). If the fetch fails, the hardcoded fallback rates below are used. All rates are per 1M tokens. Cache write = 1.25x input (5-minute cache), cache read = 0.1x input.

## Hardcoded Fallback Rates

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

## Model ID Mapping

Maps human-readable names on the Anthropic pricing page to API model IDs used in session data:

| Page Name          | API Model ID                    |
|--------------------|---------------------------------|
| Claude Opus 4.6    | `claude-opus-4-6`               |
| Claude Opus 4.5    | `claude-opus-4-5-20251101`      |
| Claude Opus 4.1    | `claude-opus-4-1-20250805`      |
| Claude Opus 4      | `claude-opus-4-20250514`        |
| Claude Sonnet 4.6  | `claude-sonnet-4-6`             |
| Claude Sonnet 4.5  | `claude-sonnet-4-5-20250929`    |
| Claude Sonnet 4    | `claude-sonnet-4-20250514`      |
| Claude Haiku 4.5   | `claude-haiku-4-5-20251001`     |

## Prefix-Based Fallback

Unknown models use prefix-based matching:
- `claude-opus-*` → Opus 4.6 rate
- `claude-sonnet-*` → Sonnet rate
- `claude-haiku-*` → Haiku rate

Truly unrecognized models default to Opus 4.6 pricing as a conservative estimate.

## Cache Tokens

The `cache_creation_input_tokens` field in usage data represents tokens written to the prompt cache. These are the dominant cost driver in long Claude Code sessions. Always include them in cost calculations.
