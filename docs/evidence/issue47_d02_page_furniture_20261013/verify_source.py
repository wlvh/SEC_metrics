"""Two existing Ford source controls; not a company pipeline or model caller."""
import argparse
import json
import time
from pathlib import Path

from vnext import d02_text_results_v3 as core
from vnext.canonical import content_hash
from vnext.normal_governance_input import _Sources
from vnext.specs import compile_spec_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--fiscal-year',type=int,choices=(2024,2025),required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError(args.receipt)
    reader=_Sources(args.source_root,'ford_motor_company','37996')
    index=reader.read('https://data.sec.gov/submissions/CIK0000037996.json',
        role='sec_submissions_inventory',media_type='application/json')
    recent=json.loads(index['raw_bytes'])['filings']['recent']
    end=str(args.fiscal_year)+'-12-31'
    indices=[i for i,form in enumerate(recent['form'])
             if form=='10-K' and recent['reportDate'][i]==end]
    assert len(indices)==1
    filing={k:v[indices[0]] for k,v in recent.items()}
    source=reader.primary(filing);ref=source['source_reference'];blob=source['raw_blob']
    target={'company_id':'ford_motor_company','entity':'37996',
        'accession':filing['accessionNumber'],'period_start':str(args.fiscal_year)+'-01-01',
        'period_end':end,'scope':core.SCOPES['D02']}
    target['scope_key']=content_hash(value=target['scope'])
    inputs={'target':target,'source_references':[ref],
        'raw_blobs':{blob['raw_asset_id']:blob},
        'raw_bytes_by_id':{blob['raw_asset_id']:source['raw_bytes']},
        'source_filings':{ref['source_reference_id']:filing}}
    start=time.perf_counter()
    before=core.prepare_business_text_sources(metric_id='D02',**inputs)
    before_seconds=time.perf_counter()-start
    start=time.perf_counter()
    after=core.prepare_business_text_sources(metric_id='D02',d02_page_furniture=True,**inputs)
    after_seconds=time.perf_counter()-start
    key=ref['source_reference_id'];bp=before['proposals'][key];ap=after['proposals'][key]
    assert before['documents']==after['documents']
    assert bp['D03']==ap['D03']
    assert all(c in bp['D02']['candidates'] for c in ap['D02']['candidates'])
    compiled=compile_spec_file(path=Path(core.__file__).resolve().parents[2]/
        'catalog/r6/D02_legal_disclosures_v1.md',dependency_specs={})
    candidate=core.create_deterministic_text_candidate(compiled_spec=compiled,
        d02_page_furniture=True,**inputs)
    evidence=core.build_text_evidence(compiled_spec=compiled,candidate=candidate,
        d02_page_furniture=True,**inputs)
    assert evidence['status']=='PASS'
    receipt={'source_only':True,'fiscal_year':args.fiscal_year,'target':target,
        'source_binding':reader.proofs[key],'before':len(bp['D02']['candidates']),
        'after':len(ap['D02']['candidates']),'before_seconds':before_seconds,
        'after_seconds':after_seconds,'removed':ap.get('d02_page_furniture'),
        'documents_unchanged':True,'D03_unchanged':True,'evidence_status':evidence['status'],
        'model_answer_not_loaded':True,'new_metric_result_or_run_created':False,
        'new_calls':[0,0,0]}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('fiscal_year','before','after','evidence_status','new_calls')}))


if __name__=='__main__':
    main()
