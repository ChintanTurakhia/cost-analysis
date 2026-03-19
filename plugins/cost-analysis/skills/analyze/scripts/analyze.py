#!/usr/bin/env python3
"""Claude Code session cost analyzer.

Reads ~/.claude/projects/**/*.jsonl to extract per-turn model and token data,
computes costs using Anthropic pricing (including prompt caching tokens), and
outputs structured JSON for report generation.

Usage:
    python3 analyze.py
    python3 analyze.py --pricing-json '{"claude-opus-4-6": [5.0, 25.0, 6.25, 0.5]}'
"""
import json, os, glob, sys, argparse
from collections import defaultdict

# ---------------------------------------------------------------------------
# Pricing defaults (overridden at runtime via --pricing-json if available)
# Format: { 'model-id': (input_per_1M, output_per_1M, cache_write_per_1M, cache_read_per_1M) }
# ---------------------------------------------------------------------------
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


def apply_pricing_overrides(pricing_json_str):
    """Override PRICING dict from a JSON string passed via --pricing-json.

    Expected format: {"model-id": [input, output, cache_write, cache_read], ...}
    Also updates PREFIX_PRICING and DEFAULT_PRICING based on the latest rates.
    """
    global PRICING, PREFIX_PRICING, DEFAULT_PRICING
    try:
        overrides = json.loads(pricing_json_str)
        for model_id, rates in overrides.items():
            if isinstance(rates, list) and len(rates) == 4:
                PRICING[model_id] = tuple(rates)

        # Update prefix pricing with latest rates for each family
        family_latest = {}
        for model_id, rates in PRICING.items():
            for prefix, _ in PREFIX_PRICING:
                if model_id.lower().startswith(prefix):
                    family_latest[prefix] = tuple(rates)
                    break

        if family_latest:
            PREFIX_PRICING = [
                (prefix, family_latest.get(prefix, rates))
                for prefix, rates in PREFIX_PRICING
            ]

        # Default to latest Opus rate
        if 'claude-opus' in family_latest:
            DEFAULT_PRICING = family_latest['claude-opus']
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f'Warning: Failed to parse --pricing-json: {e}', file=sys.stderr)


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


def main():
    parser = argparse.ArgumentParser(description='Analyze Claude Code session costs')
    parser.add_argument('--pricing-json', type=str, default=None,
                        help='JSON string of pricing overrides: {"model-id": [input, output, cache_write, cache_read]}')
    args = parser.parse_args()

    if args.pricing_json:
        apply_pricing_overrides(args.pricing_json)

    sessions = defaultdict(lambda: {
        'cwd': 'unknown', 'first_ts': '', 'last_ts': '',
        'models': defaultdict(lambda: {'input': 0, 'output': 0, 'cache_write': 0, 'cache_read': 0, 'turns': 0}),
        'first_prompt': '', 'duration_minutes': 0,
        'first_cache_write': None,
        'tool_calls': [],
        'tool_results': {},
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
                    if not line:
                        continue
                    obj = json.loads(line)
                    otype = obj.get('type')

                    if otype == 'assistant':
                        msg = obj.get('message', {})
                        if not isinstance(msg, dict):
                            continue
                        sid = obj.get('sessionId', 'unknown')
                        cwd = obj.get('cwd', 'unknown')
                        ts = obj.get('timestamp', '')
                        s = sessions[sid]
                        if not s['cwd'] or s['cwd'] == 'unknown':
                            s['cwd'] = cwd
                        if not s['first_ts'] or ts < s['first_ts']:
                            s['first_ts'] = ts
                        if ts > s['last_ts']:
                            s['last_ts'] = ts

                        # Token/model tracking
                        if 'model' in msg and 'usage' in msg:
                            model = msg['model']
                            if model == '<synthetic>':
                                continue
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
                        if not isinstance(msg, dict):
                            continue
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
            if not fname.endswith('.json'):
                continue
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


if __name__ == '__main__':
    main()
