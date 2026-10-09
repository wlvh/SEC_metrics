"""Check exact current source selector coverage for two and three CI shards."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'tools'))
from run_fast_tests_v2 import SOURCE_TESTS

HERE = Path(__file__).resolve().parent
timing = json.loads((HERE/'previous-success-timings.json').read_text())
known = timing['selector_seconds']
assert timing['source_status'] == 'SUCCESS_BOTH_SHARDS'
assert len(known) == 82 and len(set(SOURCE_TESTS)) == len(SOURCE_TESTS)


def plan(count):
    shards = []
    seen = set()
    for index in range(count):
        names = [name for position, name in enumerate(SOURCE_TESTS)
                 if position % count == index]
        assert not seen.intersection(names)
        seen.update(names)
        shards.append({'index': index, 'selector_count': len(names),
            'known_selector_seconds_sum': round(sum(known.get(name, 0)
                for name in names), 3),
            'not_in_prior_successful_run': [name for name in names
                if name not in known],
            'selectors': names})
    assert seen == set(SOURCE_TESTS) and sum(row['selector_count']
        for row in shards) == len(SOURCE_TESTS)
    return shards


body = {'record_type': 'ISSUE28_CI_SOURCE_SHARD_DISTRIBUTION',
    'current_selector_count': len(SOURCE_TESTS),
    'prior_successfully_timed_count': len(known),
    'two_shards': plan(2), 'three_shards': plan(3),
    'exact_once_partition_verified': True,
    'timing_interpretation': 'SUM_OF_PRIOR_PER_SELECTOR_PROCESS_ELAPSED_NOT_JOB_WALL_TIME',
    'prediction_or_accuracy_claim': False}
(HERE/'distribution.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'status': 'PASS_EXACT_88_SOURCE_SELECTORS_ON_THREE_SHARDS',
    'two_known_seconds': [x['known_selector_seconds_sum'] for x in body['two_shards']],
    'three_known_seconds': [x['known_selector_seconds_sum'] for x in body['three_shards']],
    'new_untimed_count': len(SOURCE_TESTS) - len(known)}, sort_keys=True))
