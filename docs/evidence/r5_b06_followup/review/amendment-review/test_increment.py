from pathlib import Path
import sys,json,copy,hashlib,subprocess,datetime,xml.etree.ElementTree as ET,tempfile
from unittest.mock import patch
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext import r5_b06_amendments as a
from vnext.canonical import sha256_bytes
O=Path(__file__).parent;review=json.loads((R/'docs/evidence/r5_b06_followup/amendment_assessments.json').read_bytes());policy=json.loads((R/'config/r5_b06_structured_v1.json').read_bytes());results=[]
def run(name,fn,expected=None):
 try:
  value=fn()
  if expected:raise AssertionError('unexpected accept '+name)
  results.append({'case':name,'status':'PASS','actual':'NO_B06_SOURCE_IMPACT' if isinstance(value,dict) and value.get('decision') else str(value)[:120]})
 except ValueError as e:
  if not expected or expected not in str(e):raise
  results.append({'case':name,'status':'PASS','actual':str(e)})
for decision in review['decisions']:
 ob=Path(decision['original']['source_path']).read_bytes();ab=Path(decision['amendment']['source_path']).read_bytes();cik=int(next(x for x in decision['amendment']['identity'] if x['attributes']['name']=='dei:EntityCentralIndexKey')['text']);orig=decision['original']['filing'];am=decision['amendment']['filing'];cid=decision['company_id']
 def call(ob=ob,ab=ab,orig=orig,am=am,decision=decision,cik=cik):return a.verify_reviewed_impact(original_raw=ob,amendment_raw=ab,original=orig,amendment=am,cik=cik,decision=decision)
 run(cid+'_full_original_amendment',call)
 run(cid+'_changed_raw_same_accession',lambda:call(ab=ab+b' '),'AMENDMENT_REVIEWED_BYTES_CHANGED')
 bad=copy.deepcopy(am);bad['reportDate']='2024-12-31';run(cid+'_different_period',lambda:call(am=bad),'AMENDMENT_ORIGINAL_RELATION_CHANGED')
 run(cid+'_wrong_entity',lambda:call(cik=1),'AMENDMENT_ISSUER_OR_FORM_CHANGED')
 # Explicit synthetic boundary test: rehash outer reviewed metadata to reach structural checks.
 root=ET.fromstring(ab);tag='{http://www.xbrl.org/2013/inlineXBRL}nonFraction';f=ET.SubElement(root,tag,{'name':'us-gaap:LongTermDebt'});f.text='999';synthetic=ET.tostring(root);sd=copy.deepcopy(decision);sd['amendment']['sha256']=sha256_bytes(content=synthetic);v=a.document_identity(synthetic,'10-K/A',cik,am['reportDate']);sd['amendment']['complete_normalized_text_sha256']=v['complete_text_sha256'];sd['amendment']['inline_fact_count']=v['inline_fact_count'];run(cid+'_synthetic_financial_fact_rehashed',lambda:call(ab=synthetic,decision=sd),'AMENDMENT_FINANCIAL_FACTS_PRESENT')
 root=ET.fromstring(ab);ET.SubElement(root,'{http://www.w3.org/1999/xhtml}div').text='Item 8. Financial Statements';synthetic=ET.tostring(root);sd=copy.deepcopy(decision);v=a.document_identity(synthetic,'10-K/A',cik,am['reportDate']);sd['amendment']['sha256']=sha256_bytes(content=synthetic);sd['amendment']['complete_normalized_text_sha256']=v['complete_text_sha256'];sd['amendment']['body_headings']=[{'text':t} for t in v['headings']];run(cid+'_synthetic_financial_section_rehashed',lambda:call(ab=synthetic,decision=sd),'AMENDMENT_FINANCIAL_SECTION_PRESENT')
 selected={'entity':str(cik),'filing':orig,'later_amendments':[am]}
 result,block=a.assess(data=R,selected=selected,policy=policy);assert not block and result[0]['decision']=='NO_B06_SOURCE_IMPACT';results.append({'case':cid+'_actual_assess_saved_boundary','status':'PASS','actual':result[0]['decision']})
 with patch('vnext.annual_input._saved_source',side_effect=FileNotFoundError('synthetic missing source')):
  result,block=a.assess(data=R,selected=selected,policy=policy);assert block==['AMENDMENT_IMPACT_UNRESOLVED'];results.append({'case':cid+'_missing_raw_source','status':'PASS','actual':block})
 originalio=__import__('vnext.annual_input',fromlist=['_saved_source'])._saved_source
 def altered(**kwargs):
  p,b=originalio(**kwargs)
  return p,b+b' ' if kwargs.get('accession')==am['accessionNumber'] else b
 with patch('vnext.annual_input._saved_source',side_effect=altered):
  result,block=a.assess(data=R,selected=selected,policy=policy);assert block==['AMENDMENT_IMPACT_UNRESOLVED'] and result[0]['reason']=='AMENDMENT_COMPLETE_SOURCE_REVIEW_REQUIRED';results.append({'case':cid+'_changed_source_no_reviewer_credit','status':'PASS','actual':result[0]['reason']})
other=copy.deepcopy(policy);other['amendment_review_sha256']='bad';run('review_file_authority_hash_changed',lambda:a.assess(data=R,selected=selected,policy=other),'AMENDMENT_REVIEW_FILE_CHANGED')
record={'reviewer':'independent /root/amendment_review','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'code_sha256':{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in ['scripts/vnext/r5_b06_amendments.py','scripts/vnext/r5_b06_structured.py','scripts/vnext/r5_b06_publication.py','tests/vnext/test_r5_b06_followup.py']},'status':'PASS_AMENDMENT_INCREMENT_SCOPE','cases':results,'limitations':['Synthetic modifications at explicit source I/O boundary or low-level deterministic validator arguments only; no genuine approval invented.','No full native package replay performed by this test.','Complete source impact judgment reused own read-only source review, not a newly claimed human review.'],'business_calls':[0,0,0]}
(O/'increment-tests.json').write_text(json.dumps(record,indent=2)+'\n');print(len(results),'cases PASS')
