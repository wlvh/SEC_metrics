import hashlib
import json
import sys
import time
import unittest
from contextlib import ExitStack
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
out = Path(sys.argv[3])
sys.path[:0] = [str(repo / 'scripts'), str(repo)]
records = []

class Results(unittest.TextTestResult):
    def addSuccess(self, test):
        records.append({'test': test.id(), 'outcome': 'PASS'})
        super().addSuccess(test)
    def addFailure(self, test, err):
        records.append({'test': test.id(), 'outcome': 'FAIL'})
        super().addFailure(test, err)
    def addError(self, test, err):
        records.append({'test': test.id(), 'outcome': 'ERROR'})
        super().addError(test, err)

def encode(value):
    if isinstance(value, bytes):
        return {'bytes_sha256': hashlib.sha256(value).hexdigest(), 'length': len(value)}
    raise TypeError(type(value).__name__)

started = time.monotonic()
replays, derivations = [], []
with ExitStack() as blocks:
    if mode == 'memo':
        from vnext.historical_run_replay import run_checks_replay_once
        from vnext.historical_derivation_memo import derived_once_per_state
        blocks.enter_context(run_checks_replay_once(replays=replays))
        blocks.enter_context(derived_once_per_state(report=derivations))
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.vnext.test_historical_debt_results')
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(suite)
    from tests.vnext import test_historical_debt_results as cases
    resolved = {company + ':' + end: row for (company, end), row in cases._RESOLVED.items()}
    identities = json.dumps(resolved, sort_keys=True, separators=(',', ':'), default=encode)
body = {'mode': mode, 'seconds': time.monotonic() - started, 'tests': records,
        'tests_run': result.testsRun, 'success': result.wasSuccessful(),
        'resolved_sha256': hashlib.sha256(identities.encode()).hexdigest(),
        'resolved_count': len(resolved), 'replays': replays, 'derivations': derivations,
        'source_test_sha256': hashlib.sha256((repo / 'tests/vnext/test_historical_debt_results.py').read_bytes()).hexdigest()}
out.write_text(json.dumps(body, indent=1, sort_keys=True) + '\n')
out.with_suffix('.resolved.json').write_text(identities + '\n')
sys.exit(0 if result.wasSuccessful() else 1)
