"""Actual selected operating revenue FY2025 original and Facts; no company/Run or hidden answer."""
from pathlib import Path
import argparse,json,sys,socket,time
from unittest.mock import patch

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);a=p.parse_args()
program=Path(__file__).resolve().parents[3];sys.path.insert(0,str(program/'scripts'))
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.historical_dei import annual_period
from vnext.normal_governance_input import _Sources
from vnext.ordinary_source_authority import verify_ordinary_source_proofs
from vnext.selected_reported_revenue_v2 import reported_revenue_scope,admit_reported_revenue_facts
from vnext.sources import companyfacts_structured_facts
from vnext.canonical import sha256_bytes,content_hash
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from sec_urls import companyfacts_url

root=a.source_root.resolve();start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),\
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
    selected=resolve_period_selection(repo_root=root,company_id='southwest_airlines',fiscal_year=2025,rules_root=program)
    annual=prepare_historical_annual_input(repo_root=root,company_id='southwest_airlines',period_selection=selected,rules_root=program)
    original=annual.get('original_input',annual)
    reader=_Sources(root,'southwest_airlines',original['entity']);documents=reader.auditor_filing(original['filing'])
    primary=next(d for d in documents if d['source_reference']['source_role']=='target_primary')
    xmls=[d for d in documents if d['source_reference']['source_role']=='auditor_facts']
    assert len(xmls)==1
    args={'primary':primary,'xml':xmls[0],'annual':original,'approved_concepts':['us-gaap:Revenues','us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'],
          'namespace_policy':YEAR_OR_DATE_RELEASE,'annual_period_reader':annual_period}
    result=reported_revenue_scope(**args)
    old=result
    assert result['complete_scope_proven'] and len(result['reported_totals'])==1
    facts=reader.read(companyfacts_url(cik=int(original['entity'])),accession=original['filing']['accessionNumber'],
                      role='companyfacts',media_type='application/json')
    rows=companyfacts_structured_facts(raw_bytes=facts['raw_bytes'],source_reference=facts['source_reference'],
                                     approved_concepts=args['approved_concepts'],allowed_ciks=[original['entity']],include_instant=False)
    kept=admit_reported_revenue_facts(facts=rows,scope=result)
    total=result['reported_totals'][0]['total']
    actual=[f for f in kept if f['entity']==original['entity'] and f['accession']==original['filing']['accessionNumber']
            and f['concept'].casefold()==total['concept'].casefold()
            and (f['period_start'],f['period_end'],f['value'])==(total['period_start'],total['period_end'],total['value'])]
    assert actual
    proofs=list({content_hash(value=x):x for x in [*annual['source_proofs'],*[x['proof'] for x in reader.proofs.values()]]}.values())
    admission=verify_ordinary_source_proofs(data_root=root,proofs=proofs)
    elapsed=time.monotonic()-start
print(json.dumps({'program_root':str(program),'source_root':str(root),'fiscal_year':annual['table_input']['target_period']['fiscal_year'],
    'filing':original['filing'],'entity':original['entity'],'target_period':original['table_input']['target_period'],
    'primary_sha256':sha256_bytes(content=primary['raw_bytes']),'xml_sha256':sha256_bytes(content=xmls[0]['raw_bytes']),
    'old_scope_status':old['status'],'new_scope_status':result['status'],'new_scope_id':result['scope_id'],
    'total':total,'total_cell':result['reported_totals'][0]['total_cell'],
    'statement_scope':result['reported_totals'][0]['statement_scope'],
    'unit_sources':result['reported_totals'][0]['unit_sources'],'year_headers':result['reported_totals'][0]['year_headers'],
    'xml_check':result['reported_totals'][0]['xml_check'],'companyfacts_fact_ids':[x['fact_id'] for x in actual],
    'source_admission':admission,'source_proofs':proofs,'seconds':elapsed,
    'new_calls':[0,0,0],'company_result_created':False,'reference_used_as_input':False},ensure_ascii=False,indent=2))
