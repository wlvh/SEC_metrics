"""Read-only Salesforce C04 four-form preparation from the original #28 root."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.normal_run_v3 import prepare_case

DATA = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
started = time.monotonic()
case = prepare_case(data_root=DATA, company_id='salesforce',
                    metric_id='C04', c04_event_forms=EVENT_FORMS)
result = case['results']['C04']
print(json.dumps({'status': 'SAVED_SOURCE_PREPARED',
    'company_id': 'salesforce', 'metric_id': 'C04',
    'result_id': result['result_id'],
    'publication': result['publication'],
    'value': result.get('value'), 'result_keys': sorted(result),
    'target': case['targets']['C04'],
    'source_proofs': len(case['source_proofs']),
    'elapsed_seconds': round(time.monotonic()-started, 3),
    'native_run_created': False,
    'provider_paid_sec_calls': [0, 0, 0]}, ensure_ascii=False, sort_keys=True))
