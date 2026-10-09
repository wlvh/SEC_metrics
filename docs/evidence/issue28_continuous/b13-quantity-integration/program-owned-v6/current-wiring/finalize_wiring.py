from pathlib import Path
import ast,json,hashlib,tarfile,shutil
from vnext.canonical import canonical_json_bytes,content_hash,sha256_file
from vnext.continuous_call_ledger import recorded_ledger
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
from vnext.continuous_call_wiring import validate_wiring_receipt
base=Path('/tmp/sec_metrics_issue28_continuous/b13-v6-current');evidence=ROOT/'docs/evidence/issue28_continuous/b13-quantity-integration/program-owned-v6/current-wiring';assert not evidence.exists() or not list(evidence.iterdir());evidence.mkdir(exist_ok=True)
log=(base/'offline-wiring.log').read_text();rows=[ast.literal_eval(line) for line in log.splitlines() if line.startswith("{'company_id'")]
assert len(rows)==2 and 'CanonicalError: Binary float is forbidden; use Decimal' in log
assert '\nOK\n' in (base/'count-control-tests.log').read_text()
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
for row in rows:
 for label,status in [('accepted','SUCCEEDED'),('omitted-unit','FAILED_TERMINAL')]:
  ledger=recorded_ledger(root=base/'wiring'/row['company_id']/label)
  with ledger.locked():snapshot=ledger.snapshot()
  assert snapshot['counts']==[1,1,0] and len(snapshot['rows'])==1 and snapshot['rows'][0]['status']==status
  path=ledger.root/'calls/0001';intent=json.loads((path/'intent.json').read_text());assert intent['requirement_closure_hash']==requirement['requirement_closure_hash']
  observed=json.loads((path/'capacity-assessment.json').read_text());assert observed['terminal']['status']==status
  assert observed['native_candidate_evidence_created']==(label=='accepted')
summary={'status':'B13_V6_CURRENT_FACTORY_NATIVE_ACCEPTOR_RECORDED_CONTROLLER_PASS','closure':requirement['requirement_closure_hash'],
 'companies':rows,'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,
 'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,'complete_company_result':False,
 'semantic_qualification':False,'production_authorized':False,'summary_recovery':'All checks and both case rows completed before final summary float serialization failed; this finalizer independently validates both recorded ledgers and outcomes without rerunning executions.'}
(base/'wiring/summary.json').write_bytes(canonical_json_bytes(value=summary))
for name in ['offline-wiring.log','count-control-tests.log','offline_wiring.py','finalize_wiring.py']:
 shutil.copyfile(base/name,evidence/name)
shutil.copyfile(base/'wiring/summary.json',evidence/'summary.json')
archive=evidence/'wiring-material.tar.gz';index={}
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted((base/'wiring').rglob('*')):
  if p.is_file():
   name=p.relative_to(base/'wiring').as_posix();raw=p.read_bytes();index[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};tar.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as tar:
 assert {m.name for m in tar.getmembers()}==set(index)
 for m in tar.getmembers():
  raw=tar.extractfile(m).read();assert index[m.name]=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
(evidence/'wiring-index.json').write_bytes(canonical_json_bytes(value={'archive_sha256':sha256_file(path=archive),'members':index,'all_members_verified':True}))
receipt_path=ROOT/requirement['policy']['offline_wiring_receipt_path'];shutil.copyfile(receipt_path,evidence/'previous-provider-wiring.json')
items=[archive,evidence/'wiring-index.json',evidence/'summary.json',evidence/'offline-wiring.log',evidence/'count-control-tests.log',evidence/'offline_wiring.py',evidence/'finalize_wiring.py']
receipt={'record_type':'CONTINUOUS_OFFLINE_WIRING_RECEIPT','requirement_id':requirement['requirement_id'],
 'execution_authority_hash':content_hash(value=requirement['execution_authority']),'delegation_url':requirement['policy']['delegation_url'],
 'calls':{'provider':0,'paid':0,'sec':0},'network_disabled':True,'legacy_default_forbidden':True,'real_request_factory_to_controller_verified':True,'count_control_tests_passed':True,
 'evidence':{str(p.relative_to(ROOT)):sha256_file(path=p) for p in items},
 'validation_scope':'Current V6 full real-source factory/request identities for Ford11 and Enphase6; representative first-group mock opener/native Candidate/Evidence/controller success and missing-unit failure,27count/role tests. Recorded/synthetic semantics only; no real-company result or production permission. Original summary serializer error preserved and original recorded ledgers independently checked.'}
receipt_path.write_bytes(canonical_json_bytes(value=receipt));validate_wiring_receipt(requirement=requirement)
shutil.copyfile(receipt_path,evidence/'current-provider-wiring.json')
print(json.dumps({'status':'CURRENT_PROVIDER_WIRING_SAVED_AND_VALIDATED','closure':requirement['requirement_closure_hash'],'archive_members':len(index),'archive_bytes':archive.stat().st_size,'real_calls':[0,0,0]}))
