import contextlib,csv,io,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
base=Path('/private/tmp/issue28-current-revenue-20261011')
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
all_rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('network prohibited')):
 for company,metrics in [('lumen_technologies',['B01','B02','B03']),('macys',['B01','B02'])]:
  state=base/('baseline-'+company); out=base/('baseline-output-'+company)
  args=['run','--company',company,'--source-root',str(source),'--work-dir',str(state),'--output-dir',str(out)]
  for metric in metrics:args.extend(['--metric',metric])
  stream=io.StringIO();started=time.monotonic()
  with contextlib.redirect_stdout(stream):code=main(args) if not state.exists() else 0
  rows=list(csv.DictReader(next(out.rglob('metrics_matrix.csv')).open()))
  record={'company':company,'args':args,'code':code,'seconds':time.monotonic()-started,'rows':rows,'stdout':stream.getvalue()}
  (base/(company+'-baseline.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
  all_rows.extend(rows)
  print(json.dumps({'company':company,'exit':code,'seconds':record['seconds'],'rows':[{k:r[k] for k in ('metric_id','value','unit','period_start','period_end','result_id','status')} for r in rows]},ensure_ascii=False),flush=True)
assert len(all_rows)==5
