"""Compare a V7 request's exact bytes with the pushed pre-repair code."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from tests.vnext.test_capacity_two_stage import CapacityTwoStageTest
from vnext import capacity_two_stage as current
from vnext.canonical import canonical_json_bytes

BASE = '227182efe31b7ce6364c866753ae1332afb41ea2'
raw = subprocess.check_output(['git', 'show',
    BASE + ':scripts/vnext/capacity_two_stage.py'], cwd=ROOT)
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'capacity_two_stage_before.py'
    source.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('vnext._claim_before', source)
    previous = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = previous
    spec.loader.exec_module(previous)
    test = CapacityTwoStageTest(
        'test_claim_context_successor_keeps_distinct_claims_and_shared_sentence')
    test.setUp()
    old = previous.interpretation_request(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw,
        claim_contexts=True)
    new = current.interpretation_request(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw,
        claim_contexts=True)
    assert canonical_json_bytes(value=old) == canonical_json_bytes(value=new)
    print(json.dumps({'status': 'V7_REQUEST_BYTES_UNCHANGED',
        'pushed_base': BASE, 'request_id': old['request_id'],
        'bytes': len(canonical_json_bytes(value=new)),
        'model_calls': 0, 'provider_permission_added': False}, sort_keys=True))
