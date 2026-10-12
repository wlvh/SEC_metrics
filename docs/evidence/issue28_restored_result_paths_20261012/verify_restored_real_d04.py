import contextlib,csv,fcntl,hashlib,io,json,shutil,socket,tempfile
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
original=Path('/private/tmp/issue28-d04-debt-version-y5y0j55n/state').resolve()
backup=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-backups/20261012-marriott-ordinary-d04')
backup.parent.mkdir(parents=True,exist_ok=True)
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before=hashes(original)
if not backup.exists():
 with (original/'company.lock').open('rb') as lock:
  fcntl.flock(lock,fcntl.LOCK_SH);stage=Path(tempfile.mkdtemp(prefix='.marriott-d04-backup-',dir=backup.parent));shutil.copytree(original,stage/'state');(stage/'inventory.json').write_text(json.dumps(before,indent=2)+'\n');stage.rename(backup)
assert before==hashes(backup/'state')
restore=Path(tempfile.mkdtemp(prefix='issue28-d04-restore-'));shutil.copytree(backup/'state',restore/'state');assert before==hashes(restore/'state')
old_open=Path.open;old_is_file=Path.is_file
def old(p):return p.resolve().is_relative_to(original)
def blocked_open(p,*a,**k):
 if old(p):raise FileNotFoundError('Original completed state is unavailable for restore verification')
 return old_open(p,*a,**k)
def blocked_is_file(p):return False if old(p) else old_is_file(p)
stream=io.StringIO()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),patch.object(Path,'open',blocked_open),patch.object(Path,'is_file',blocked_is_file),contextlib.redirect_stdout(stream):
 code=main(['results','--company','marriott_international','--state-root',str(restore/'state'),'--output-root',str(restore/'reader')])
output=json.loads(stream.getvalue());rows=list(csv.DictReader((restore/'reader'/'metrics_matrix.csv').open()))
report={'backup':str(backup),'restore':str(restore),'original_state_unavailable':True,'file_count':len(before),'bytes':sum(p.stat().st_size for p in (backup/'state').rglob('*') if p.is_file()),'reader_exit':code,'rows':[{k:r[k] for k in ('metric_id','value','status','result_id','period_start','period_end')} for r in rows],'original_files_unchanged':before==hashes(original),'calls':[0,0,0]}
Path('/private/tmp/issue28-d04-small-restore-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report));assert code==0 and len(rows)==1 and rows[0]['result_id']=='sha256:e523b7a9b36b787596d7de5100746a3c23b44ca336b4791d64c7df9ef7555371',report
