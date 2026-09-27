"""Compare exact V5/V6 request bytes and V5 diagnostics to the pushed parent."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
BASE = '1613dab6b4d41e378c5f6d3ef922789f14ff0331'
raw = subprocess.check_output(['git', 'show',
    BASE + ':scripts/vnext/capacity_two_stage.py'], cwd=ROOT)
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'capacity_two_stage_before.py'
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('vnext._capacity_two_stage_before', path)
    previous = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = previous
    spec.loader.exec_module(previous)

    from tests.vnext.test_capacity_two_stage import CapacityTwoStageTest
    from vnext import capacity_two_stage as current
    from vnext.canonical import canonical_json_bytes

    test = CapacityTwoStageTest('test_nonempty_two_stage_uses_complete_original_source_and_semantics')
    test.setUp()
    assert previous.scan_request(test.request) == current.scan_request(test.request)
    pairs = []
    for scoped in (False, True):
        before = previous.interpretation_request(request=test.request,
            scan_result=test.scan_result, scan_raw_response=test.scan_raw,
            assertion_scopes=scoped)
        after = current.interpretation_request(request=test.request,
            scan_result=test.scan_result, scan_raw_response=test.scan_raw,
            assertion_scopes=scoped)
        assert canonical_json_bytes(value=before) == canonical_json_bytes(value=after)
        pairs.append({'version': before['source_reference_contract']['version'],
                      'request_id': before['request_id'], 'bytes': len(canonical_json_bytes(value=before))})
    before = previous.interpretation_request(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw)
    after = current.interpretation_request(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw)
    response = canonical_json_bytes(value=test.interpretation_response)
    old_check = previous.validate_interpretation(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw,
        interpretation=before, raw_response=response, source=test.source)
    new_check = current.validate_interpretation(request=test.request,
        scan_result=test.scan_result, scan_raw_response=test.scan_raw,
        interpretation=after, raw_response=response, source=test.source)
    assert old_check == new_check
    print(json.dumps({'pushed_parent': BASE, 'unchanged_requests': pairs,
                      'v5_checked_equal': True}, sort_keys=True))
