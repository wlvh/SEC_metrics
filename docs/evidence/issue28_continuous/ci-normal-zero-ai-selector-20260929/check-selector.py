"""Confirm this CI repair changes one limit, not the selected tests."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools'))
import run_fast_tests_v2 as current

PREVIOUS_HEAD = '357bae2452b29dc1ed9f0679f6591668c604e7c4'
old_source = subprocess.check_output(['git', 'show',
    PREVIOUS_HEAD + ':tools/run_fast_tests_v2.py'], cwd=ROOT, text=True)
previous = {'__name__': 'issue28_previous_runner',
            '__file__': str(ROOT/'tools/run_fast_tests_v2.py')}
exec(compile(old_source, previous['__file__'], 'exec'), previous)
target = 'tests.vnext.test_normal_zero_ai_results'
old = previous['SOURCE_TIMEOUT_OVERRIDES']
now = current.SOURCE_TIMEOUT_OVERRIDES
assert target not in old and now[target] == 300
assert {k: v for k, v in now.items() if k != target} == old
assert current.SOURCE_TESTS == previous['SOURCE_TESTS']
assert current.FAST_TESTS == previous['FAST_TESTS']
assert current.SOURCE_TESTS.count(target) == 1
body = {'record_type': 'ISSUE28_NORMAL_ZERO_AI_ONLY_TIMEOUT_OVERRIDE',
    'previous_head': PREVIOUS_HEAD,
    'target_selector': target,
    'old_effective_timeout_seconds': current.SOURCE_TIMEOUT_SECONDS,
    'new_effective_timeout_seconds': now[target],
    'source_selectors_unchanged': True,
    'fast_selectors_unchanged': True,
    'source_selector_count': len(current.SOURCE_TESTS),
    'fast_selector_count': len(current.FAST_TESTS),
    'all_other_overrides_unchanged': True,
    'new_real_calls': [0, 0, 0]}
(HERE/'selector-identity.json').write_text(json.dumps(body, indent=2) + '\n')
print(json.dumps({'target': target, 'timeout': now[target],
    'source_selectors': len(current.SOURCE_TESTS),
    'fast_selectors': len(current.FAST_TESTS)}, sort_keys=True), flush=True)
