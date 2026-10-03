"""Time the existing D03 material test without replacing source validation."""
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))

from tests.vnext import test_d03_recorded_response_store as tests
from vnext import (d03_recorded_response_store as store,
                   r6_regulatory_semantics as semantic,
                   regulatory_fact_review as review)

events = []


def timed(original, label):
    def wrapped(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original(*args, **kwargs)
        finally:
            events.append({'call': label,
                           'seconds': round((time.perf_counter_ns()-start)/1e9, 3)})
    return wrapped


def instrument(module, name, label, aliases=()):
    wrapper = timed(getattr(module, name), label)
    setattr(module, name, wrapper)
    for alias, alias_name in aliases:
        setattr(alias, alias_name, wrapper)


instrument(semantic, 'prepare_regulatory_semantic_source', 'source_rebuild',
           [(tests, 'prepare_regulatory_semantic_source')])
instrument(semantic, 'requests_from_source', 'request_grouping',
           [(tests, 'requests_from_source')])
instrument(semantic, 'validate_response', 'base_semantic_validation')
instrument(review, 'candidate_request', 'candidate_request',
           [(store, 'candidate_request')])
instrument(review, 'validate_candidate_response', 'candidate_validation',
           [(store, 'validate_candidate_response')])
instrument(store, 'record_offline_response', 'record_packet',
           [(tests, 'record_offline_response')])
instrument(store, 'replay_offline_response', 'replay_packet',
           [(tests, 'replay_offline_response')])

start = time.perf_counter_ns()
suite = unittest.TestSuite([tests.D03RecordedResponseStoreTest(
    'test_original_response_bytes_and_unresolved_survive_cold_replay')])
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
by_call = {}
for event in events:
    item = by_call.setdefault(event['call'], {'count': 0, 'inclusive_seconds': 0.0,
                                              'individual_seconds': []})
    item['count'] += 1
    item['inclusive_seconds'] += event['seconds']
    item['individual_seconds'].append(event['seconds'])
for item in by_call.values():
    item['inclusive_seconds'] = round(item['inclusive_seconds'], 3)
print(json.dumps({'record_type': 'D03_EXISTING_MATERIAL_TEST_PHASE_TIMING',
    'wall_seconds': round((time.perf_counter_ns()-start)/1e9, 3),
    'tests_run': result.testsRun, 'successful': result.wasSuccessful(),
    'events': events, 'by_call': by_call,
    'source_material': 'CURRENT_SAVED_JPM_ORIGINAL',
    'provider_paid_sec_calls': [0, 0, 0]}, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
