"""Exercise exact D01 selectors under their intended fast/source limits."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RUNNER = ROOT / 'tools/run_fast_tests_v2.py'
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'


def selectors(suite):
    return json.loads(subprocess.check_output([PYTHON, str(RUNNER), '--suite', suite,
                                               '--list'], cwd=ROOT))['tests']


results = {}
for suite, target in [('fast', 'tests.vnext.test_d01_emphasis_successor'),
                      ('source-material', 'tests.vnext.test_d01_emphasis_material')]:
    names = selectors(suite)
    assert names.count(target) == 1
    index = names.index(target)
    command = [PYTHON, str(RUNNER), '--suite', suite]
    if suite == 'fast':
        command.extend(['--jobs', '4'])
    else:
        command.extend(['--shard-count', str(len(names)), '--shard-index',
                        str(index), '--jobs', '1'])
    run = subprocess.run(command, cwd=ROOT,
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr[-1600:] + run.stdout[-1600:]
    value = json.loads(run.stdout)
    assert value['status'] == 'PASSED'
    assert len(value['tests']) == (len(names) if suite == 'fast' else 1)
    matched = [row for row in value['tests'] if row['test'] == target]
    assert len(matched) == 1 and matched[0]['return_code'] == 0
    results[suite] = {'target': target, 'shard_index': index,
                      'shard_count': len(names),
                      'suite_status': value['status'],
                      'suite_selector_count': len(value['tests']),
                      'duration_seconds': matched[0]['duration_seconds'],
                      'timeout_seconds': matched[0].get('timeout_seconds',
                                                             value['per_case_timeout_seconds']),
                      'stderr_tail': matched[0]['stderr_tail'][-300:]}
body = {'record_type': 'ISSUE28_D01_SELECTOR_TIER_SPLIT',
        'status': 'PASS_FAST_SYNTHETIC_AND_SOURCE_MATERIAL',
        'original_remote_run_id': 36966491013,
        'original_remote_head': 'eea7821cc794e87276c06ab583a8623e06a1ccf6',
        'source_and_product_rules_unchanged': True,
        'new_real_calls': [0, 0, 0], 'selectors': results}
(HERE / 'selector-split.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'], 'selectors': {
    key: {'seconds': row['duration_seconds'], 'timeout': row['timeout_seconds']}
    for key, row in results.items()}}))
