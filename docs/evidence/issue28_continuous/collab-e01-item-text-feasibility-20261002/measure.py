"""Try a fixed peer item-text reader on #28's ten saved current 8-K sets.

This is source-reading feasibility, not a confirmation, count, or native Run.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
PEER = '488a61734978adaa57e82ec0654e75a0af284cfb'
RULE = 'scripts/vnext/historical_event_items.py'
blob = subprocess.check_output(['git','rev-parse',PEER+':'+RULE],
                               cwd=ROOT,text=True).strip()
source = subprocess.check_output(['git','show',PEER+':'+RULE],cwd=ROOT)
with tempfile.TemporaryDirectory(prefix='issue28-e01-peer-item-read-') as temporary:
    module_path = Path(temporary)/'reader.py'
    module_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location('vnext._issue28_e01_peer_reader_pilot',
                                                   module_path)
    peer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(peer)

    roots = {
        'marriott_international':'issue28-marriott-current-36-20260929',
        'southwest_airlines':'issue28-southwest-current-36-cli-20260929',
        'ford_motor_company':'issue28-ford_motor_company-current-36-cli-20260929',
        'pfizer':'issue28-pfizer-current-36-cli-20260929',
        'jpmorgan_chase':'issue28-jpmorgan_chase-current-36-cli-20260929',
        'salesforce':'issue28-salesforce-current-36-cli-20261001',
        'lumen_technologies':'issue28-lumen_technologies-current-36-cli-20260929',
        'macys':'issue28-macys-current-36-cli-20260929',
        'paramount_skydance_paramount_global':
            'issue28-paramount_skydance_paramount_global-current-36-cli-20260929',
        'enphase_energy':'issue28-enphase_energy-current-36-cli-20260929'}
    assert len(roots) == 10
    companies = []
    for company,dirname in roots.items():
        paths = list((Path('/private/tmp')/dirname).glob(
            'state/**/metrics/E01/attempts/*/runs/E01/records.jsonl'))
        assert len(paths) == 1, (company,paths)
        path = paths[0]
        records = [json.loads(line) for line in path.read_bytes().splitlines()]
        result = next(row for row in records if row['record_type']=='METRIC_RESULT'
                      and row['metric_id']=='E01')
        references = {row['source_reference_id']:row for row in records
                      if row['record_type']=='SOURCE_REFERENCE'}
        blobs = {row['raw_asset_id']:row for row in records
                 if row['record_type']=='RAW_BLOB'}
        rows = []
        for claim in records:
            if (claim['record_type'] != 'DETERMINISTIC_VERIFIED_CLAIM'
                    or claim['attributes']['item_code'] not in {'1.01','2.01','8.01'}):
                continue
            attrs = claim['attributes']
            reference = references[attrs['primary_source_reference_id']]
            assert reference['source_role']=='fy_8k_primary'
            assert reference['accession']==attrs['accession']
            raw_blob = blobs[reference['raw_asset_id']]
            rawpath = ROOT/raw_blob['storage_uri']
            if not rawpath.exists():
                rawpath = path.parents[2]/'data'/raw_blob['storage_uri']
            raw = rawpath.read_bytes()
            assert len(raw)==raw_blob['byte_length']
            assert 'sha256:'+hashlib.sha256(raw).hexdigest()==raw_blob['raw_asset_id']
            row = {'accession':attrs['accession'],'item_code':attrs['item_code'],
                   'verified_claim_id':claim['verified_claim_id'],
                   'primary_source_reference_id':reference['source_reference_id'],
                   'primary_raw_asset_id':reference['raw_asset_id']}
            try:
                item = peer.item_text(raw_bytes=raw,item_code=attrs['item_code'])
                row.update(status='READABLE',heading=item['heading'],
                           start=item['start'],end=item['end'],
                           end_marker=item['end_marker'],
                           shares_the_body_of=item['shares_the_body_of'],
                           text_sha256=item['text_sha256'],
                           text_length=len(item['text']),
                           text_excerpt=item['text'][:260])
            except peer.EventItemTextError as error:
                row.update(status='UNRESOLVED',reason=str(error))
            rows.append(row)
        companies.append({'company_id':company,'old_result_id':result['result_id'],
                          'old_result_value':result['value'],
                          'candidate_item_count':len(rows),'items':rows})
    by_company = {row['company_id']:row for row in companies}
    pfizer = next(row for row in by_company['pfizer']['items']
                  if row['accession']=='0000078003-25-000159' and row['item_code']=='8.01')
    assert pfizer['status']=='READABLE' and 'Metsera' in pfizer['text_excerpt']
    ford = next(row for row in by_company['ford_motor_company']['items']
                if row['accession']=='0000037996-25-000067' and row['item_code']=='1.01')
    assert ford['status']=='READABLE' and '2.03' in ford['shares_the_body_of']
    output = {'record_type':'ISSUE28_TEN_COMPANY_PEER_E01_ITEM_TEXT_FEASIBILITY',
        'peer_fixed_commit':PEER,'peer_source_git_blob':blob,
        'peer_reader_wired_into_28':False,
        'companies':companies,
        'total_candidate_items':sum(x['candidate_item_count'] for x in companies),
        'readable_items':sum(row['status']=='READABLE' for x in companies
                             for row in x['items']),
        'unresolved_items':sum(row['status']=='UNRESOLVED' for x in companies
                               for row in x['items']),
        'old_result_credit_reused':False,'new_result_or_run':False,
        'new_real_calls':[0,0,0],
        'scope_limit':'Source-bound item text only; no M&A semantic answer, de-duplication, company count, provider execution or production credit.'}
    (HERE/'measure.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidate_items':output['total_candidate_items'],
                      'readable':output['readable_items'],
                      'unresolved':output['unresolved_items'],
                      'new_real_calls':[0,0,0]}))
