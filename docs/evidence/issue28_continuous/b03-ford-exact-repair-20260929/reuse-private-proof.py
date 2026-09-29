"""Check whether the earlier private Run still matches the final V13 tree."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.continuous_call_wiring import validate_wiring_receipt
from vnext.ordinary_processing_source import verify_processing_source
from vnext.requirements import load_requirement_snapshot

first = json.loads((HERE/'binding-after-first-prototype.json').read_text())
final = json.loads((HERE/'binding-after.json').read_text())
processing = json.loads((HERE/'processing.json').read_text())
created = json.loads((HERE/'private-result.json').read_text())
cold = json.loads((HERE/'cold.json').read_text())
requirement = load_requirement_snapshot(
    snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
validate_wiring_receipt(requirement=requirement)
assert first['parent_requirement_closure_hash'] == \
       final['parent_requirement_closure_hash']
assert first['child_requirement_closure_hash'] == \
       final['child_requirement_closure_hash'] == \
       requirement['requirement_closure_hash'] == \
       processing['requirement_closure_hash'] == \
       created['requirement_closure_hash']
assert first['child_execution_authority_hash'] == \
       final['child_execution_authority_hash']
verified = verify_processing_source(
    acquisition_root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs'),
    processing_root=Path(processing['processing_root']),
    requirement=requirement)
assert verified['snapshot_id'] == processing['source_snapshot_id'] == \
       created['source_snapshot_id'] == cold['source_snapshot_id']
assert created['result_id'] == cold['result_id']
assert created['new_real_calls'] == cold['new_real_calls'] == [0, 0, 0]
body = {'status': 'EXACT_BOUND_TREE_PRIVATE_RUN_AND_COLD_READ_REUSABLE',
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'execution_authority_hash': final['child_execution_authority_hash'],
    'source_snapshot_id': verified['snapshot_id'],
    'result_id': created['result_id'], 'value': created['value'],
    'source_and_run_replayed_earlier_under_identical_bound_bytes': True,
    'repeated_private_creation_or_cold_read': False,
    'new_real_calls': [0, 0, 0], 'formal_adoption': False}
(HERE/'reuse-private-proof.json').write_text(json.dumps(body,
    ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'],
    'result_id': body['result_id'],
    'source': body['source_snapshot_id']}, sort_keys=True))
