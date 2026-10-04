"""CI-only partition of the fixed inherited selectors; no added business suite.

Reuse the existing v2 source-material classification and workers. Keep every
selector in the frozen inherited runner exactly once, without changing either
runner's functions, per-case limits or old CLI behavior.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time

import run_fast_tests as inherited
import run_fast_tests_v2 as v2


def partition():
    original = tuple(inherited.FAST_TESTS)
    source = tuple(s for s in original
                   if any(s.startswith(prefix) for prefix in v2.SOURCE_PREFIXES))
    fast = tuple(s for s in original if s not in source)
    if (len(set(original)) != len(original) or set(fast) & set(source)
            or set(fast) | set(source) != set(original)
            or len(fast) + len(source) != len(original)):
        raise inherited.FastTestError('FOUNDATION_CI_SELECTOR_COVERAGE_CHANGED')
    return {'fast':fast, 'source-material':source}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('fast','source-material'), required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    suites = partition()
    selected = suites[args.suite]
    if args.list:
        print(json.dumps({'suite':args.suite, 'selectors':selected,
                          'total_inherited':len(inherited.FAST_TESTS)}, indent=2))
        return 0
    if not 1 <= args.jobs <= len(selected):
        raise inherited.FastTestError('FAST_TEST_JOBS_INVALID')
    def worker(name):
        return (inherited._run_case(test_name=name) if args.suite == 'fast'
                else v2._run_source_case(name))
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(worker, selected))
    status = 'PASSED' if all(r['return_code'] == 0 for r in results) else 'FAILED'
    print(json.dumps({'suite':args.suite, 'status':status,
        'duration_seconds':time.monotonic()-start, 'jobs':args.jobs,
        'total_inherited':len(inherited.FAST_TESTS), 'tests':results}, sort_keys=True))
    return 0 if status == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
