"""Reconcile existing, explicitly named native summaries; never rerun results."""
import csv, gzip, hashlib, json, tarfile
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'docs/evidence/issue28_continuous'
OUT=Path(__file__).parent
registry=json.loads((BASE/'completed-v14-batch-340/summary.json').read_text())
rows={}; consumed={}; reads=[]

def digest(raw):return hashlib.sha256(raw).hexdigest()
def read_json(name):
 p=BASE/name;raw=p.read_bytes();consumed[str(p.relative_to(ROOT))]=digest(raw)
 return json.loads(raw)
def evidence(name,detail=None):
 return {'path':str((BASE/name).relative_to(ROOT)),**({'selector':detail} if detail else {})}
def kind(result):
 if result.get('applicability')=='N_A_STRUCTURAL':return 'STRUCTURAL_NOT_APPLICABLE'
 if result.get('quality')=='NOT_MEANINGFUL':return 'NOT_MEANINGFUL'
 if result.get('quality') not in {'EXACT','APPROX'}:return 'IMPLEMENTATION_OR_SOURCE_PROOF_UNRESOLVED'
 return 'TEXT_RESULT' if result.get('unit')=='text' or 'text_payload' in result else 'NUMERIC_RESULT'
def native(c,name,implementation=None,source_credit='SAVED_ORIGINAL_SEC_SOURCE_NO_NEW_ACQUISITION', extra=None):
 cid=c.get('company_id') or c.get('company');mid=c.get('metric_id') or c.get('metric') or c['result']['metric_id'];key=(cid,mid)
 result=c.get('result',{})
 old=rows.get(key);history=[] if old is None else old['evidence_history']+[old['selected_evidence']]
 period=c.get('target_period') or c.get('period') or {k:result.get(k) for k in ['period_start','period_end']}
 selected=evidence(name, cid+'/'+mid)
 if extra:selected.update(extra)
 rows[key]={'company_id':cid,'metric_id':mid,'result_category':kind(result),
  'quality':result.get('quality'),'applicability':result.get('applicability'),
  'value':result.get('value'),'unit':result.get('unit'),'reason_code':result.get('reason_code'),
  'source_period':period,'source_period_basis':'BOUND_NATIVE_RESULT_AND_RECORDED_TARGET_PERIOD',
  'implementation_identity':{'run_id':c.get('run_id'),'result_id':result.get('result_id'),
    'spec_closure_hash':result.get('spec_closure_hash'),**(implementation or {})},
  'evidence_type':'SAVED_SEC_ORIGINAL_NATIVE_DEVELOPMENT_RESULT', 'source_credit':source_credit,
  'selected_evidence':selected,'evidence_history':history,'run_status':c.get('run_status','OPEN'),
  'public_row_status':c.get('public_row_status','SEE_BOUND_NATIVE_MATERIAL'),
  'historical_native_record_retained':bool(result),'new_real_result_this_review':False,
  'current_head_full_revalidated':False,'formal_adoption_or_active_credit':False,
  'real_disclosure_limitation_established':False,
  'remaining_responsibility':'Current affected-path evidence and unified update/release acceptance; no blanket rerun claim'}
 if source_credit=='RECORDED_TEST_ONLY':
  rows[key]['evidence_type']='REAL_SAVED_SEC_CONTENT_NATIVE_RESULT_WITH_RECORDED_SOURCE_ADMISSION'
  rows[key]['remaining_responsibility']='Preserve proved source-content calculation; recorded source admission is not a new live acquisition or real model result'
 if kind(result)=='IMPLEMENTATION_OR_SOURCE_PROOF_UNRESOLVED':
  rows[key]['remaining_responsibility']='Resolve the specific implementation/source-proof gap; do not count as valid disclosure absence'

def batch(name,impl=None):
 x=read_json(name)
 for c in x['coordinates']:native(c,name,impl)
 return x

class Archive:
 def __init__(self,folder,index='material-index.json',archive='material.tar.gz',blob=False):
  self.folder=folder;self.blob=blob;self.name=folder+'/'+archive
  p=BASE/folder/index;raw=p.read_bytes();consumed[str(p.relative_to(ROOT))]=digest(raw)
  self.index=json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
  self.tar=tarfile.open(BASE/self.name)
 def read(self,path):
  b=self.index['files'][path];member=b.get('archive_member') or ('blobs/'+b['sha256'] if self.blob else path)
  raw=self.tar.extractfile(member).read();assert digest(raw)==b['sha256'] and len(raw)==b['size']
  reads.append({'archive':str((BASE/self.name).relative_to(ROOT)),'logical_path':path,'archive_member':member,'sha256':b['sha256'],'size':b['size']})
  return raw
 def json(self,path):return json.loads(self.read(path))

batch('completed-v14-batch-340/summary.json',{'head':'1c9f5621e4e09f891d597fa7edcea970a3d434dc','evidence_date':'2026-09-12','current_code_replay_claim':False})
# Fixes are applied only from identified successor native outcomes, never from the old gap label alone.
batch('integrated-amendment-repairs/southwest/summary.json',{'requirement_closure_hash':'sha256:2c7f64c2b35fc477988ba0779d173d43e900db4aca53ba08a11af03a7db1acbd'})
batch('integrated-amendment-repairs/denominator/summary.json',{'requirement_closure_hash':'sha256:2c7f64c2b35fc477988ba0779d173d43e900db4aca53ba08a11af03a7db1acbd'})
# Current wrapper evidence for the three previously withheld positive B06 coordinates.
a=Archive('remaining-current-source-routes','positive-debt-routes-index.json.gz','positive-debt-routes.tar.gz')
for c in read_json('remaining-current-source-routes/positive-debt-summary.json')['rows']:
 cid=c['company_id'];manifest=a.json(cid+'/run/manifest.json');c={**c,'run_id':manifest['run_id']}
 native(c,'remaining-current-source-routes/positive-debt-summary.json',{'requirement_closure_hash':manifest['requirement_closure_hash']},c['source_credit'],
        {'archive':a.name,'run_records':cid+'/run/records.jsonl','run_manifest':cid+'/run/manifest.json'})
a.tar.close()
# Earlier actual native source runs remain lineage when a later wrapper uses recorded source admission.
for name in ['ordinary-note-debt/final-native-summary.json','ordinary-bond-leases/native-summary.json']:
 for c in read_json(name)['coordinates']:
  key=(c['company_id'],c['metric_id'])
  if key in rows and c['result']['quality']=='EXACT':
   rows[key].setdefault('prior_native_source_results',[]).append({'evidence':evidence(name,key[0]+'/'+key[1]),
      'run_id':c['run_id'],'result_id':c['result']['result_id'],'quality':c['result']['quality'],
      'source_period':c['target_period'],'fresh_execution_credit_this_review':False})
p=read_json('ordinary-inclusive-debt/validation-summary.json')
rows[('paramount_skydance_paramount_global','B06')].setdefault('prior_native_source_results',[]).append({
 'evidence':evidence('ordinary-inclusive-debt/validation-summary.json','native_material/cold'),
 'run_id':p['cold']['run_id'],'result_id':p['native_material']['result']['result_id'],
 'quality':p['native_material']['result']['quality'],'fresh_execution_credit_this_review':False})

# Finite selected coordinate and manifest reads from four existing source-acquisition archives.
for folder,summary in [('ordinary-document-identity','restored-coordinates.json'),('ordinary-history-identities','restored-and-regression-coordinates.json'),
                       ('ordinary-registered-event-runs','event-coordinates.json'),('ordinary-current-income','income-coordinates.json'),
                       ('ordinary-special-debt-scope','scoped-coordinates.json')]:
 a=Archive(folder)
 for short in read_json(folder+'/'+summary)['coordinates']:
  cid,mid=short['company'],short['metric'];prefix=short['evidence_folder'];path=prefix+'/coordinates/'+cid+'-'+mid+'.json'
  c=a.json(path);manifest=a.json(prefix+'/'+c['run_path']+'/manifest.json')
  assert c['run_id']==short['run_id'] and c['result']['quality']==short['quality']
  native(c,folder+'/'+summary,{'requirement_closure_hash':manifest['requirement_closure_hash']},short['source_credit'],
         {'archive':a.name,'coordinate_member':path,'run_records':prefix+'/'+c['run_path']+'/records.jsonl',
          'run_manifest':prefix+'/'+c['run_path']+'/manifest.json'})
  if 'limitations' in short:rows[(cid,mid)]['specific_source_or_policy_details']=short['limitations']
 a.tar.close()
# Six exact successor continuity outcomes, preserving the initial failed material.
name='ordinary-continuity-policy/native-continuity-material.tar.gz'
continuity_index=read_json('ordinary-continuity-policy/archive-members.json')['members']
with tarfile.open(BASE/name) as t:
 member='continuity-policy-native-second/summary.json';raw=t.extractfile(member).read();assert {'sha256':digest(raw),'size':len(raw)}==continuity_index[member];x=json.loads(raw)
 reads.append({'archive':str((BASE/name).relative_to(ROOT)),'archive_member':member,'sha256':digest(raw),'size':len(raw)})
 for c in x['coordinates']:
  mpath='continuity-policy-native-second/'+c['run_path']+'/manifest.json';manifest_raw=t.extractfile(mpath).read();assert {'sha256':digest(manifest_raw),'size':len(manifest_raw)}==continuity_index[mpath];manifest=json.loads(manifest_raw)
  native(c,name,{'requirement_closure_hash':manifest['requirement_closure_hash']},extra={'summary_member':member,'run_manifest':mpath,
     'run_records':'continuity-policy-native-second/'+c['run_path']+'/records.jsonl'})
# Preserve all 20 original lodging coordinates, overlay only the four actual later Runs.
batch('ordinary-lodging/ten-company-before-role-move/summary.json',{'requirement_closure_hash':'sha256:8f38c1458f3af391a63d89c82c2662bac5e5d6e99cdf7307f60bd242bdf66de3'})
batch('ordinary-lodging/current-native/summary.json',{'requirement_closure_hash':'sha256:f7352d6cffff8d28f18315c2acf2ff16205567b32d41cd526e2afb1327c95284'})
# Eight real-source, zero-model structural Runs. Read each exact result and period.
a=Archive('b13-content-guards','native-material-index.json','native-material.tar.gz',blob=True)
for short in read_json('b13-content-guards/structural-summary.json')['rows']:
 cid=short['company_id'];prefix='structural-3/'+cid+'/run/'
 manifest=a.json(prefix+'manifest.json');records=[json.loads(line) for line in a.read(prefix+'records.jsonl').splitlines()]
 result=next(r for r in records if r.get('record_type')=='METRIC_RESULT' and r['result_id']==short['result_id'])
 native({'company_id':cid,'metric_id':'B13','run_id':short['run_id'],'result':result,'target_period':manifest['target_period'],
         'public_row_status':short['row_status']},'b13-content-guards/structural-summary.json',
        {'requirement_closure_hash':manifest['requirement_closure_hash']},extra={'archive':a.name,'run_records':prefix+'records.jsonl','run_manifest':prefix+'manifest.json'})
a.tar.close()
# Current source preparation supplies periods only; recorded/model partials are never whole-coordinate credit.
census=read_json('request-context-counting/grouped-census.json')
for c in census['rows']:
 cid,mid=c['company_id'],c['metric_id']
 if mid=='B13' and c['status']=='N_A_STRUCTURAL':continue
 key=(cid,mid)
 assert key not in rows
 rows[key]={'company_id':cid,'metric_id':mid,'result_category':'VALIDATION_OR_IMPLEMENTATION_PENDING',
  'quality':None,'applicability':'APPLICABLE','value':None,'unit':None,'reason_code':
    'D03_NATIVE_RESULT_ROUTE_AND_REAL_VALIDATION_PENDING' if mid=='D03' else
    'D04_COMPLETE_CURRENT_REAL_VALIDATION_PENDING' if mid=='D04' else 'B13_COMPLETE_SOURCE_ROLE_AND_QUANTITY_VALIDATION_PENDING',
  'source_period':c['source_period'],'source_period_basis':'CURRENT_COMPLETE_SOURCE_PREPARATION_ONLY_NOT_RESULT',
  'implementation_identity':{'source_id':c['source_id'],'request_context_format':c['request_context_format'],
      'implementation_files':'docs/evidence/issue28_continuous/request-context-counting/implementation-files.json'},
  'evidence_type':'SOURCE_PREPARATION_WITH_SEPARATE_RECORDED_OR_SYNTHETIC_DEVELOPMENT_EVIDENCE',
  'source_credit':'SEE_ORIGINAL_SOURCE_PROOFS_NO_MODEL_RESULT_CREDIT','selected_evidence':evidence('request-context-counting/grouped-census.json',cid+'/'+mid),
  'evidence_history':[],'historical_native_record_retained':False,'new_real_result_this_review':False,'current_head_full_revalidated':False,
  'formal_adoption_or_active_credit':False,'real_disclosure_limitation_established':False,
  'remaining_responsibility':'Complete current source-dependent native response/Review/Run validation; retain partials and failures at original scope'}
 if mid=='B13':
  rows[key]['development_evidence']=[evidence('b13-current-source-roles/README.md'),evidence('b13-quantity-integration/README.md'),evidence('b13-source-indexing/original68-content-audit.json')]
  rows[key]['original_68_business_result_credit']=False
 if mid=='D04':rows[key]['development_evidence']=[evidence('review-5207290213/after.json'),evidence('review-5207290213/d04-reference-native.log')]
 if mid=='D03':rows[key]['development_evidence']=[evidence('resume-2026-09-14/d03-source-fact-final.json')]
# Five residual old-batch coordinates remain specific proof/development obligations, not certified absence.
limitations={
 ('southwest_airlines','B06'):('24m supplier financing taxonomy versus Deferred supplier credits in accrued liabilities; economic inclusion/exclusion remains unproved','ordinary-financing-inventory/README.md'),
 ('pfizer','B06'):('64.795bn borrowing subtotal reconstructed; complete financing-lease inclusion has not been proved. No standalone lease fact is not zero','ordinary-borrowing-composition/README.md'),
 ('jpmorgan_chase','B06'):('970.329bn reported bank financing subtotal; finance-lease completeness not established, not whole-SEC absence','ordinary-special-debt-scope/README.md'),
 ('ford_motor_company','B06'):('21.919bn industrial debt identified; same-scope attributable parent equity not established','ordinary-special-debt-scope/README.md'),
 ('paramount_skydance_paramount_global','C04'):('Comparable auditor facts missing in the implemented route; no independent full-source absence proof found in the whitelisted successor evidence','completed-v14-batch-340/summary.json')}
for key,(detail,path) in limitations.items():
 row=rows[key];row['result_category']='IMPLEMENTATION_OR_SOURCE_PROOF_UNRESOLVED';row['specific_source_or_policy_details']=detail
 row['fact_limitation_evidence']=[evidence(path)];row['real_disclosure_limitation_established']=False
 row['remaining_responsibility']='Distinguish actual source ambiguity from unsupported implementation through complete bounded source proof; no coordinate completion credit from refusal'
# Two complete real D04 source tasks, preserving the original model and Run identities.
for company in ('ford_motor_company','pfizer'):
 name='d04-indexed-unit-response/live/'+company+'-D04-summary.json'
 c=read_json(name)
 cold=read_json('d04-indexed-unit-response/live/'+('ford' if company=='ford_motor_company' else 'pfizer')+'-cold.json')
 assert c['native_company_metric_created'] and c['all_source_requests_accepted'] and not c['failed_requests']
 assert c['receipt']['semantic_assessment_mode']=='LIVE' and cold['semantic_assessment_mode']=='LIVE'
 assert cold['result_id']==c['result']['result_id'] and cold['run_id']==c['run_id']
 assert c['result']['reason_code']=='D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE' and c['row']['status']=='TEXT_QUAL'
 native({**c,'target_period':c['source_period'],'public_row_status':c['row']['status']},name,
        {'execution_requirement_closure_hash':'sha256:be11771764276962cfabd7b51c551e8d12f596f15c9c4b7276665cf4cd1a2c29',
         'head_when_executed':'ddecbf03b98c9c40f24be87c8181ae9077cb7ae3',
         'uncommitted_execution_files_bound':True},
        source_credit='ORIGINAL_SAVED_SEC_SOURCES_WITH_LIVE_NATIVE_ASSESSMENTS')
 row=rows[(company,'D04')]
 row.update(result_category='DEFINED_SCOPE_TEXT_STATEMENT',
     evidence_type='COMPLETE_LIVE_NATIVE_SOURCE_ASSESSMENT_RUN_AND_COLD_REPLAY',
     new_real_result_this_review=True,executed_binding_native_and_cold_verified=True,
     source_period_basis='BOUND_COMPLETE_REAL_NATIVE_RESULT',
     derived_public_statement=c['row']['notes'],native_result_publication=c['result']['publication'],
     remaining_responsibility='Carry this valid source statement into normal update and unified release; current later runtime changes require scoped revalidation, not new model credit.')
 row['cold_replay_evidence']=evidence('d04-indexed-unit-response/live/'+('ford' if company=='ford_motor_company' else 'pfizer')+'-cold.json')
for company,folder,ordinal in [('enphase_energy','live',82),('ford_motor_company','live-ford-b13',94)]:
 name='d04-indexed-unit-response/'+folder+'/call-%04d.json'%ordinal
 failure=read_json(name);assert failure['status']=='FAILED_TERMINAL'
 rows[(company,'B13')].update(reason_code='B13_REAL_RESPONSE_REJECTED_NO_COMPLETE_COORDINATE',
     actual_failed_request=evidence(name),
     remaining_responsibility='Resolve the demonstrated quantity-role response failures; original failed calls retain no usable result credit. Do not relabel implementation/model failure as a disclosure limitation.')
# Original 53 gaps are historical lineage only. Successor native records supersede their old unresolved labels.
gaps=read_json('resume-2026-09-13/current-gap-index.json')
for old in gaps['rows']:
 row=rows[(old['company_id'],old['metric_id'])]
 row['historical_340_gap']={'reason':old['historical_reason'],'prior_triage':old['current_triage'],
    'superseded_by_later_native_evidence':row['result_category']!='IMPLEMENTATION_OR_SOURCE_PROOF_UNRESOLVED'}
companies=list(dict.fromkeys(c['company_id'] for c in registry['coordinates']))
metrics=sorted(set(k[1] for k in rows))
assert len(companies)==10 and len(metrics)==39 and len(rows)==390
assert set(rows)=={(c,m)for c in companies for m in metrics}
ordered=[rows[(c,m)] for c in companies for m in metrics]
counts=dict(Counter(r['result_category'] for r in ordered))
body={'record_type':'ISSUE28_CURRENT_390_EVIDENCE_RECONCILIATION','as_of':'2026-09-15_THROUGH_REAL_CALL94_AND_TWO_D04_COLD_READS',
 'coordinate_count':390,'full_current_head_reexecution':False,'full_issue_acceptance':False,'production_authorized':False,
 'new_calls_for_index':[0,0,0],'categories':counts,'native_record_count':sum(r['historical_native_record_retained'] for r in ordered),
 'native_result_or_valid_noncomputing_state_count':sum(r['result_category'] in {'NUMERIC_RESULT','TEXT_RESULT','DEFINED_SCOPE_TEXT_STATEMENT','STRUCTURAL_NOT_APPLICABLE','NOT_MEANINGFUL'} for r in ordered),
 'recorded_source_admission_numeric_entries':sum(r['source_credit']=='RECORDED_TEST_ONLY' and r['result_category']=='NUMERIC_RESULT' for r in ordered),
 'real_disclosure_limitation_established_count':sum(r['real_disclosure_limitation_established'] for r in ordered),
 'historical_53_replaced_by_later_native_evidence':sum(r.get('historical_340_gap',{}).get('superseded_by_later_native_evidence',False)for r in ordered),
 'interpretation':'Existing saved-source native records, current limitations, and pending validation kept separate. Internal Result publication flags do not grant production adoption. Recorded source-admission and model-response evidence are not upgraded to fresh real execution credit.',
 'rows':ordered,'source_summary_sha256':consumed,'selected_archive_reads':reads}
(OUT/'current-390.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
fields=['company_id','metric_id','result_category','quality','applicability','value','unit','reason_code','source_period','implementation_identity','evidence_type','source_credit','selected_evidence','current_head_full_revalidated','real_disclosure_limitation_established','remaining_responsibility']
with (OUT/'current-390.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in ordered:w.writerow({k:json.dumps(r.get(k),ensure_ascii=False) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in fields})
print(json.dumps({k:v for k,v in body.items()if k not in {'rows','source_summary_sha256','selected_archive_reads'}},ensure_ascii=False,indent=2))
