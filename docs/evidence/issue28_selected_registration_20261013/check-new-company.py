"""Fresh default producer, save, forbidden repeat and independent company read."""
import csv,hashlib,io,json,socket,subprocess,sys,time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from tools.vnext_company import main
from vnext import ordinary_saved_result as saved
BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/selected-registration-new-company-20261013')
STATE=BASE/'state';SOURCE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
assert not STATE.exists();BASE.mkdir(exist_ok=True)
argv=['run','--company','marriott_international','--source-root',str(SOURCE),'--metric','B01','--work-dir',str(STATE),'--output-dir',str(BASE/'runs')]
phases=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 for name,forbid in [('first',False),('repeat',True)]:
  out=io.StringIO();started=time.monotonic()
  if forbid:
   with patch.object(saved,'_ordinary_case',side_effect=AssertionError('No repeated calculation')),redirect_stdout(out):rc=main(argv)
  else:
   with redirect_stdout(out):rc=main(argv)
  report=json.loads(out.getvalue());metric=report['metrics'][0]
  assert rc in (0,2) and metric['status']==('NO_SOURCE_CONTENT_CHANGE' if forbid else 'CANDIDATE_READY'),report
  phases.append({'name':name,'seconds':time.monotonic()-started,'exit_code':rc,'metric':metric})
  if not forbid:before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(metric['result_root']).rglob('*') if p.is_file()}
  else:assert before=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
started=time.monotonic();reader=BASE/'reader'
r=subprocess.run([sys.executable,str(ROOT/'tools/vnext_company.py'),'results','--company','marriott_international','--state-root',str(STATE),'--output-root',str(reader)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
row=list(csv.DictReader((reader/'metrics_matrix.csv').open()))[0]
assert row['value']=='26186000000' and row['unit']=='USD' and row['period_start']=='2025-01-01' and row['period_end']=='2025-12-31',row
assert before=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
receipt={'code_root':str(ROOT),'state_root':str(STATE),'source_root':str(SOURCE),'phases':phases,
 'row':row,'independent_read_seconds':time.monotonic()-started,'result_files_preserved':len(before),'new_calls':[0,0,0]}
(Path(__file__).parent/'new-company.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('phases',[(p['name'],p['seconds']) for p in phases],'read',receipt['independent_read_seconds'],'value',row['value'],flush=True)
