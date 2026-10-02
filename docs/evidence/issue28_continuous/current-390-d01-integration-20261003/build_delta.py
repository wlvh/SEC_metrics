"""Bind only two already reviewed D01 outcomes to the immutable parent index."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.records import validate_record
from current_view import BASE, PARENT, digest, read

HERE = Path(__file__).resolve().parent
CONTENT = BASE / 'collab-d01-content-20261002'
parent = read(PARENT)
summary = read(CONTENT / 'mechanical-corrected-summary.json')
conclusion = (CONTENT / 'conclusion.md').read_text()
changes = []
proofs = {str(path.relative_to(ROOT)): digest(path) for path in (
    CONTENT / 'conclusion.md', CONTENT / 'mechanical-corrected-summary.json',
    CONTENT / 'mechanical-receipts.md',
    BASE / 'collab-d01-page-boundary-20261002/independent-review-865d822/conclusion.md')}
for checked in summary['results']:
    company = checked['company_id']
    manifest = read(Path(checked['run_copy']) / 'manifest.json')
    receipt = read(Path(checked['run_copy']) / 'validation.json')
    original = Path(checked['original_attempt']) / 'runs/D01'
    records = [json.loads(line) for line in (original / 'records.jsonl').read_text().splitlines()]
    result_id = checked['mechanical_result']['result_id']
    result = next(r for r in records if r.get('result_id') == result_id)
    assert result['record_type'] == 'METRIC_RESULT'
    validate_record(record=result)
    validate_record(record=receipt)
    assert receipt == checked['mechanical_result']['receipt'] and receipt['status'] == 'PASSED'
    assert manifest['company_id'] == company and manifest['status'] == 'OPEN'
    assert result_id in conclusion and result['metric_id'] == 'D01' and result['quality'] == 'EXACT'
    assert len(result['text_payload']['items']) == 38
    assert (original / 'manifest.json').read_bytes() == (Path(checked['run_copy']) / 'manifest.json').read_bytes()
    assert read(original / 'validation.json')['status'] == 'NOT_RUN'
    for relative, bound in receipt['artifact_hashes'].items():
        source = original / relative
        assert digest(source) == bound['sha256'] and source.stat().st_size == bound['size']
    prior = next(row for row in parent['rows'] if row['company_id'] == company and row['metric_id'] == 'D01')
    assert prior['source_period'] == manifest['target_period']
    row = {**prior, 'value': result['value'], 'unit': result['unit'], 'quality': result['quality'],
           'applicability': result['applicability'], 'reason_code': result['reason_code'],
           'source_period': manifest['target_period'], 'run_status': 'OPEN',
           'implementation_identity': {'run_id': manifest['run_id'], 'result_id': result_id,
               'spec_closure_hash': result['spec_closure_hash'],
               'requirement_closure_hash': manifest['requirement_closure_hash'],
               'semantic_execution_root': checked['installed_code_data_root']},
           'evidence_type': 'SAVED_SEC_D01_NATIVE_RESULT_WITH_EXACT_CONTENT_REVIEW_AND_MECHANICAL_COPY_RECEIPT',
           'source_credit': 'SAVED_ORIGINAL_SEC_SOURCE_NO_NEW_ACQUISITION',
           'selected_evidence': {'path': str((HERE / 'delta.json').relative_to(ROOT)), 'selector': company + '/D01'},
           'public_row_status': 'TEXT_QUAL', 'current_head_full_revalidated': False,
           'formal_adoption_or_active_credit': False, 'new_real_result_this_review': False,
           'remaining_responsibility': 'Two saved FY2025 outcomes verified; automatic new inputs, full390 and production remain separate obligations'}
    changes.append({'company_id': company, 'metric_id': 'D01',
                    'prior_result_id': prior['implementation_identity']['result_id'],
                    'result_id': result_id, 'content_review_result_id': result_id,
                    'mechanical_receipt_status': receipt['status'],
                    'mechanical_receipt_id': receipt['validation_receipt_id'],
                    'native_result': result, 'mechanical_receipt': receipt, 'current_row': row})
delta = {'record_type': 'ISSUE28_CURRENT_390_D01_TWO_COORDINATE_DELTA',
         'parent_index': str(PARENT.relative_to(ROOT)), 'parent_index_sha256': digest(PARENT),
         'coordinate_count': 390, 'changed_coordinates': changes, 'proof_file_sha256': proofs,
         'all390_acceptance': False, 'production_authorized': False, 'new_calls': [0, 0, 0]}
target = HERE / 'delta.json'
if '--write' in sys.argv:
    assert not target.exists()
    target.write_text(json.dumps(delta, ensure_ascii=False, indent=2) + '\n')
else:
    assert read(target) == delta
print(json.dumps({'status': 'PASS_TWO_COORDINATE_NATIVE_PROOF_BINDING',
                  'changed': [(r['company_id'], r['result_id']) for r in changes],
                  'parent_bytes_retained': True, 'new_calls': [0, 0, 0]}, indent=2))
