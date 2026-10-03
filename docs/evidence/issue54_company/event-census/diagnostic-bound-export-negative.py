"""Add an undeclared header beside a real Run-bound event census header."""
import json,os,shutil,subprocess,sys,time
from pathlib import Path
work=Path('/workspace/work');state=work/'company-event-ordinary-v2-state'
cp=json.loads((state/'updates/metrics/C01/current.json').read_text());attempt=cp['successful_attempt']
data=state/'updates/metrics/C01/attempts'/attempt/'data'
manifest=json.loads((data.parent/'runs/C01/manifest.json').read_text())
reference=next(r for r in manifest['source_references'] if r['source_url'].endswith('.hdr.sgml'))
admission=json.loads((data/'config/ordinary_source_checkpoint.json').read_text())
relative=next(p for p in admission['files'] if p.startswith('evidence/accession_materials/') and p.endswith('.hdr.sgml') and Path(p).name in reference['source_url'])
copy=work/'company-event-bound-export-negative';shutil.copytree(state,copy)
bound=copy/'updates/metrics/C01/attempts'/attempt/'data'/relative
extra=bound.parent/'undeclared.hdr.sgml';extra.write_bytes(bound.read_bytes())
env={**os.environ,'COMPANY_DENY_READ_ROOTS':str(state)+':/workspace/SEC_metrics:/workspace/work/sec-company-compute:/workspace/work/history-preparation:/workspace/work/history-mixed-restored','PYTHONDONTWRITEBYTECODE':'1'}
start=time.monotonic()
child=subprocess.run([sys.executable,'-B',str(work/'isolated_company_cli.py'),str(work/'company-event-ordinary-runtime-v2'),
 'export-results','--state-root',str(copy),'--trust-root',str(work/'baseline-company-trust'),'--company','marriott_international',
 '--runtime-root',str(work/'company-event-ordinary-runtime-v2'),'--output-root',str(work/'company-event-bound-export-negative-results')],capture_output=True,text=True,env=env)
(work/'company-event-bound-export-negative.stderr.log').write_text(child.stderr)
payload=json.loads(child.stdout)
assert child.returncode==2 and payload['status']=='EXPORTED_PARTIAL',payload
assert [r['metric_id']for r in payload['failed_candidates']]==['C01'],payload
assert len(payload['native_candidates'])==5,payload
print(json.dumps({'status':'PASSED','uid':os.getuid(),'run_id':manifest['run_id'],'source_reference_id':reference['source_reference_id'],
 'request_attempt_id':reference['request_attempt_id'],'run_data_census_locator':relative,'undeclared_added_header':extra.relative_to(copy).as_posix(),
 'failed_candidates':payload['failed_candidates'],'unaffected_exported_metrics':[r['metric_id']for r in payload['native_candidates']],
 'seconds':time.monotonic()-start,'new_business_calls':[0,0,0]},indent=2))
