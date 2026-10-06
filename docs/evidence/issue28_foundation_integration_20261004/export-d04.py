"""Use the fixed #54 exporter with original LIVE input, no new execution."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).parent
OLD=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260922/marriott_international')
EXPORT=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-foundation-handoff-20261004')
CONSUMER=Path('/private/tmp/issue28-foundation-pr55-consumer-83db2c02')
EXPORT.mkdir(parents=True,exist_ok=False)
start=time.monotonic()
args=['/private/tmp/issue28-tokenizers-venv/bin/python',str(CONSUMER/'tools/vnext_company.py'),'export-processing','--installed-root',str(OLD/'data'),'--output-root',str(EXPORT/'processing'),'--runtime-output-root',str(EXPORT/'processing-runtime'),'--trust-root',str(EXPORT/'processing-trust'),'--company','marriott_international']
p=subprocess.run(args,cwd=CONSUMER,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True)
(HERE/'d04-export-stdout.log').write_text(p.stdout);(HERE/'d04-export-stderr.log').write_text(p.stderr)
record={'pr55_sha':'83db2c0284d76cfe6a1fafc8703743add05738f8','installed_original':str(OLD/'data'),'output_root':str(EXPORT),'returncode':p.returncode,'seconds':round(time.monotonic()-start,3),'args':args,'new_calls':[0,0,0],'old_data_changed':False}
if p.returncode==0:record['result']=json.loads(p.stdout)
(HERE/'d04-export-summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(p.returncode)
