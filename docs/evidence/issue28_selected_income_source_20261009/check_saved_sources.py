"""Explicit saved filings only: old/new native rows and visible short dates."""
import hashlib,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch

code,source_root=map(lambda p:Path(p).resolve(),sys.argv[1:3])
sys.path[:0]=[str(code),str(code/'scripts')]
from vnext.normal_governance_input import _Sources,_filings
from vnext.normal_annual_input import annual_period
from vnext.annual_update import saved_source
from vnext.canonical import strict_json_loads,canonical_json_bytes
from vnext.ordinary_income_input import native_income_reports as old
from vnext.selected_income_source_v1 import native_income_reports as new
from sec_urls import submissions_url

cases=[('marriott_international','1048286','2024-12-31'),('paramount_skydance_paramount_global','2041610','2025-12-31')]
reports=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
     patch('vnext.normal_candidates._prepare_b06',side_effect=AssertionError('No latest/current preparation')):
    for company,cik,end in cases:
        start=time.perf_counter()
        payload=strict_json_loads(text=saved_source(repo_root=source_root,url=submissions_url(cik=int(cik)))['raw'].decode())
        matched=[f for f in _filings(payload,inventory_name='saved_submissions') if f['form']=='10-K' and f['reportDate']==end]
        assert len(matched)==1
        filing=matched[0];reader=_Sources(source_root,company,cik)
        sources=reader.auditor_filing(filing)
        primary=next(s for s in sources if s['raw_blob']['media_type']=='text/html')
        period=annual_period(raw=primary['raw_bytes'],cik=cik,filing=filing)
        annual={'company_id':company,'entity':cik,'filing':filing,'table_input':{'target_period':period}}
        pairs=[]
        for item in sources:
            if item['raw_blob']['media_type'] not in {'text/html','application/xml'}:continue
            before=old(item,annual,['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'])
            actual=new(item,annual,['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'])
            assert before==actual
            enriched=new(item,annual,['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],check_visible_short_period=item['raw_blob']['media_type']=='text/html')
            checks=[row['visible_period_check'] for row in enriched if 'visible_period_check' in row]
            pairs.append({'media_type':item['raw_blob']['media_type'],'raw_sha256':hashlib.sha256(item['raw_bytes']).hexdigest(),
                          'rows':len(actual),'old_new_rows_equal':True,'rows_sha256':hashlib.sha256(canonical_json_bytes(value=actual)).hexdigest(),
                          'visible_checks':checks})
        assert len(pairs)==2
        if company=='paramount_skydance_paramount_global':
            checks=next(p['visible_checks'] for p in pairs if p['media_type']=='text/html')
            assert any(c['status']=='CONFLICT' and c['native_period']==['2025-08-08','2025-12-31']
                       and ['2025-08-07','2025-12-31'] in c['visible_periods'] for c in checks)
        report={'company':company,'selected_accession':filing['accessionNumber'],'source_period':period,
                'elapsed_seconds':time.perf_counter()-start,'original_pairs':pairs}
        reports.append(report)
        print(company,period,'pair rows',[p['rows'] for p in pairs],'seconds',round(report['elapsed_seconds'],3),flush=True)
result={'code_root':str(code),'source_root':str(source_root),'tested_tree':'main dae5 plus uncommitted explicit source helper/tests',
        'cases':reports,'current_preparation_forbidden':True,'new_business_calls':[0,0,0],'company_result_created':False}
(code/'docs/evidence/issue28_selected_income_source_20261009/saved-source-results.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS_SELECTED_SAVED_PRIMARY_XML_AND_SHORT_VISIBLE_CONFLICT',flush=True)
