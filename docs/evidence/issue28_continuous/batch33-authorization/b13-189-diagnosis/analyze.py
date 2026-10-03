"""Bounded offline audit of the first real B13 V3 failure at ledger ordinal 189."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from vnext.capacity_program_roles import verify_request_contract
from vnext.capacity_semantic_review import _restore_units


root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0189')
intent = json.loads((root/'intent.json').read_text())
terminal = json.loads((root/'terminal.json').read_text())
wire = json.loads((root/'wire/journal.json').read_text())
response = json.loads((root/'wire/raw-response.bin').read_text())
request = json.loads((root/'semantic-request.json').read_text())
source = json.loads((root/'source.json').read_text())
content = response['choices'][0]['message']['content']
assert intent['ordinal'] == 189 and intent['batch_group_id'] == 'B13:enphase_energy:0'
assert terminal['status'] == 'FAILED_TERMINAL' and not terminal['stop_reason']
assert wire['error_class'] == 'DEEPSEEK_RESPONSE_INVALID'
assert response['choices'][0]['finish_reason'] == 'length'
assert wire['usage']['output_tokens'] == 4096
assert len(request['required_candidate_assessments']) == 5

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
assert len(units) == len(request['units']) == 5
assert len(rows) == 141 and len({json.dumps(row, sort_keys=True) for row in rows}) == 141

required = {('B' if row['kind'] == 'VISIBLE_BLOCK' else 'F') + str(row['source_index'])
            for row in request['required_candidate_assessments']}
program, _ = verify_request_contract(
    request, _restore_units(request['units'], request['shared_source_dictionaries']), source)
program_refs = {('B' if evidence['kind'] == 'VISIBLE_BLOCK' else 'F') + str(evidence['source_index'])
                for finding in program['program_findings']
                for evidence in finding['resolved_evidence']}
prefix_refs = {ref for row in rows for ref in row[3]}
assert required <= prefix_refs | program_refs

role_counts = dict(Counter(row[0] for row in rows))
nonrequired_monetary = [row for row in rows
    if row[0] == 'monetary_credit_capacity' and not any(ref in required for ref in row[3])]
overlong = [{'role_label': row[0], 'source_refs': row[3], 'reason_characters': len(row[4])}
            for row in rows if len(row[4]) > 96]
assert len(nonrequired_monetary) == 115
assert {'B809'} <= program_refs and 'B809' not in prefix_refs
summary = {
    'record_type': 'ISSUE28_B13_189_OFFLINE_FAILURE_DIAGNOSIS',
    'original_ordinal': 189,
    'request_digest': intent['request_digest'],
    'intent_id': intent['intent_id'],
    'terminal_id': terminal['terminal_id'],
    'raw_response_sha256': hashlib.sha256((root/'wire/raw-response.bin').read_bytes()).hexdigest(),
    'request_sha256': hashlib.sha256((root/'semantic-request.json').read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256((root/'source.json').read_bytes()).hexdigest(),
    'terminal_status': terminal['status'],
    'stop_reason': terminal['stop_reason'],
    'wire_error_class': wire['error_class'],
    'provider_finish_reason': response['choices'][0]['finish_reason'],
    'usage': wire['usage'],
    'source_unit_count': len(request['units']),
    'required_candidate_count': len(required),
    'program_owned_required_refs': sorted(required & program_refs),
    'complete_prefix_finding_count': len(rows),
    'complete_prefix_unique_finding_count': len(rows),
    'complete_prefix_role_counts': role_counts,
    'nonrequired_monetary_credit_findings': len(nonrequired_monetary),
    'required_refs_not_in_complete_prefix_or_program': sorted(required - (prefix_refs | program_refs)),
    'reasons_over_96_characters': overlong,
    'response_complete_json': False,
    'original_failure_upgraded': False,
    'new_calls': [0, 0, 0],
    'inference': 'Nonrequired negative-background enumeration dominates the completed prefix and plausibly caused the 4096-token truncation; the source of the model behavior is not proven by this audit alone.'
}
destination = Path(__file__).with_name('summary.json')
destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: summary[k] for k in ('original_ordinal', 'provider_finish_reason',
    'complete_prefix_finding_count', 'nonrequired_monetary_credit_findings',
    'program_owned_required_refs', 'required_refs_not_in_complete_prefix_or_program',
    'response_complete_json', 'new_calls')}))
