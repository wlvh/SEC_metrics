"""Measure a compact complete-reference B13 scan on the saved 191 group."""
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
import re
import sys
from types import SimpleNamespace

CODE = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path.insert(0, str(CODE/'scripts'))

from vnext.canonical import canonical_json_bytes, strict_json_file
from vnext.capacity_reference_contract import restore_base_request, upgrade_request
from vnext.capacity_two_stage import (_reference_inventory,
    coverage_scan_request, validate_coverage_scan)
from vnext.continuous_request_context import measure_request
from vnext.continuous_semantic_calls import request_body


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ranges_for_all_refs(inventory):
    grouped = defaultdict(list)
    for ref, owner in inventory.items():
        matched = re.fullmatch(r'([BF])(\d+)', ref)
        if matched is None:
            raise ValueError('This actual 191 group has unexpected supplements')
        grouped[(matched[1], owner)].append(int(matched[2]))
    ranges = []
    for (kind, owner), values in sorted(grouped.items()):
        values.sort()
        start = previous = values[0]
        for value in values[1:]:
            if value != previous + 1:
                ranges.append([kind, owner, start, previous + 1])
                start = value
            previous = value
        ranges.append([kind, owner, start, previous + 1])
    return ranges


def main():
    watched = [LEDGER/'claims.jsonl']
    for ordinal in (191, 192):
        path = LEDGER/'calls'/('%04d' % ordinal)
        watched.extend(path/name for name in
            ('semantic-request.json', 'source.json', 'terminal.json'))
    before = {str(path): digest(path) for path in watched}
    original = strict_json_file(path=LEDGER/'calls/0191/semantic-request.json')
    v4 = upgrade_request(restore_base_request(original), compact=True,
                         role_labels=True, relevance_scope=True)
    inventory = _reference_inventory(v4)
    ranges = ranges_for_all_refs(inventory)
    response = {'units_reviewed': list(range(len(v4['units']))),
        'candidate_refs': [], 'unresolved_refs': [],
        'excluded_ref_ranges': ranges}
    scan = coverage_scan_request(v4)
    raw_response = canonical_json_bytes(value=response)
    checked = validate_coverage_scan(request=v4,
        scan_request_value=scan, raw_response=raw_response)
    measured = measure_request(request_body(scan,
        SimpleNamespace(model='deepseek-flash')), require_reference=True)
    assert len(v4['required_candidate_assessments']) == 0
    assert checked['source_reference_count'] == 1276
    assert checked['excluded_count'] == 1276
    assert len(ranges) == 4 and measured['fits']
    assert checked['absence_established'] is False
    assert checked['model_relevance_proven'] is False
    assert checked['native_credit'] is False

    def reject(value, expected):
        try:
            validate_coverage_scan(request=v4, scan_request_value=scan,
                raw_response=canonical_json_bytes(value=value))
        except ValueError as error:
            assert expected in str(error), (expected, str(error))
            return str(error)
        raise AssertionError('Changed scan was accepted: ' + expected)

    gap = json.loads(json.dumps(response))
    gap['excluded_ref_ranges'][-1][-1] -= 1
    gap_reason = reject(gap, 'B13_COVERAGE_SCAN_SOURCE_GAP')
    wrong_owner = json.loads(json.dumps(response))
    wrong_owner['excluded_ref_ranges'][0][1] = 3
    wrong_owner_reason = reject(wrong_owner,
        'B13_COVERAGE_SCAN_RANGE_NOT_ORIGINAL_OR_OVERLAPS')
    candidate_overlap = json.loads(json.dumps(response))
    candidate_overlap['candidate_refs'] = ['B1884']
    overlap_reason = reject(candidate_overlap,
        'B13_COVERAGE_SCAN_RANGE_NOT_ORIGINAL_OR_OVERLAPS')
    after = {str(path): digest(path) for path in watched}
    assert before == after
    body = {'record_type': 'ISSUE28_B13_191_COMPLETE_REFERENCE_COVERAGE_OFFLINE',
        'tested_module_sha256': digest(CODE/'scripts/vnext/capacity_two_stage.py'),
        'tested_v14_manifest_sha256': digest(CODE/'requirements/issue_28_v14/baseline_manifest.json'),
        'tested_scalability_policy_sha256': digest(CODE/'config/ordinary_scalability_exemptions_v1.json'),
        'original_191_request_sha256': before[str(LEDGER/'calls/0191/semantic-request.json')],
        'original_192_request_sha256': before[str(LEDGER/'calls/0192/semantic-request.json')],
        'original_191_terminal_status': strict_json_file(
            path=LEDGER/'calls/0191/terminal.json')['status'],
        'original_192_terminal_status': strict_json_file(
            path=LEDGER/'calls/0192/terminal.json')['status'],
        'v4_prior_request_id': v4['request_id'],
        'new_scan_request_id': scan['request_id'],
        'source_id': v4['source_id'],
        'source_reference_count': checked['source_reference_count'],
        'candidate_count': checked['candidate_count'],
        'excluded_count': checked['excluded_count'],
        'excluded_ranges': ranges,
        'synthetic_response_bytes': len(raw_response),
        'new_request_input_tokens': measured['input_tokens'],
        'new_request_output_reserve_tokens': measured['output_reserve_tokens'],
        'new_request_context_tokens': measured['context_tokens'],
        'new_request_fits_current_limit': measured['fits'],
        'negative_gap_reason': gap_reason,
        'negative_wrong_owner_reason': wrong_owner_reason,
        'negative_candidate_overlap_reason': overlap_reason,
        'saved_originals_unchanged': before == after,
        'model_relevance_proven': False,
        'absence_established': False,
        'native_result_or_run_created': False,
        'new_real_calls': [0, 0, 0]}
    output = os.environ.get('ISSUE28_EXERCISE_OUTPUT', 'exercise.json')
    assert output in {'exercise.json', 'exercise-current.json'}
    (HERE/output).write_text(json.dumps(body, ensure_ascii=False,
        indent=2)+'\n')
    print(json.dumps({key: body[key] for key in (
        'source_reference_count', 'candidate_count', 'excluded_count',
        'synthetic_response_bytes', 'new_request_context_tokens',
        'new_request_fits_current_limit', 'saved_originals_unchanged',
        'new_real_calls')}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
