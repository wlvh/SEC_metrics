"""Bounded read of Salesforce B03 D&A components in authenticated #28 originals."""
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.normal_run_v3 import prepare_case
from vnext.sources import resolve_repository_file
from vnext.text_results_v2 import _ReportedFactMetadata

with original_sources_only():
    case = prepare_case(data_root=ROOT, company_id='salesforce', metric_id='B03')
period = case['target_period']
assert period['period_start'] == '2025-02-01'
assert period['period_end'] == '2026-01-31'
assert case['admission']['source_credit'] == 'PREEXISTING_SAVED_ACQUISITIONS_ONLY'
references = {row['source_role']: row for row in case['references']}
blobs = {row['raw_asset_id']: row for row in case['source_records']
         if row['record_type'] == 'RAW_BLOB'}


def source(role):
    reference = references[role]
    blob = blobs[reference['raw_asset_id']]
    raw = resolve_repository_file(repo_root=ROOT,
        repo_relative_path=blob['storage_uri']).read_bytes()
    assert 'sha256:' + hashlib.sha256(raw).hexdigest() == reference['raw_asset_id']
    assert reference['accession'] == '0001108524-26-000060'
    return reference, raw


primary_ref, raw = source('target_primary')
facts_ref, facts_raw = source('companyfacts')
parsed = parse_accession_xbrl_source(raw_bytes=raw)
metadata = _ReportedFactMetadata()
metadata.feed(raw.decode('utf-8-sig'))
metadata.close()
assert metadata.ordinal == len(parsed.facts)
names = {
    'DepreciationAndAmortization',
    'DepreciationDepletionAndAmortization',
    'AmortizationOfAboveAndBelowMarketLeases',
    'FinanceLeaseRightOfUseAssetAmortization',
}
selected = []
primary_rou_impairment = []
rou_pattern = re.compile(r'(?:right.?of.?use|lease).*impair|impair.*(?:right.?of.?use|lease)', re.I)
for fact in parsed.facts:
    context = parsed.contexts[fact['context_ref']]
    if context['period_end'] != period['period_end']:
        continue
    local = fact['qualified_name'].split(':')[-1]
    if rou_pattern.search(local):
        primary_rou_impairment.append({'ordinal': fact['ordinal'],
            'concept': fact['qualified_name'], 'context_ref': fact['context_ref']})
    if local not in names or context['period_start'] != period['period_start']:
        continue
    assert not context['dimensions'] and not context['typed_dimension_count']
    assert str(int(context['entity_identifier'])) == '1108524'
    selected.append({'ordinal': fact['ordinal'],
        'concept': fact['qualified_name'], 'context_ref': fact['context_ref'],
        'reported_text': fact['text'], 'scale': fact['scale'],
        'decimals': metadata.facts[fact['ordinal']]['attrs'].get('decimals')})
assert {row['concept'].split(':')[-1] for row in selected} == names

companyfacts = json.loads(facts_raw)
current = []
companyfacts_rou_impairment = []
for namespace, concepts in companyfacts['facts'].items():
    for name, detail in concepts.items():
        for unit, rows in detail.get('units', {}).items():
            for row in rows:
                if row.get('accn') != primary_ref['accession'] or \
                   row.get('end') != period['period_end']:
                    continue
                if rou_pattern.search(name):
                    companyfacts_rou_impairment.append({
                        'concept': namespace + ':' + name, 'unit': unit,
                        'start': row.get('start'), 'value': row['val']})
                if name in names and row.get('start') == period['period_start']:
                    current.append({'concept': namespace + ':' + name,
                        'unit': unit, 'value': row['val'], 'start': row['start'],
                        'end': row['end'], 'accession': row['accn']})
assert {row['concept'].split(':')[-1] for row in current} == names
assert not primary_rou_impairment and not companyfacts_rou_impairment

start = raw.find(b'Includes amortization of intangible assets')
end_phrase = b'impairment of right-of-use assets'
end = raw.find(end_phrase, start) + len(end_phrase)
assert start >= 0 and end > start
span = raw[start:end]
statement = html.unescape(' '.join(re.sub(rb'<[^>]+>', b' ', span).decode(
    'utf-8', 'replace').split()))
assert 'impairment of right-of-use assets' in statement


def note_span(prefix):
    start = raw.find(prefix)
    assert start >= 0 and raw.find(prefix, start + 1) < 0
    end = raw.find(b'respectively.', start) + len(b'respectively.')
    assert end > start and end - start < 1500
    piece = raw[start:end]
    return {'start_byte': start, 'end_byte': end,
        'sha256': hashlib.sha256(piece).hexdigest(),
        'visible_text': html.unescape(' '.join(re.sub(rb'<[^>]+>', b' ',
            piece).decode('utf-8', 'replace').split()))}


fixed_note = note_span(b'Depreciation and amortization of fixed assets totaled')
acquired_note = note_span(
    b'Amortization of intangible assets resulting from business combinations')
assert '1.2' in fixed_note['visible_text']
assert '1.7' in acquired_note['visible_text']
body = {
    'record_type': 'ISSUE28_SALESFORCE_B03_EXACT_DA_COMPONENT_CENSUS',
    'scope': 'FY2026_SAME_ACCESSION_PRIMARY_INLINE_AND_COMPANYFACTS_ONLY',
    'source_admission': {key: case['admission'][key] for key in
        ('trusted_baseline_commit', 'source_manifest_sha256', 'source_credit')},
    'source_proof_count': len(case['source_proofs']),
    'period': period,
    'primary_source_reference_id': primary_ref['source_reference_id'],
    'primary_raw_sha256': primary_ref['raw_asset_id'][7:],
    'companyfacts_source_reference_id': facts_ref['source_reference_id'],
    'companyfacts_raw_sha256': facts_ref['raw_asset_id'][7:],
    'primary_facts': selected,
    'companyfacts_values': current,
    'cash_flow_note_raw_span': {'start_byte': start, 'end_byte': end,
        'sha256': hashlib.sha256(span).hexdigest(), 'visible_text': statement},
    'fixed_asset_note_raw_span': fixed_note,
    'acquired_intangible_note_raw_span': acquired_note,
    'separately_tagged_rou_impairment_in_scanned_period': {
        'primary': primary_rou_impairment,
        'companyfacts': companyfacts_rou_impairment},
    'exact_impairment_free_total_proven': False,
    'rounded_component_residual_is_not_impairment_amount': True,
    'old_b03_result_id_retained': case['results']['B03']['result_id'],
    'new_result_or_run_created': False,
    'new_real_calls': [0, 0, 0],
}
(HERE/'census.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'primary_fact_count': len(selected),
    'companyfacts_value_count': len(current),
    'separate_rou_impairment_tag_count': 0,
    'exact_clean_total_proven': False, 'calls': [0, 0, 0]},
    sort_keys=True), flush=True)
