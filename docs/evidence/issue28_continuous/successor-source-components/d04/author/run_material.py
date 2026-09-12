"""Re-run D04 read-only source preparation and fresh-process byte replay."""
import argparse,csv,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo.resolve();out=a.output.resolve()
if out.exists() or out==repo or repo in out.parents: raise SystemExit('A fresh external output directory is required')
out.mkdir(parents=True)
sys.path.insert(0,str(repo/'scripts'))
def no_network(event,args):
 if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'): raise RuntimeError('NO_NETWORK_D04_MATERIAL')
sys.addaudithook(no_network)
from vnext.going_concern_source import prepare_ordinary_going_concern_source
from vnext.canonical import sha256_file
protected=['evidence/requests_log.csv','evidence/requests_log_manifest.json','artifacts/vnext/active.json']
protected_before={p:sha256_file(path=repo/p) for p in protected if (repo/p).is_file()}
code_paths=['scripts/vnext/going_concern_source.py','tests/vnext/test_going_concern_source.py','scripts/vnext/text_business_candidates.py','scripts/vnext/text_coverage.py','scripts/vnext/normal_annual_input.py','scripts/vnext/normal_source_authority.py']
code={p:sha256_file(path=repo/p) for p in code_paths}
(out/'code-hashes.json').write_text(json.dumps(code,indent=2))
child='''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]+"/scripts")
def deny(event,args):
 if event in ("socket.connect","socket.connect_ex","socket.getaddrinfo"): raise RuntimeError("NO_NETWORK_D04_COLD_READ")
sys.addaudithook(deny)
from vnext.going_concern_source import verify_ordinary_going_concern_source
p=json.loads(Path(sys.argv[2]).read_text())
r=verify_ordinary_going_concern_source(packet=p,repo_root=Path(sys.argv[1]),company_id=sys.argv[3])
print(json.dumps({"status":"SOURCE_PACKET_REBUILT_FROM_ORIGINAL_BYTES","packet_id":r["packet_id"],"documents":len(r["components"]),"not_disclosed_confirmed":r["not_disclosed_confirmed"],"native_result_created":r["native_result_created"],"calls":r["calls"]}))
'''
(out/'cold_read.py').write_text(child)
rows=[]
for company in csv.DictReader((repo/'config/company_registry.csv').open()):
 c=company['company_id'];start=time.monotonic(); row={'company_id':c}
 try:
  packet=prepare_ordinary_going_concern_source(repo_root=repo,company_id=c)
  file=out/(c+'.json');file.write_text(json.dumps(packet,ensure_ascii=False,separators=(',',':'))+'\n')
  command=[sys.executable,str(out/'cold_read.py'),str(repo),str(file),c]
  result=subprocess.run(command,cwd=out,text=True,capture_output=True,timeout=120)
  (out/(c+'-cold.log')).write_text(result.stdout+result.stderr)
  row.update(status='PASS' if result.returncode==0 else 'COLD_READ_FAILED',packet_id=packet['packet_id'],saved_packet_sha256=sha256_file(path=file),cold_command=command,cold_exit_code=result.returncode,documents=[])
  for item in packet['components']:
   row['documents'].append(dict(accession=item['source_filing']['accessionNumber'],form=item['source_filing']['form'],reportDate=item['source_filing']['reportDate'],filingDate=item['source_filing']['filingDate'],raw_asset_id=item['raw_blob']['raw_asset_id'],source_path=item['raw_blob']['storage_uri'],native_facts=len(item['native_concept_candidates']),language_candidates=len(item['language_candidates']),audit_reports=[{'kind':r['report_kind'],'identity_status':r['identity_status'],'subject':r.get('source_subject'),'date':r.get('source_balance_sheet_date'),'opening_start_byte':r['opening']['raw_start_byte'] if r['opening'] else None} for r in item['auditor_openings']],input_coverage=item['input_coverage'],input_units=len(item['semantic_source_units']),oversized_units=sum(u['oversized_single_block'] for u in item['semantic_source_units']),document_state=item['document']['source_state'],document_reasons=item['document']['source_reasons']))
 except Exception as e:
  row.update(status='FAILED',error_type=type(e).__name__,reason=str(e));(out/(c+'-first-failure.log')).write_text(traceback.format_exc())
 row['elapsed_seconds']=round(time.monotonic()-start,3);rows.append(row);(out/'index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(c,row['status'],row['elapsed_seconds'],flush=True)
protected_after={p:sha256_file(path=repo/p) for p in protected_before}
(out/'execution.json').write_text(json.dumps(dict(command=sys.argv,python=sys.version,protected_before=protected_before,protected_after=protected_after,protected_unchanged=protected_before==protected_after,code_before=code,code_after={p:sha256_file(path=repo/p) for p in code_paths},network_audit_guard=True,calls={'provider':0,'paid':0,'sec':0},native_run_created=False,freeze_called=False),indent=2))
raise SystemExit(0 if all(r['status']=='PASS' for r in rows) and protected_before==protected_after else 1)
