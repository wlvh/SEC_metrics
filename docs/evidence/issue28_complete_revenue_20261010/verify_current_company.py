from pathlib import Path
import contextlib,csv,io,json,shutil,subprocess,sys,tempfile,time
from unittest.mock import patch
from vnext.ordinary_saved_result import _ordinary_case
from vnext.canonical import sha256_file
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tools.vnext_company import main
program=Path.cwd();existing=Path('/Users/lyuhongwang/Developer/SEC_metrics')
base=Path(tempfile.mkdtemp(prefix='issue28-revenue-company-'));source=base/'source';source.mkdir()
with original_sources_only():case=_ordinary_case(existing,'pfizer','B01')
paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
for p in case['source_proofs']:paths.update((p['request_repo_relative_path'],p['request_headers_repo_relative_path']))
for p in paths:
 target=source/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(existing/p,target)
state=base/'state';output=base/'output'
args=['run','--company','pfizer','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(output),'--metric','B01']
import socket
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 stream=io.StringIO();started=time.monotonic()
 with contextlib.redirect_stdout(stream):first_exit=main(args)
 first=time.monotonic()-started
 files={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
 started=time.monotonic()
 with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No calculation on unchanged input')),contextlib.redirect_stdout(stream):repeat_exit=main(args)
 repeat=time.monotonic()-started
 assert files=={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
reader=base/'reader';started=time.monotonic()
r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','pfizer','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True)
read=time.monotonic()-started;assert r.returncode==0,r.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert len(rows)==1 and rows[0]['value']=='62579000000',rows
proofs=list(csv.DictReader((reader/'metric_evidence.csv').open()));assert proofs and all(row['source_url'].startswith('https://') for row in proofs)
out={'program_root':str(program),'git_base':'f6ef7886d6630f7675c25cd42e306c373ab05769','uncommitted_changes':True,'source_root':str(source),'state_root':str(state),'independent_read_root':str(reader),'source_files':sorted(paths),'source_hashes':{p:sha256_file(path=source/p) for p in sorted(paths)},'cli_args':args,'first_seconds':first,'first_exit':first_exit,'repeat_seconds':repeat,'repeat_exit':repeat_exit,'independent_read_seconds':read,'reader_returncode':r.returncode,'rows':rows,'result_hashes':files,'result_hashes_unchanged_on_forbidden_repeat':True,'cli_output':stream.getvalue(),'reader_output':r.stdout,'calls':{'provider':0,'paid':0,'sec':0}}
Path('docs/evidence/issue28_complete_revenue_20261010/current-company.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('paths',base);print('first/repeat/read',first,repeat,read);print('value/unit/period',rows[0]['value'],rows[0]['unit'],rows[0]['period_start'],rows[0]['period_end']);print('exit',first_exit,repeat_exit);print('result files stable',len(files))
