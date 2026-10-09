import json,sys,time,hashlib,traceback
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(ROOT/'scripts'))
from vnext.regulatory_investigation_candidates import replay_regulatory_investigation_candidates
from vnext.normal_source_authority import verify_saved_source_proofs
OUT=Path(__file__).parent;BASE=Path('/tmp/sec_metrics_issue28_continuous/r5-r6-route/d03-material-authority-final')
def deny(event,args):
 if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):raise RuntimeError('D03_REVIEW_NO_NETWORK')
sys.addaudithook(deny)
if (OUT/'actual-replay.json').exists():raise SystemExit('Preserve first results')
rows=[]
for c in ['marriott_international','southwest_airlines','ford_motor_company','pfizer','jpmorgan_chase','salesforce','lumen_technologies','macys','paramount_skydance_paramount_global','enphase_energy']:
 start=time.monotonic();p=json.loads((BASE/(c+'.json')).read_text());a=p['arguments'];a['raw_bytes']=(ROOT/a['raw_blob']['storage_uri']).read_bytes()
 try:
  admission=verify_saved_source_proofs(data_root=ROOT,proofs=p['source_proofs']);b=replay_regulatory_investigation_candidates(bundle=p['bundle'],**a)
  facts=[{'fact':f,'excerpt':x['excerpt'],'context_excerpts':x['context_excerpts'],'requires_semantic_review':x['requires_semantic_review']} for x in b['candidates'] for f in x['facts'] if f['status']=='SOURCE_REPORTED_FACT']
  row={'company_id':c,'status':'PASS','source_sha256':hashlib.sha256(a['raw_bytes']).hexdigest(),'source_storage_uri':a['raw_blob']['storage_uri'],'admission':admission,'supported_facts':facts,'native_result_created':b['native_result_created'],'semantic_scope_completeness_asserted':b['semantic_scope_completeness_asserted']}
 except Exception as e:
  row={'company_id':c,'status':'FAILED','error':str(e)};(OUT/(c+'-actual-first-failure.log')).write_text(traceback.format_exc())
 row['elapsed_seconds']=round(time.monotonic()-start,3);rows.append(row);(OUT/'actual-replay.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(c,row['status'],len(row.get('supported_facts',[])),flush=True)
raise SystemExit(0 if all(r['status']=='PASS' for r in rows) else 1)
