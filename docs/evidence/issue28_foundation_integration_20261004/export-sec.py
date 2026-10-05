import os,json,time,subprocess
from pathlib import Path
HERE=Path(__file__).parent;BASE=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-foundation-handoff-20261004');OLD=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260922/marriott_international/data');CODE=Path('/private/tmp/issue28-foundation-pr55-consumer-83db2c02')
s=time.monotonic();p=subprocess.run(['/private/tmp/issue28-tokenizers-venv/bin/python',str(CODE/'tools/vnext_company.py'),'export','--source-root',str(OLD),'--output-root',str(BASE/'sec-sources'),'--trust-root',str(BASE/'source-trust'),'--company','marriott_international','--metric','D04'],cwd=CODE,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
(HERE/'d04-sec-stdout.log').write_text(p.stdout);(HERE/'d04-sec-stderr.log').write_text(p.stderr);record={'returncode':p.returncode,'seconds':round(time.monotonic()-s,3),'source_root':str(OLD),'new_calls':[0,0,0]};
if not p.returncode:record['result']=json.loads(p.stdout)
(HERE/'d04-sec-summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(p.returncode)
