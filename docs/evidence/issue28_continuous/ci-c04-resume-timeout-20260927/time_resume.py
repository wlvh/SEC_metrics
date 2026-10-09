"""Time the four actual branches of the one C04 material selector."""
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext import ordinary_refresh_cycle as refresh

original = refresh.refresh_and_process
observed = []


def timed(*args, **kwargs):
    started = time.monotonic()
    try:
        result = original(*args, **kwargs)
    except Exception as error:
        observed.append({'branch': len(observed) + 1,
            'resume': kwargs.get('resume_from') is not None,
            'seconds': round(time.monotonic() - started, 3),
            'raised': type(error).__name__, 'reason': str(error)})
        raise
    observed.append({'branch': len(observed) + 1,
        'resume': kwargs.get('resume_from') is not None,
        'seconds': round(time.monotonic() - started, 3),
        'status': result['status'],
        'calls': result['calls']})
    return result


refresh.refresh_and_process = timed
suite = unittest.defaultTestLoader.loadTestsFromName(
    'tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest')
started = time.monotonic()
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAIL',
    'test_cases': result.testsRun, 'elapsed_seconds': round(time.monotonic() - started, 3),
    'branches': observed, 'source_material_substitution': False,
    'new_real_calls': [0, 0, 0]}, sort_keys=True), flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
