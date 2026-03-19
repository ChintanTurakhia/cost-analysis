# MCP Analysis Sections

When the `--mcp` flag is present, replace the standard Top Sessions, Daily Spend, Token Cost Breakdown, Trends, and Model Recommendations sections with the following MCP-specific sections. Keep the Header, Project Breakdown, and Model Breakdown sections.

If `--mcp-server <name>` is set, filter all MCP data to only tools whose name contains that server name (e.g., `--mcp-server glean-hosted` filters to tools starting with `mcp__glean-hosted__`).

## Section A: MCP Server Configuration

List all configured MCP servers from `mcp_config` and whether they were actually used in any session.

**Required data:** server source (user/plugin), server name, connection type, usage status (sessions count).

```
MCP SERVER CONFIGURATION
===========================================================================

  Source       Server              Type     Used?
  -------------------------------------------------------------------
  user         excalidraw          stdio    No
  plugin       glean-hosted        stdio    Yes (14 sessions)
  plugin       pencil              stdio    Yes (3 sessions)
  plugin       linear              stdio    No

  Configured: 4 servers  |  Actually used: 2 servers
```

To determine "Used?" — check if any session has tool calls with names starting with `mcp__<server-name>__`. Count how many sessions used each server.

## Section B: MCP Tool Usage Breakdown

Table of every MCP tool with call count and avg result size, grouped by server. Aggregate across all filtered sessions.

**Required data per row:** tool name, call count, avg result size, total result size.

```
MCP TOOL USAGE BREAKDOWN
===========================================================================

  Server: glean-hosted
  Tool                                   Calls    Avg Result    Total Result
  --------------------------------------------------------------------------
  mcp__glean-hosted__search                 42       29.5K         1.2M
  mcp__glean-hosted__chat                   18       45.2K         813K
  mcp__glean-hosted__read_document          11       91.3K         1.0M
  mcp__glean-hosted__employee_search         5       12.1K          61K
  --------------------------------------------------------------------------
  Subtotal                                  76       40.6K         3.1M

  Server: pencil
  Tool                                   Calls    Avg Result    Total Result
  --------------------------------------------------------------------------
  mcp__pencil__batch_get                    12        8.3K         100K
  mcp__pencil__get_editor_state              3        2.1K           6K
  --------------------------------------------------------------------------
  Subtotal                                  15        7.1K         106K
```

Format sizes with K suffix for thousands, M for millions of characters.

## Section C: Context Overhead Analysis

The key analysis section showing how MCP impacts costs.

**Required data:** avg first cache write for MCP vs non-MCP sessions, avg result sizes, avg session costs.

```
CONTEXT OVERHEAD ANALYSIS
===========================================================================

  SCHEMA OVERHEAD (first cache_creation_input_tokens per session)
  --------------------------------------------------------------------------
  MCP sessions avg first cache write:       X,XXX,XXX tokens
  Non-MCP sessions avg first cache write:   X,XXX,XXX tokens
  Estimated schema overhead:                +XXX,XXX tokens  (+XX%)

  RESULT SIZE COMPARISON
  --------------------------------------------------------------------------
  Avg MCP tool result:       XX.XK chars
  Avg non-MCP tool result:    X.XK chars
  MCP results are XXXx larger than non-MCP results

  COST IMPACT
  --------------------------------------------------------------------------
  MCP sessions avg cost:       $XX.XX  (N sessions)
  Non-MCP sessions avg cost:    $X.XX  (N sessions)
  MCP sessions cost X.Xx more on average
```

**Computation notes:**
- Schema overhead = avg `first_cache_write` in MCP sessions minus avg `first_cache_write` in non-MCP sessions. Only include sessions where `first_cache_write` is not null.
- Result size comparison = total MCP result chars / total MCP calls vs total non-MCP result chars / total non-MCP calls. Only include sessions where tool results were tracked (result size > 0).
- Cost impact = avg `total_cost` of MCP sessions vs avg `total_cost` of non-MCP sessions.

## Section D: MCP Sessions Detail

Table of sessions that used MCPs with their MCP-specific stats.

**Required data per row:** date, project, cost, MCP call count, MCP result data size, first prompt.

```
MCP SESSIONS
===========================================================================
Date         Project              Cost     MCP Calls   MCP Result Data   Prompt
---------------------------------------------------------------------------------
2026-03-08   my-frontend        $47.23          12          1.4M         Build a new dashboard...
2026-03-05   my-api-project     $38.91          28          3.1M         Implement plan: rede...
```

Sort by cost descending. Apply `--top N` limit.

## Section E: Optimization Recommendations

Rule-based recommendations. Check each condition and output matching recommendations as bullet points.

| Condition | Recommendation |
|---|---|
| Configured servers > actually used servers | "You have N configured MCP servers but only used M. Remove unused servers (X, Y) to reduce schema overhead — each unused server still loads its full tool schema into context." |
| Avg MCP result size > 20K chars | "MCP tool results average XXK chars — that's large context consumption. Use more specific queries to reduce result sizes (e.g., narrow Glean searches, request fewer fields)." |
| Any single tool avg result > 50K chars | "Tool `mcp__X__Y` averages XXK chars per result — consider whether you need all that data or can use a more targeted query." |
| MCP sessions cost > 1.5x non-MCP sessions | "MCP sessions cost X.Xx more than non-MCP sessions on average. Consider using dedicated sessions for MCP-heavy work to avoid bloating your context in regular coding sessions." |
| Sessions use < 30% of tools from a loaded server | "You loaded N tools from server `X` but only used M (NN%). Consider if you need this server for most sessions, or load it only when needed." |

If no recommendations match (unlikely), output: "No significant MCP overhead issues detected."
