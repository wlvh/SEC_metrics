"""Current CI: small tests share a process; full originals keep their own tier.

The old runner stays available for saved-version diagnostics. This current
entry keeps its selectors visible without launching Python for each unit test.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
import json
import io
import sys
import time
import unittest

import run_fast_tests as inherited
import run_fast_tests_v2 as v2

# These methods parse full originals across several companies. They are not
# small-input tests and cannot meaningfully use the old 30-second unit budget.
MATERIAL_PREFIXES = ('tests.vnext.test_normal_annual_input.NormalAnnualInputTest.',)
# Only ancestor/creator anti-forgery checks, retired by trusted-internal-20261006.
# Their old source and runner remain available in the saved historical version.
RETIRED_SELECTORS = ('tests.vnext.test_normal_candidate_authority',)


def partition():
    original = tuple(inherited.FAST_TESTS)
    retired = tuple(s for s in original if s in RETIRED_SELECTORS)
    active = tuple(s for s in original if s not in retired)
    source = tuple(s for s in active
                   if s == v2.REPLACED
                   or any(s.startswith(prefix) for prefix in (*v2.SOURCE_PREFIXES, *MATERIAL_PREFIXES)))
    fast = tuple(s for s in active if s not in source)
    if (len(set(original)) != len(original) or set(fast) & set(source)
            or set(fast) | set(source) | set(retired) != set(original)
            or len(fast) + len(source) + len(retired) != len(original)):
        raise inherited.FastTestError('FOUNDATION_CI_SELECTOR_COVERAGE_CHANGED')
    return {'fast':fast, 'source-material':source, 'retired':retired}


def run_fast_suite(selected):
    """Use unittest's class/module fixtures once; keep each failure observable."""
    # Direct script invocation starts with tools/, whereas `python -m unittest`
    # starts with the repository root. In-process loading needs that same root.
    if str(inherited.REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(inherited.REPO_ROOT))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(s) for s in selected)
    stream = io.StringIO(); start = time.monotonic()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {'return_code': 0 if result.wasSuccessful() else 1,
            'duration_seconds': time.monotonic()-start,
            'test_count': result.testsRun,
            'failures': [{'test': str(t), 'traceback': error} for t,error in result.failures],
            'errors': [{'test': str(t), 'traceback': error} for t,error in result.errors],
            'skips': [{'test': str(t), 'reason': reason} for t,reason in result.skipped],
            'diagnostics': stream.getvalue()}


def run_fast_suite(selected):
    """Use unittest's class/module fixtures once; keep each failure observable."""
    # Direct script invocation starts with tools/, whereas `python -m unittest`
    # starts with the repository root. In-process loading needs that same root.
    if str(inherited.REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(inherited.REPO_ROOT))
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(s) for s in selected)
    stream = io.StringIO(); start = time.monotonic()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {'return_code': 0 if result.wasSuccessful() else 1,
            'duration_seconds': time.monotonic()-start,
            'test_count': result.testsRun,
            'failures': [{'test': str(t), 'traceback': error} for t,error in result.failures],
            'errors': [{'test': str(t), 'traceback': error} for t,error in result.errors],
            'skips': [{'test': str(t), 'reason': reason} for t,reason in result.skipped],
            'diagnostics': stream.getvalue()}


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
                          'retired_selectors':suites['retired'],
                          'total_inherited':len(inherited.FAST_TESTS)}, indent=2))
        return 0
    if not 1 <= args.jobs <= len(selected):
        raise inherited.FastTestError('FAST_TEST_JOBS_INVALID')
    start = time.monotonic()
    if args.suite == 'fast':
        results = [run_fast_suite(selected)]
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(v2._run_source_case, selected))
    status = 'PASSED' if all(r['return_code'] == 0 for r in results) else 'FAILED'
    print(json.dumps({'suite':args.suite, 'status':status,
        'duration_seconds':time.monotonic()-start,
        'jobs':1 if args.suite == 'fast' else args.jobs, 'selected_selectors': selected,
        'retired_selectors':suites.get('retired',()),
        'total_inherited':len(inherited.FAST_TESTS), 'tests':results}, sort_keys=True))
    return 0 if status == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
