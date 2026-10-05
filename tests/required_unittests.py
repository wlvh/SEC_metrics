"""Run required unittest modules and fail on unexpected skips.

CI jobs that restore inherited source-material coverage need a material
root; without it several classes are skipped and unittest still exits 0.
This runner counts what actually executed so a skip cannot pass as coverage.
"""
import argparse
import json
from pathlib import Path
import sys
import unittest

# Run as `python3 tests/required_unittests.py`: replace the script directory
# (which would shadow `vnext` with `tests/vnext`) by the repository root, as
# `python3 -m unittest` from the repository root would.
sys.path[0] = str(Path(__file__).resolve().parents[1])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-skips', type=int, default=0,
                        help='Skips that already existed in the original workflow')
    parser.add_argument('names', nargs='+')
    args = parser.parse_args(argv)
    suite = unittest.defaultTestLoader.loadTestsFromNames(args.names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'tests': args.names, 'run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'allowed_skips': args.allow_skips,
               'skip_reasons': [reason for _, reason in result.skipped]}
    print(json.dumps(summary, sort_keys=True))
    ok = (result.wasSuccessful() and result.testsRun > 0
          and len(result.skipped) <= args.allow_skips)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
