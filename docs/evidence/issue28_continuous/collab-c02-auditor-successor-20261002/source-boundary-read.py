"""Authenticate the two repair boundaries and a separate unjudged paragraph."""
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
path=next(Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929').glob(
    'state/jpmorgan_chase/metrics/C02/attempts/*/runs/C02/records.jsonl'))
records=[json.loads(row) for row in path.read_bytes().splitlines()]
candidate=next(row for row in records if row['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
references={row['source_reference_id']:row for row in records if row['record_type']=='SOURCE_REFERENCE'}
blobs={row['raw_asset_id']:row for row in records if row['record_type']=='RAW_BLOB'}
readings={
    3367:('EXCLUDE_KNOWN_DEFECT','The independence belongs to the external auditor; the paragraph reports its retention and tenure, no board or member composition fact.'),
    3409:('INCLUDE_POSITIVE','Four non-management Audit Committee directors, each member independent, financially literate and an audit committee financial expert are explicit composition/qualification facts.'),
    3436:('SEPARATE_UNJUDGED_SCOPE_QUESTION','The paragraph assigns management/auditor/Internal Audit responsibilities, then says committee members do not practise accounting and monitor the processes. It appears to describe duties; whether the final negative professional-practice statement is a qualification fact needs contract-based peer alignment. No new defect or acceptance credit is recorded here.'),
}
rows=[]
for index,(disposition,why) in readings.items():
    claim=next(row for row in candidate['selected'].values() if row['block_index']==index)
    reference=references[claim['source_reference_id']];blob=blobs[reference['raw_asset_id']]
    source=ROOT/blob['storage_uri']
    if not source.exists():source=path.parents[2]/'data'/blob['storage_uri']
    raw=source.read_bytes();span=raw[claim['raw_start_byte']:claim['raw_end_byte']]
    assert len(raw)==blob['byte_length']
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==blob['raw_asset_id']
    assert hashlib.sha256(span).hexdigest()==claim['raw_span_sha256'].removeprefix('sha256:')
    rows.append({'block_index':index,'source_accession':reference['accession'],
        'source_reference_id':reference['source_reference_id'],
        'raw_asset_id':blob['raw_asset_id'],'raw_span_sha256':claim['raw_span_sha256'],
        'text':claim['text'],'own_scope_reading':disposition,'why':why})
spec=ROOT/'catalog/r6/C02_board_disclosures_v3.md'
result={'record_type':'ISSUE28_C02_AUDITOR_REPAIR_SOURCE_BOUNDARIES',
    'company_id':'jpmorgan_chase','period_end':'2025-12-31',
    'approved_scope_source':str(spec.relative_to(ROOT)),
    'scope_spec_sha256':hashlib.sha256(spec.read_bytes()).hexdigest(),
    'readings':rows,'whole_result_accepted':False,'new_result_created':False,
    'new_real_calls':[0,0,0]}
(HERE/'source-boundary-read.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'authenticated_blocks':[x['block_index'] for x in rows],
    'new_defect_for_3436':False,'whole_result_accepted':False,'calls':[0,0,0]}))
