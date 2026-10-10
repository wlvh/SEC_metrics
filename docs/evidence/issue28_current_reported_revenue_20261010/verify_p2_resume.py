"""One affected real current company after source-date/header repair, old state retained."""
import contextlib,csv,io,json,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
from vnext.canonical import sha256_file
from tools.vnext_company import main
program=Path.cwd();evidence=program/'docs/evidence/issue28_current_reported_revenue_20261010'
old=json.loads((evidence/'final-actual-company.json').read_text())['outcomes'][0]
state=Path(old['state_root']);source=Path(old['source_root']);output=state.parent/'p2-output'
protected=old['protected_result_files'];assert all(sha256_file(path=state/p)==h for p,h in protected.items())
prior_dirs=sorted(str(p.relative_to(state)) for p in state.rglob('manifest.json'))
args=['run','--company','macys','--source-root',str(source),'--work-dir',str(state),
      '--output-dir',str(output),'--metric','B01'];stream=io.StringIO();t=time.monotonic()
with contextlib.redirect_stdout(stream):first=main(args)
first_time=time.monotonic()-t;after_dirs=sorted(str(p.relative_to(state)) for p in state.rglob('manifest.json'))
assert len(after_dirs)==len(prior_dirs)+1,(prior_dirs,after_dirs)
assert all(sha256_file(path=state/p)==h for p,h in protected.items())
new_protected={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*') if p.is_file() and '/results/' in str(p)}
t=time.monotonic()
with patch('vnext.ordinary_current_update.create_saved_result',side_effect=AssertionError('No repeated P2 calculation')),contextlib.redirect_stdout(stream):repeat=main(args)
repeat_time=time.monotonic()-t
assert new_protected=={str(p.relative_to(state)):sha256_file(path=p) for p in state.rglob('*') if p.is_file() and '/results/' in str(p)}
reader=state.parent/'p2-reader';t=time.monotonic()
r=subprocess.run([sys.executable,'tools/vnext_company.py','results','--company','macys','--state-root',str(state),
                  '--output-root',str(reader)],capture_output=True,text=True);read_time=time.monotonic()-t
assert first==repeat==r.returncode==0,r.stderr
rows=list(csv.DictReader((reader/'metrics_matrix.csv').open()));assert rows[0]['value']=='22621000000'
assert rows[0]['result_id']==old['rows'][0]['result_id']
record={'program_root':str(program),'base_before_repair':'7e6f6a240e63000ad69c1a9354f86980eced4228',
        'tested_tree':'UNCOMMITTED_P2_REPAIR','actual_source_root':str(source),'state_root':str(state),
        'reader_root':str(reader),'first_seconds':first_time,'repeat_seconds':repeat_time,'reader_seconds':read_time,
        'old_files_unchanged':protected,'after_repeat_protected_files':new_protected,
        'one_changed_program_version':len(after_dirs)-len(prior_dirs),'value':rows[0]['value'],
        'unit':rows[0]['unit'],'period':[rows[0]['period_start'],rows[0]['period_end']],
        'result_id':rows[0]['result_id'],'csv_sha256':sha256_file(path=reader/'metrics_matrix.csv'),
        'tested_code_sha256':{p:sha256_file(path=program/p) for p in ('scripts/vnext/selected_revenue_scope_v1.py',
            'scripts/vnext/selected_reported_revenue_v2.py')},'CLI_output':stream.getvalue(),'calls':[0,0,0]}
(evidence/'p2-actual-resume.json').write_text(json.dumps(record,indent=2)+'\n')
print(record['value'],record['result_id'],first_time,repeat_time,read_time,
      'old files',len(protected),'protected after',len(new_protected),'new version',record['one_changed_program_version'])
