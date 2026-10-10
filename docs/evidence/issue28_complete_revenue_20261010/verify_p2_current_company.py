import contextlib,csv,io,json,time,socket,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from vnext.canonical import sha256_file
from tools.vnext_company import main
old=json.loads(Path('docs/evidence/issue28_complete_revenue_20261010/current-company.json').read_text());state=Path(old['state_root']);source=Path(old['source_root']);output=state.parent/'repaired-output';reader=state.parent/'repaired-reader'
old_files={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
args=['run','--company','pfizer','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(output),'--metric','B01']
s=io.StringIO()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 start=time.monotonic()
 with contextlib.redirect_stdout(s):rc=main(args)
 first=time.monotonic()-start
 before={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
 assert all(before[p]==h for p,h in old_files.items())
 start=time.monotonic()
 with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No repeat calculation')),contextlib.redirect_stdout(s):repeat_rc=main(args)
 repeat=time.monotonic()-start
 after={str(p.relative_to(state)):sha256_file(path=p) for p in (state/'updates').rglob('*') if p.is_file() and '/results/' in str(p)}
 assert before==after
start=time.monotonic();r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','pfizer','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True);read=time.monotonic()-start;assert r.returncode==0,r.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert rows[0]['value']=='62579000000',rows
result={'code_base':'83eaa4da5d18c7accc0c093b1ef4db5f5158da16','product_changes_uncommitted':True,'source_root':str(source),'state_root':str(state),'reader_root':str(reader),'first_after_processing_change_seconds':first,'forbidden_repeat_seconds':repeat,'independent_process_read_seconds':read,'run_exit':rc,'repeat_exit':repeat_rc,'reader_exit':r.returncode,'old_result_files_preserved':old_files,'result_files_after_config_reprocessing':after,'repeated_files_identical':True,'rows':rows,'cli_output':s.getvalue(),'calls':[0,0,0]}
Path('docs/evidence/issue28_complete_revenue_20261010/p2-current-company.json').write_text(json.dumps(result,indent=2)+'\n');print(first,repeat,read,rc,repeat_rc,r.returncode,len(old_files),len(after),rows[0]['value'])
