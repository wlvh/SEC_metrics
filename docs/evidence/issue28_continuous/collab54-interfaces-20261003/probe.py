"""Small saved-input/schema and bound-dependency check; no full route replay."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import content_hash
acquired=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
packet=acquired/'native-candidate-results-20260924/enphase_energy/data/config/ordinary_going_concern_assessment.json'
protected=[acquired/'claims.jsonl',ROOT/'evidence/requests_log.csv',ROOT/'outputs/active_publication.json']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
before={str(p):digest(p) for p in protected}
v=json.loads(packet.read_text());assert v['input_record_id']==content_hash(value={k:x for k,x in v.items() if k!='input_record_id'})
assert v['record_type']=='D04_REGISTERED_NATIVE_ASSESSMENT_INPUT' and v['company_id']=='enphase_energy'
assert v['mode']=='LIVE' and v['new_call_authority'] is False
rows=[]
for r in v['native_requests']:
 assert r['semantic_request']['request_id']==r['request_id']
 rows.append({'ordinal':r['ordinal'],'request_id':r['request_id'],'has_saved_assistant_output':bool(r['assistant_output']),'has_plan_acceptance_wire':all(k in r for k in ['plan','acceptance_receipt','intent','terminal','wire']),'assistant_output_bytes':len(r['assistant_output'].encode())})
assert [r['ordinal'] for r in rows]==list(range(173,179))
assert len({r['request_id'] for r in rows})==6
binding=[]
for version in ['issue_28_v13','issue_28_v14']:
 b=json.loads((ROOT/'requirements'/version/'baseline_manifest.json').read_text())
 binding.append({'version':version,'AGENTS_in_execution_files':'AGENTS.md' in b['execution_authority']['files'],'AGENTS_in_rule_files':'AGENTS.md' in b.get('new_rule_files',{})})
assert before=={str(p):digest(p) for p in protected}
body={'record_type':'ISSUE28_54_SAVED_NATIVE_INPUT_SCHEMA_AND_DOC_BINDING_READ','code_commit':'f6a4e4425a6229d0583a4752a1a58b604a21a33e','data_root':str(packet.parents[1]),'packet_sha256':digest(packet),'packet_bytes':packet.stat().st_size,'schema_version':v['schema_version'],'source_id':v['source_id'],'input_record_id':v['input_record_id'],'native_requests':rows,'new_call_authority':False,'production_authorized':False,'data_root_has_git':(packet.parents[1]/'.git').exists(),'binding_doc_checks':binding,'protected_hashes_unchanged':True,'execution_scope':'ACTUAL_JSON_READ_AND_INPUT_HASH_CHECK_ONLY; NOT_ENGINE_REPLAY_OR_COMPANY_PACKAGE_TEST','new_real_calls':[0,0,0],'new_result_or_content_credit':False}
(HERE/'probe.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'schema_version':v['schema_version'],'native_groups':len(rows),'saved_AI_records_are_SEC_originals':False,'AGENTS_direct_bound':False,'new_calls':[0,0,0]}))
