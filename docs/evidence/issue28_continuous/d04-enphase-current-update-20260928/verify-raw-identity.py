"""Compare installed Enphase D04 input with six original call identities."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
ORIGINAL = ROOT/'docs/evidence/issue28_continuous/batch33-authorization/d04-enphase-real'
HISTORY = Path('/private/tmp/issue28-d04-enphase-normal-b868-20260928/metrics/D04')


def read(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


first = read(HERE/'result.json')
finish = read(ORIGINAL/'finish-summary.json')
original_calls = {int(row['ledger_ordinal']): row
                  for row in read(ORIGINAL/'calls.json')['calls']}
attempt = HISTORY/'attempts'/first['successful_attempt']
installed = attempt/'data'
manifest = read(attempt/'runs/D04/manifest.json')
key = manifest['run_id'].split(':')[-1]
binding = read(installed/'ordinary_integrated_bindings'/f'{key}.json')
registered_path = installed/'config/ordinary_going_concern_assessment.json'
registered = read(registered_path)
assert registered['source_id'] == finish['source_id'] == \
    binding['input_binding']['source_id']
assert registered['input_record_id'] == \
    binding['input_binding']['assessment_input_id']
assert registered['input_record_id'] != finish['assessment_input_id']
assert registered['mode'] == binding['input_binding']['mode'] == 'LIVE'
assert registered['requirement_closure_hash'] == manifest['requirement_closure_hash']
assert registered['assessment']['all_source_requests_accepted'] is True
assert not registered['assessment']['failed_requests']
assert len(registered['native_requests']) == 6
assert set(original_calls) == set(finish['original_call_ordinals']) == \
    {row['ordinal'] for row in registered['native_requests']}

proofs = []
for row in sorted(registered['native_requests'], key=lambda item: item['ordinal']):
    ordinal = row['ordinal']
    original = original_calls[ordinal]
    call = LEDGER/'calls'/f'{ordinal:04d}'
    source_raw = (call/'source.json').read_bytes()
    request_raw = (call/'semantic-request.json').read_bytes()
    assistant_raw = (call/'wire/assistant-output.bin').read_bytes()
    raw_response = (call/'wire/raw-response.bin').read_bytes()
    wire = read(call/'wire/journal.json')
    assert registered['source_snapshot'] == json.loads(source_raw)
    assert row['semantic_request'] == json.loads(request_raw)
    assert row['assistant_output'].encode('utf-8') == assistant_raw
    assert row['intent'] == read(call/'intent.json')
    assert row['terminal'] == read(call/'terminal.json')
    assert row['wire'] == wire
    assert row['request_id'] == original['request_id'] == \
        row['semantic_request']['request_id']
    assert row['intent']['request_digest'] == original['request_digest']
    assert row['terminal']['status'] == original['terminal_status'] == 'SUCCEEDED'
    assert row['acceptance_receipt']['response_body_sha256'] == \
        wire['assistant_output_sha256'] == sha(assistant_raw)
    assert wire['raw_response_sha256'] == sha(raw_response)
    proofs.append({'ordinal': ordinal, 'request_id': row['request_id'],
        'request_digest': original['request_digest'],
        'source_sha256': sha(source_raw), 'semantic_request_sha256': sha(request_raw),
        'assistant_output_sha256': sha(assistant_raw),
        'raw_response_sha256': sha(raw_response),
        'wire_id': wire['wire_id'],
        'acceptance_receipt_id': row['acceptance_receipt']['acceptance_receipt_id'],
        'installed_assistant_bytes_equal_original': True,
        'installed_request_and_terminal_equal_original': True})

report = {'record_type': 'ISSUE28_ENPHASE_D04_INSTALLED_RAW_IDENTITY_AUDIT',
    'status': 'PASS_SIX_ORIGINAL_RESPONSES_AND_JSON_CONTENT_BOUND_TO_CURRENT_RUN',
    'company_id': 'enphase_energy', 'metric_id': 'D04',
    'original_source_id': finish['source_id'],
    'original_assessment_input_id': finish['assessment_input_id'],
    'current_assessment_input_id': registered['input_record_id'],
    'current_run_id': manifest['run_id'],
    'current_result_id': first['result_id'],
    'installed_registration_sha256': sha(registered_path.read_bytes()),
    'original_calls_summary_sha256': sha((ORIGINAL/'calls.json').read_bytes()),
    'call_proofs': proofs,
    'original_call_files_before_after_full_tree_hashed_during_update': False,
    'new_real_calls': [0, 0, 0], 'production_authorized': False}
(HERE/'raw-identity.json').write_text(json.dumps(report,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': report['status'],
                  'ordinals': [row['ordinal'] for row in proofs],
                  'source_id': report['original_source_id'],
                  'current_run_id': report['current_run_id'],
                  'current_input_differs_from_original_input_id':
                      report['current_assessment_input_id'] !=
                      report['original_assessment_input_id']},
                 ensure_ascii=False))
