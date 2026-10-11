"""Real ordinary company entry; source/config reuse and separate-process reader."""
import contextlib,csv,io,json,socket,subprocess,sys,tempfile,time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext.canonical import sha256_file
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
root=Path.cwd();e=root/'docs/evidence/issue28_revenue_note_reference_20261011'
work=Path(tempfile.mkdtemp(prefix='issue28-note-current-pfizer-'));state=work/'state';output=work/'output'
args=['run','--company','pfizer','--source-root',str(source),'--work-dir',str(state),'--output-dir',str(output),'--metric','B01','--metric','B02']
protected={str(p):sha256_file(path=p) for p in (source/'config/company_registry.csv',source/'evidence/requests_log.csv',source/'evidence/requests_log_manifest.json')}
def invoke(forbid=False):
 stream=io.StringIO();start=time.perf_counter()
 with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')),contextlib.redirect_stdout(stream):
  if forbid:
   with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No calculation on unchanged inputs')):code=main(args)
  else:code=main(args)
 return code,time.perf_counter()-start,stream.getvalue()
first,seconds,first_output=invoke();assert first==0,first_output
files={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*') if p.is_file() and '/results/' in str(p)}
repeat,repeat_seconds,repeat_output=invoke(True);assert repeat==0,repeat_output
assert files=={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*') if p.is_file() and '/results/' in str(p)}
reader=work/'reader';started=time.perf_counter();r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','pfizer','--state-root',str(state),'--output-root',str(reader)],capture_output=True,text=True);read_seconds=time.perf_counter()-started;assert r.returncode==0,r.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));by={r['metric_id']:r for r in rows};assert set(by)=={'B01','B02'},rows
assert by['B01']['value']=='62579000000' and by['B01']['unit']=='USD',rows
assert Decimal(by['B02']['value'])==((Decimal('62579')-Decimal('63627'))/Decimal('63627')) and by['B02']['unit']=='ratio',rows
assert all((r['period_start'],r['period_end'])==('2025-01-01','2025-12-31') for r in rows),rows
refs=list(csv.DictReader((reader/'metric_evidence.csv').open()));assert refs and all(r['source_url'].startswith('https://') for r in refs)
assert protected=={p:sha256_file(path=Path(p)) for p in protected}
record={'actual_program_root':str(root),'source_root':str(source),'state_root':str(state),'reader_root':str(reader),'cli':args,'tested_local_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'runtime_file_sha256':{p:sha256_file(path=root/p) for p in ('scripts/vnext/selected_revenue_scope_v1.py','scripts/vnext/selected_reported_revenue_v2.py')},'rows':rows,'source_evidence':refs,'first_seconds':seconds,'forbidden_repeat_seconds':repeat_seconds,'independent_read_seconds':read_seconds,'protected_result_files':len(files),'source_bookkeeping_hashes':protected,'calls':{'provider':0,'paid':0,'sec':0}}
(e/'current-pfizer.json').write_text(json.dumps(record,indent=2)+'\n')
print('PASS_PFIZER_CURRENT_B01_B02_FORMAL_ENTRY_UNCHANGED_REUSE_INDEPENDENT_CSV',[(r['metric_id'],r['value'],r['unit']) for r in rows],seconds,repeat_seconds,read_seconds,flush=True)
