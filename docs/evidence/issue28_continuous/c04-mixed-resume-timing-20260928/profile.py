"""Time one existing C04 mixed-resume material test without changing its inputs."""
import functools
import json
from pathlib import Path
import time
import unittest

from vnext import c04_update_cycle as c04
from vnext import normal_run_v3 as normal
from vnext import ordinary_processing_source as processing
from vnext import ordinary_refresh_cycle as refresh
from vnext import ordinary_update_cycle as cycle


HERE = Path(__file__).resolve().parent
EVENTS = []
DEPTH = 0


def wrap(module, name):
    original = getattr(module, name)

    @functools.wraps(original)
    def timed(*args, **kwargs):
        global DEPTH
        depth = DEPTH
        DEPTH += 1
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            EVENTS.append({'module': module.__name__, 'function': name,
                           'depth': depth,
                           'seconds': round(time.perf_counter()-started, 3)})
            DEPTH -= 1

    setattr(module, name, timed)


for module, names in (
        (refresh, ('refresh_and_process', '_resume_one_c04_source',
                   'discover_saved_source_requirements', '_check_session',
                   '_ordinary_pre_capture_state', '_failed_urls',
                   '_historical_c04_processing_copies')),
        (processing, ('current_processing_source', 'verify_processing_source')),
        (normal, ('prepare_case', 'install_normal_inputs', 'create_normal_run')),
        (cycle, ('run_once', '_verify_candidate', '_state', '_recover')),
        (c04, ('run_once', '_verify_candidate'))):
    for name in names:
        wrap(module, name)

started = time.perf_counter()
suite = unittest.TestLoader().loadTestsFromName(
    'tests.vnext.test_c04_source_only_install.C04MixedSourceRouteMaterialTest.'
    'test_mixed_old_root_resumes_current_rule_metric_and_c04')
result = unittest.TextTestRunner(verbosity=1).run(suite)
body = {'test': 'C04 mixed old root resume existing material test',
        'status': 'PASS' if result.wasSuccessful() else 'FAILED',
        'duration_seconds': round(time.perf_counter()-started, 3),
        'tests_run': result.testsRun,
        'errors': len(result.errors), 'failures': len(result.failures),
        'events': EVENTS,
        'real_provider_or_sec_calls': 0,
        'profile_only_no_source_or_business_code_change': True}
(HERE/'timing.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
