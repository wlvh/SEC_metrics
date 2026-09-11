from pathlib import Path
import sys,json,hashlib,copy,subprocess,datetime
from decimal import Decimal
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path[:0]=[str(R/'scripts'),str(R)]
from vnext import r5_b06_structured as p
from vnext.r5_b06_scope import scope_inputs,precision_choice,validate_partition
from vnext.sources import raw_blob_record,source_reference_record,companyfacts_structured_facts
from vnext.specs import compile_spec_file
from vnext.batch_workflow import _registry_rows,repository_company_traits
from vnext.observations import scope_key
from vnext.run_store import load_frozen_run
O=Path(__file__).parent;spec=compile_spec_file(path=R/p.SPEC_PATH,dependency_specs={});checks=[];results=[]
for company in _registry_rows(repo_root=R):
 cid=company['company_id'];s=p.discover(data_root=R,company=company);scope={'entity_scope':'consolidated'};target={'company_id':cid,'period_start':s['target_period']['period_end'],'period_end':s['target_period']['period_end'],'accession':s['filing']['accessionNumber'],'entity':s['entity'],'scope':scope,'scope_key':scope_key(scope=scope)};sources=[]
 for proof in s['sources']:
  role='accession_xbrl' if proof['document_name'].endswith('_htm.xml') else 'companyfacts' if '/companyfacts/' in proof['source_url'] else None
  if not role:continue
  blob=raw_blob_record(repo_root=R,repo_relative_path=proof['request_repo_relative_path'],media_type='application/xml' if role=='accession_xbrl' else 'application/json');ref=source_reference_record(raw_blob=blob,company_id=cid,source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role=role,request_attempt_id=proof['request_attempt_id']);sources.append((role,ref,(R/proof['request_repo_relative_path']).read_bytes()))
 _,xref,xraw=next(x for x in sources if x[0]=='accession_xbrl');_,cfref,cfraw=next(x for x in sources if x[0]=='companyfacts');m=scope_inputs(raw=xraw,source=xref,spec=spec,target=target,filed=s['filing']['filingDate'],data_root=R)
 facts=companyfacts_structured_facts(raw_bytes=cfraw,source_reference=cfref,approved_concepts=p.concepts(spec),allowed_ciks=[s['entity']],include_instant=True);traits=repository_company_traits(repo_root=R,company_id=cid);r,t,o,a=p.resolve_primary(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=p.scope_warnings(xraw,spec,target),measurement=m)
 results.append({'company':cid,'result':r,'debt':a['debt'],'proven_subtotal':a['proven_debt_subtotal'],'reasons':a['reasons'],'source_sha256':hashlib.sha256(xraw).hexdigest(),'selected_observations':o,'precision':m.get('precision')})
 if cid=='pfizer':
  bad=copy.deepcopy(m);bad['unresolved']=[];br,bt,bo,ba=p.resolve_primary(spec=spec,target=target,traits=traits,facts=facts,measurement=bad);assert br['publication']=='WITHHELD' and 'DEBT_SET_COMPLETENESS_UNPROVEN' in ba['reasons'];checks.append({'case':'complete_false_empty_unresolved','result':br,'reasons':ba['reasons'],'type':'derived proof boundary injection; original source and core validator untouched'})
  assert a['proven_debt_subtotal']=='64795000000' and r['publication']=='WITHHELD';checks.append({'case':'Pfizer_precise61641_and_coarse62000_compatible','status':'PASS','actual_precision':next(x for x in m['precision'] if x['concept']=='us-gaap:LongTermDebtNoncurrent')})
 if cid in ['salesforce','macys','enphase_energy','southwest_airlines','paramount_skydance_paramount_global']:
  expect={'salesforce':(14974,59142),'macys':(2445,4860),'enphase_energy':(1204377,1087023),'southwest_airlines':(4901,7981),'paramount_skydance_paramount_global':(13658,11693)}[cid];assert Decimal(r['value'])==Decimal(expect[0])/Decimal(expect[1]) and r['quality']=='EXACT'
 if cid=='macys':
  bad=copy.deepcopy(m['model']);bad['inputs']['finance_lease']=bad['inputs']['principal']
  try:validate_partition(bad,['current_borrowings','noncurrent_borrowings','finance_leases']);raise AssertionError('duplicateconcept accepted')
  except ValueError as e:assert str(e)=='DEBT_FACT_REUSED_AS_DIFFERENT_ROLES';checks.append({'case':'distinct_roles_same_actual_concept','rejected':str(e)})
  assert scope_inputs(raw=xraw+b' ',source=xref,spec=spec,target=target,filed=s['filing']['filingDate'],data_root=R) is None
  br,bt,bo,ba=p.resolve_primary(spec=spec,target=target,traits=traits,facts=facts,measurement=None);assert br['publication']=='WITHHELD';checks.append({'case':'changed_source_cannot_borrow_registered_relationship','reasons':ba['reasons']})
for values in [[{'value':'61641000000','decimals':'-6','ordinal':1},{'value':'70000000000','decimals':'-9','ordinal':2}],[{'value':'1','decimals':'-6','ordinal':1},{'value':'2','decimals':'-6','ordinal':2}]]:
 try:precision_choice(values);raise AssertionError('precision conflict accepted')
 except ValueError as e:checks.append({'case':'precision_conflict','rejected':str(e)})
# Native read of a small unchanged historical sample, not a repeated whole publication run.
history=[]
for version,path in [('v1','/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-structured/complete-02/snapshot'),('v2','/Users/lyuhongwang/Documents/Codex/2026-09-11/r5-b06-followup/complete/snapshot')]:
 root=Path(path);rd=root/'runs/southwest_airlines';before={str(q.relative_to(rd)):hashlib.sha256(q.read_bytes()).hexdigest() for q in rd.rglob('*') if q.is_file()};rm,recs,_=load_frozen_run(run_dir=rd,repo_root=root/'data');after={str(q.relative_to(rd)):hashlib.sha256(q.read_bytes()).hexdigest() for q in rd.rglob('*') if q.is_file()};assert before==after;history.append({'version':version,'run_id':rm['run_id'],'result':next(r for r in recs if r['record_type']=='METRIC_RESULT'),'native_graph_replay':'PASS','bytes_unchanged':True})
paths=['scripts/vnext/r5_b06_scope.py','scripts/vnext/r5_b06_structured.py','scripts/vnext/specs.py','scripts/vnext/calculator.py','catalog/r5/B06_structured.md','config/r5_b06_debt_sets_v3.json','docs/evidence/r5_b06_scope/debt_scope_relationships.json'];x={'status':'PASS_BOUNDED_SCOPE_INCREMENT_CHECKS','reviewer':'independent Codex subtask /root/debt_reconciliation_review','time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parent_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'files':[{'path':v,'sha256':hashlib.sha256((R/v).read_bytes()).hexdigest()} for v in paths],'results':results,'checks':checks,'historical_native_reads':history,'business_calls':[0,0,0],'scope':'Current10 real-source function calls plus finite boundary injections and2historical native graph reads; no new complete candidate acceptance'};(O/'code-checks.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'status':x['status'],'results':[{k:r[k] for k in ['company','debt','proven_subtotal','reasons']} for r in results],'negative_checks':len(checks),'historical':len(history)},indent=2))
