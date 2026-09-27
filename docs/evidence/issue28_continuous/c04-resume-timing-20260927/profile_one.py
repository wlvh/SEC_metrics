"""Time one recorded C04 recovery test without changing its source or assertions."""

import faulthandler
import json
import time
import unittest

from vnext import c04_update_cycle as c04
from vnext import continuous_sec_acquisition as sec
from vnext import normal_run_v3 as normal
from vnext import ordinary_processing_source as processing
from vnext import ordinary_refresh_cycle as refresh
from vnext import ordinary_update_cycle as update


def clock(module, name):
    original = getattr(module, name)

    def measured(*args, **kwargs):
        start = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            print(json.dumps({'event': module.__name__ + '.' + name,
                              'seconds': round(time.perf_counter() - start, 3)}),
                  flush=True)

    setattr(module, name, measured)


for module, names in (
    (refresh, ('initialize_source_inputs', 'discover_saved_source_requirements',
               '_resume_one_c04_source', '_historical_c04_processing_copies',
               'run_company')),
    (processing, ('initialize_source_inputs', 'checkpoint_installation',
                  '_check_copy', 'current_processing_source',
                  'verify_processing_source')),
    (normal, ('prepare_case',)),
    (c04, ('run_company',)),
    (update, ('_config', '_state')),
    (sec.SecAcquisitionSession, ('capture',)),
):
    for name in names:
        clock(module, name)

faulthandler.dump_traceback_later(180, repeat=True)
suite = unittest.defaultTestLoader.loadTestsFromName(
    'tests.vnext.test_c04_source_only_install.'
    'C04MixedSourceRouteMaterialTest.'
    'test_failed_processing_copy_preserves_recorded_capture_for_resume')
started = time.perf_counter()
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'event': 'whole_test',
                  'seconds': round(time.perf_counter() - started, 3),
                  'success': result.wasSuccessful()}), flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
