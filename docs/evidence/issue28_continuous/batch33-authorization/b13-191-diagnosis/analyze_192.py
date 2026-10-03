"""Read-only audit of the one allowed real V4 repair outcome at ordinal192."""
import hashlib
import json
from collections import Counter
from pathlib import Path


root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0192')
intent = json.loads((root / 'intent.json').read_text())
terminal = json.loads((root / 'terminal.json').read_text())
wire = json.loads((root / 'wire/journal.json').read_text())
response = json.loads((root / 'wire/raw-response.bin').read_text())
request = json.loads((root / 'semantic-request.json').read_text())
content = response['choices'][0]['message']['content']
assert intent['ordinal'] == 192 and intent['batch_group_id'] == 'B13:enphase_energy:1'
assert intent['batch_attempt_index'] == 1 and intent['batch_repair_191_id']
assert terminal['status'] == 'FAILED_TERMINAL' and not terminal['stop_reason']
assert terminal['counts'] == [1, 1, 0]
assert wire['error_class'] == 'DEEPSEEK_RESPONSE_INVALID'
assert wire['usage']['output_tokens'] == 4096
assert response['choices'][0]['finish_reason'] == 'length'
assert request['source_reference_contract']['version'] == 'B13_REQUIRED_FIRST_RELEVANCE_V4'

decoder = json.JSONDecoder()
units, _ = decoder.raw_decode(content[content.index('"units":') + len('"units":'):])
position = content.index('"findings":[') + len('"findings":[')
rows = []
while position < len(content):
    while position < len(content) and content[position] in ' \t\r\n,':
        position += 1
    try:
        row, end = decoder.raw_decode(content, position)
    except json.JSONDecodeError:
        break
    if not isinstance(row, list):
        break
    rows.append(row)
    position = end
assert len(units) == len(request['units']) == 4
assert len(request['required_candidate_assessments']) == 0
roles = dict(Counter(row[0] for row in rows))
assert len(rows) == 156 and roles == {
    'physical_capacity_context': 1, 'other_context': 155}
summary = {
    'record_type': 'ISSUE28_B13_192_V4_REPAIR_OUTCOME_AUDIT',
    'ordinal': 192,
    'group': intent['batch_group_id'],
    'attempt_index': intent['batch_attempt_index'],
    'v4_record_id': intent['batch_b13_v4_id'],
    'repair_record_id': intent['batch_repair_191_id'],
    'request_digest': intent['request_digest'],
    'request_sha256': hashlib.sha256((root / 'semantic-request.json').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256((root / 'source.json').read_bytes()).hexdigest(),
    'raw_response_sha256': hashlib.sha256((root / 'wire/raw-response.bin').read_bytes()).hexdigest(),
    'terminal_id': terminal['terminal_id'],
    'terminal_status': terminal['status'],
    'stop_reason': terminal['stop_reason'],
    'provider_finish_reason': response['choices'][0]['finish_reason'],
    'usage': wire['usage'],
    'source_unit_count': len(request['units']),
    'required_candidate_count': 0,
    'complete_prefix_finding_count': len(rows),
    'complete_prefix_unique_finding_count': len({json.dumps(row, sort_keys=True) for row in rows}),
    'complete_prefix_role_counts': roles,
    'nonrequired_other_context_count': roles['other_context'],
    'reasons_over_128_count': sum(len(row[4]) > 128 for row in rows),
    'response_complete_json': False,
    'native_candidate_created': False,
    'group1_repair_slot_consumed': True,
    'real_calls_already_charged': [1, 1, 0],
    'new_calls_from_this_audit': [0, 0, 0],
    'model_semantics_fully_reviewed': False,
}
destination = Path(__file__).with_name('v4-192-audit.json')
destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: summary[key] for key in (
    'ordinal', 'terminal_status', 'provider_finish_reason',
    'complete_prefix_finding_count', 'complete_prefix_role_counts',
    'reasons_over_128_count', 'group1_repair_slot_consumed',
    'new_calls_from_this_audit')}))
