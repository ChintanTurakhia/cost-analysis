#!/usr/bin/env python3
"""Unit tests for analyze.py.

Run with:
    python3 -m pytest plugins/cost-analysis/skills/analyze/tests/ -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts dir to path so we can import module-level functions directly
SCRIPTS_DIR = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))
import analyze  # noqa: E402

ANALYZE_SCRIPT = str(SCRIPTS_DIR / 'analyze.py')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_analyze(*args, fake_home=None):
    """Run analyze.py as a subprocess, optionally with a fake HOME dir."""
    cmd = [sys.executable, ANALYZE_SCRIPT] + list(args)
    env = os.environ.copy()
    if fake_home:
        env['HOME'] = str(fake_home)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


def make_assistant_turn(session_id, cwd, model='claude-sonnet-4-6',
                        input_tokens=100, output_tokens=50,
                        cache_write_tokens=0, cache_read_tokens=0,
                        timestamp='2026-03-15T10:00:00Z',
                        tool_names=None, tool_uses=None):
    """Return a list of JSONL line strings representing one assistant turn.

    tool_uses overrides tool_names when provided. Each entry is a dict with
    'name', 'id', and optionally 'input' (for Read file_path tracking etc).
    """
    usage = {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
    }
    if cache_write_tokens:
        usage['cache_creation_input_tokens'] = cache_write_tokens
    if cache_read_tokens:
        usage['cache_read_input_tokens'] = cache_read_tokens

    content = []
    if tool_uses:
        for tu in tool_uses:
            block = {'type': 'tool_use', 'name': tu['name'], 'id': tu['id']}
            if 'input' in tu:
                block['input'] = tu['input']
            content.append(block)
    elif tool_names:
        for name in tool_names:
            content.append({'type': 'tool_use', 'name': name, 'id': f'tool_{name}'})

    turn = {
        'type': 'assistant',
        'sessionId': session_id,
        'cwd': cwd,
        'timestamp': timestamp,
        'message': {
            'model': model,
            'usage': usage,
            'content': content,
        },
    }
    return [json.dumps(turn)]


def make_user_text_turn(session_id, text='hello'):
    """Return a JSONL line for a user text message."""
    turn = {
        'type': 'user',
        'sessionId': session_id,
        'message': {
            'role': 'user',
            'content': text,
        },
    }
    return [json.dumps(turn)]


def make_user_tool_result(session_id, tool_use_id, content='result', size=None):
    """Return a JSONL line for a user tool_result message."""
    rc = content if size is None else 'x' * size
    turn = {
        'type': 'user',
        'sessionId': session_id,
        'message': {
            'role': 'user',
            'content': [
                {'type': 'tool_result', 'tool_use_id': tool_use_id, 'content': rc}
            ],
        },
    }
    return [json.dumps(turn)]


def write_sessions(projects_dir, lines, filename='test-session.jsonl'):
    """Write JSONL lines to a file inside projects_dir."""
    Path(projects_dir).mkdir(parents=True, exist_ok=True)
    fpath = Path(projects_dir) / filename
    fpath.write_text('\n'.join(lines))
    return fpath


# ---------------------------------------------------------------------------
# Tests that import analyze functions directly
# ---------------------------------------------------------------------------

class TestCacheTokenParsing(unittest.TestCase):
    """cache_creation_input_tokens must be included in cost computation."""

    def test_cache_write_tokens_add_cost(self):
        # Sonnet cache_write rate = $3.75 / 1M tokens
        cost_with_cache = analyze.token_cost(
            'claude-sonnet-4-6', inp=0, out=0, cache_write=1_000_000, cache_read=0)
        cost_no_cache = analyze.token_cost(
            'claude-sonnet-4-6', inp=0, out=0, cache_write=0, cache_read=0)
        self.assertGreater(cost_with_cache, cost_no_cache)
        self.assertAlmostEqual(cost_with_cache, 3.75, places=2)

    def test_cache_read_tokens_add_cost(self):
        # Sonnet cache_read rate = $0.30 / 1M tokens
        cost = analyze.token_cost(
            'claude-sonnet-4-6', inp=0, out=0, cache_write=0, cache_read=1_000_000)
        self.assertAlmostEqual(cost, 0.30, places=2)


class TestPricingJsonOverride(unittest.TestCase):
    """--pricing-json flag rates must override hardcoded defaults."""

    # Save and restore global state around each test
    def setUp(self):
        self._orig_pricing = dict(analyze.PRICING)
        self._orig_prefix = list(analyze.PREFIX_PRICING)
        self._orig_default = analyze.DEFAULT_PRICING

    def tearDown(self):
        analyze.PRICING = self._orig_pricing
        analyze.PREFIX_PRICING = self._orig_prefix
        analyze.DEFAULT_PRICING = self._orig_default

    def test_override_updates_known_model(self):
        override = json.dumps({'claude-sonnet-4-6': [1.0, 5.0, 1.25, 0.10]})
        analyze.apply_pricing_overrides(override)
        rates = analyze.get_pricing('claude-sonnet-4-6')
        self.assertEqual(rates[0], 1.0)
        self.assertEqual(rates[1], 5.0)
        self.assertEqual(rates[2], 1.25)
        self.assertEqual(rates[3], 0.10)

    def test_invalid_json_does_not_crash(self):
        # Bad JSON string should emit a warning but not raise
        analyze.apply_pricing_overrides('not-json')
        # PRICING should be unchanged
        self.assertIn('claude-sonnet-4-6', analyze.PRICING)


# ---------------------------------------------------------------------------
# Tests that run analyze.py as a subprocess with a fake HOME directory
# ---------------------------------------------------------------------------

class TestMcpToolDetection(unittest.TestCase):
    """Tools prefixed mcp__ must set uses_mcp: true on the session."""

    def test_mcp_prefix_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = make_assistant_turn(
                'sess-mcp-001', '/proj',
                tool_names=['mcp__glean-hosted__search'])
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            by_id = {s['session_id']: s for s in data['sessions']}
            self.assertIn('sess-mcp-001', by_id)
            self.assertTrue(by_id['sess-mcp-001']['uses_mcp'])

    def test_non_mcp_tool_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = make_assistant_turn(
                'sess-no-mcp', '/proj',
                tool_names=['Bash', 'Read'])
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            by_id = {s['session_id']: s for s in data['sessions']}
            self.assertFalse(by_id['sess-no-mcp']['uses_mcp'])


class TestSessionAggregation(unittest.TestCase):
    """Multiple turns in the same session_id must be summed."""

    def test_two_turns_summed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn1 = make_assistant_turn('sess-agg', '/proj',
                                        input_tokens=100, output_tokens=50)
            turn2 = make_assistant_turn('sess-agg', '/proj',
                                        input_tokens=200, output_tokens=100)
            write_sessions(proj, turn1 + turn2)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            by_id = {s['session_id']: s for s in data['sessions']}
            sess = by_id['sess-agg']
            self.assertEqual(sess['input_tokens'], 300)
            self.assertEqual(sess['output_tokens'], 150)


class TestSubagentAttribution(unittest.TestCase):
    """Subagent jsonl files must be attributed to the parent session."""

    def test_subagent_tokens_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'

            # Parent session file
            parent_lines = make_assistant_turn(
                'sess-parent', '/proj',
                input_tokens=100, output_tokens=50,
                timestamp='2026-03-15T10:00:00Z')
            write_sessions(proj, parent_lines, filename='sess-parent.jsonl')

            # Subagent file — same session_id, nested under subagents/
            sub_dir = proj / 'sess-parent' / 'subagents'
            sub_dir.mkdir(parents=True)
            sub_lines = make_assistant_turn(
                'sess-parent', '/proj',
                input_tokens=50, output_tokens=25,
                timestamp='2026-03-15T10:05:00Z')
            (sub_dir / 'agent-sub-001.jsonl').write_text('\n'.join(sub_lines))

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            by_id = {s['session_id']: s for s in data['sessions']}
            sess = by_id['sess-parent']
            # Subagent tokens should be summed with parent
            self.assertEqual(sess['input_tokens'], 150)
            self.assertEqual(sess['output_tokens'], 75)


class TestSyntheticModelSkip(unittest.TestCase):
    """Turns with model '<synthetic>' must be skipped entirely."""

    def test_synthetic_excluded_from_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            real = make_assistant_turn('sess-syn', '/proj',
                                       model='claude-sonnet-4-6',
                                       input_tokens=100, output_tokens=50)
            synthetic = make_assistant_turn('sess-syn', '/proj',
                                            model='<synthetic>',
                                            input_tokens=9999, output_tokens=9999)
            write_sessions(proj, real + synthetic)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            by_id = {s['session_id']: s for s in data['sessions']}
            sess = by_id['sess-syn']
            # Only the real turn's tokens should be counted
            self.assertEqual(sess['input_tokens'], 100)
            self.assertEqual(sess['output_tokens'], 50)


class TestSinceUntilFilter(unittest.TestCase):
    """--since / --until must restrict returned sessions by date."""

    def _write_dated_sessions(self, proj):
        all_lines = []
        for sid, ts in [
            ('sess-before', '2026-02-28T10:00:00Z'),
            ('sess-within', '2026-03-10T10:00:00Z'),
            ('sess-after',  '2026-03-20T10:00:00Z'),
        ]:
            all_lines.extend(make_assistant_turn(sid, '/proj', timestamp=ts))
        write_sessions(proj, all_lines)

    def test_since_excludes_older(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_dated_sessions(
                Path(tmp) / '.claude' / 'projects' / 'proj')
            result = run_analyze('--since', '2026-03-01', fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            ids = {s['session_id'] for s in data['sessions']}
            self.assertNotIn('sess-before', ids)
            self.assertIn('sess-within', ids)
            self.assertIn('sess-after', ids)

    def test_until_excludes_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_dated_sessions(
                Path(tmp) / '.claude' / 'projects' / 'proj')
            result = run_analyze('--until', '2026-03-15', fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            ids = {s['session_id'] for s in data['sessions']}
            self.assertNotIn('sess-after', ids)
            self.assertIn('sess-within', ids)

    def test_since_and_until_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_dated_sessions(
                Path(tmp) / '.claude' / 'projects' / 'proj')
            result = run_analyze(
                '--since', '2026-03-01', '--until', '2026-03-15',
                fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            ids = {s['session_id'] for s in data['sessions']}
            self.assertEqual(ids, {'sess-within'})


class TestMaxSessionsCap(unittest.TestCase):
    """--max-sessions must truncate oldest sessions and set truncated flag."""

    def test_truncation_flag_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            all_lines = []
            for i in range(10):
                sid = f'sess-cap-{i:03d}'
                ts = f'2026-03-{i + 1:02d}T10:00:00Z'
                all_lines.extend(make_assistant_turn(sid, '/proj', timestamp=ts))
            write_sessions(proj, all_lines)

            result = run_analyze('--max-sessions', '5', fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)

            self.assertEqual(len(data['sessions']), 5)
            self.assertTrue(data.get('truncated'), 'Expected truncated=true in JSON')
            self.assertEqual(data.get('truncated_count'), 5)

    def test_no_truncation_when_under_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = make_assistant_turn('sess-only', '/proj')
            write_sessions(proj, lines)

            result = run_analyze('--max-sessions', '10', fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertFalse(data.get('truncated', False))
            self.assertEqual(len(data['sessions']), 1)


class TestContextGrowthFields(unittest.TestCase):
    """cost_first_half, cost_second_half, and context_growth_ratio must be computed."""

    def test_context_growth_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn1 = make_assistant_turn(
                'sess-grow', '/proj',
                cache_write_tokens=10000, input_tokens=10, output_tokens=10,
                timestamp='2026-03-15T10:00:00Z')
            turn2 = make_assistant_turn(
                'sess-grow', '/proj',
                cache_write_tokens=50000, input_tokens=10, output_tokens=10,
                timestamp='2026-03-15T10:05:00Z')
            write_sessions(proj, turn1 + turn2)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-grow']
            self.assertEqual(sess['context_growth_ratio'], 5.0)
            self.assertGreater(sess['cost_second_half'], 0)
            self.assertGreater(sess['cost_first_half'], 0)
            self.assertGreater(sess['max_turn_cost'], 0)
            self.assertGreater(sess['avg_turn_cost'], 0)

    def test_single_turn_session(self):
        """Single-turn sessions should have sensible defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn = make_assistant_turn(
                'sess-single', '/proj',
                cache_write_tokens=10000, input_tokens=10, output_tokens=10)
            write_sessions(proj, turn)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-single']
            # Single turn: mid=0, cost_first_half=0, cost_second_half=total
            self.assertEqual(sess['cost_first_half'], 0)
            self.assertGreater(sess['cost_second_half'], 0)


class TestUserTextTurns(unittest.TestCase):
    """user_text_turns must count user text messages, not tool results."""

    def test_text_turns_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = (
                make_assistant_turn('sess-ut', '/proj') +
                make_user_text_turn('sess-ut', 'fix this bug') +
                make_assistant_turn('sess-ut', '/proj',
                                    timestamp='2026-03-15T10:01:00Z') +
                make_user_text_turn('sess-ut', 'no, try again') +
                make_assistant_turn('sess-ut', '/proj',
                                    timestamp='2026-03-15T10:02:00Z')
            )
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-ut']
            self.assertEqual(sess['user_text_turns'], 2)

    def test_tool_results_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = (
                make_assistant_turn('sess-tr', '/proj',
                                    tool_names=['Read']) +
                make_user_tool_result('sess-tr', 'tool_Read', 'file contents')
            )
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-tr']
            self.assertEqual(sess['user_text_turns'], 0)


class TestInterTurnGaps(unittest.TestCase):
    """inter_turn_gaps must detect gaps > 5 minutes between turns."""

    def test_gap_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn1 = make_assistant_turn(
                'sess-gap', '/proj',
                cache_write_tokens=50000,
                timestamp='2026-03-15T10:00:00Z')
            # 10 minute gap
            turn2 = make_assistant_turn(
                'sess-gap', '/proj',
                cache_write_tokens=60000,
                timestamp='2026-03-15T10:10:00Z')
            write_sessions(proj, turn1 + turn2)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-gap']
            self.assertEqual(len(sess['inter_turn_gaps']), 1)
            self.assertEqual(sess['inter_turn_gaps'][0]['gap_seconds'], 600)
            self.assertGreater(sess['inter_turn_gaps'][0]['rewrite_cost'], 0)

    def test_no_gap_under_5min(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn1 = make_assistant_turn(
                'sess-nogap', '/proj',
                timestamp='2026-03-15T10:00:00Z')
            turn2 = make_assistant_turn(
                'sess-nogap', '/proj',
                timestamp='2026-03-15T10:04:00Z')
            write_sessions(proj, turn1 + turn2)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-nogap']
            self.assertEqual(len(sess['inter_turn_gaps']), 0)


class TestDuplicateFileReads(unittest.TestCase):
    """read_file_counts must track files read 2+ times."""

    def test_duplicate_reads_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            read_tool = {'name': 'Read', 'id': 'read_1',
                         'input': {'file_path': '/src/handler.ts'}}
            read_tool2 = {'name': 'Read', 'id': 'read_2',
                          'input': {'file_path': '/src/handler.ts'}}
            read_tool3 = {'name': 'Read', 'id': 'read_3',
                          'input': {'file_path': '/src/handler.ts'}}
            lines = (
                make_assistant_turn('sess-dup', '/proj',
                                    tool_uses=[read_tool],
                                    timestamp='2026-03-15T10:00:00Z') +
                make_assistant_turn('sess-dup', '/proj',
                                    tool_uses=[read_tool2],
                                    timestamp='2026-03-15T10:01:00Z') +
                make_assistant_turn('sess-dup', '/proj',
                                    tool_uses=[read_tool3],
                                    timestamp='2026-03-15T10:02:00Z')
            )
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-dup']
            self.assertEqual(sess['read_file_counts']['/src/handler.ts'], 3)
            self.assertEqual(sess['duplicate_reads'], 2)

    def test_no_duplicates_for_single_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            read_a = {'name': 'Read', 'id': 'ra', 'input': {'file_path': '/a.ts'}}
            read_b = {'name': 'Read', 'id': 'rb', 'input': {'file_path': '/b.ts'}}
            lines = make_assistant_turn('sess-nodup', '/proj',
                                         tool_uses=[read_a, read_b])
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-nodup']
            self.assertEqual(sess['read_file_counts'], {})
            self.assertEqual(sess['duplicate_reads'], 0)


class TestLargeToolResults(unittest.TestCase):
    """large_tool_results must capture tool results exceeding 20K chars."""

    def test_large_result_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = (
                make_assistant_turn('sess-big', '/proj',
                                    tool_names=['Bash']) +
                make_user_tool_result('sess-big', 'tool_Bash', size=25000)
            )
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-big']
            self.assertEqual(len(sess['large_tool_results']), 1)
            self.assertEqual(sess['large_tool_results'][0]['tool'], 'Bash')
            self.assertEqual(sess['large_tool_results'][0]['size'], 25000)

    def test_small_result_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            lines = (
                make_assistant_turn('sess-small', '/proj',
                                    tool_names=['Read']) +
                make_user_tool_result('sess-small', 'tool_Read', size=5000)
            )
            write_sessions(proj, lines)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-small']
            self.assertEqual(len(sess['large_tool_results']), 0)


class TestFirstCacheWriteInOutput(unittest.TestCase):
    """first_cache_write must appear in the output JSON for F1 detection."""

    def test_first_cache_write_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn1 = make_assistant_turn(
                'sess-fcw', '/proj',
                cache_write_tokens=45000, input_tokens=100, output_tokens=50,
                timestamp='2026-03-15T10:00:00Z')
            turn2 = make_assistant_turn(
                'sess-fcw', '/proj',
                cache_write_tokens=5000, input_tokens=100, output_tokens=50,
                timestamp='2026-03-15T10:01:00Z')
            write_sessions(proj, turn1 + turn2)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-fcw']
            self.assertIn('first_cache_write', sess)
            self.assertEqual(sess['first_cache_write'], 45000)

    def test_first_cache_write_zero_when_no_cache(self):
        """Sessions with zero cache writes should have first_cache_write=0."""
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / '.claude' / 'projects' / 'proj'
            turn = make_assistant_turn(
                'sess-nocw', '/proj',
                cache_write_tokens=0, input_tokens=100, output_tokens=50)
            write_sessions(proj, turn)

            result = run_analyze(fake_home=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            sess = {s['session_id']: s for s in data['sessions']}['sess-nocw']
            self.assertIn('first_cache_write', sess)
            self.assertEqual(sess['first_cache_write'], 0)


if __name__ == '__main__':
    unittest.main()
