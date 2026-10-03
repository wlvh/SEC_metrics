"""Run the current C02 successor through the normal CLI on saved originals."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
WORK=Path('/private/tmp/issue28-c02-member-current-20261003')
ACQUIRED=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0]=[str(ROOT),str(ROOT/'scripts'),str(ROOT/'tools')]
spec=importlib.util.spec_from_file_location('legacy_probe',ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocked(*args,**kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


old_record=next(Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929').glob(
    'state/jpmorgan_chase/metrics/C02/attempts/*/runs/C02/records.jsonl'))
protected={'claims':ACQUIRED/'claims.jsonl','source_log':ROOT/'evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json',
    'old_private_records':old_record,'old_private_manifest':old_record.parent/'manifest.json',
    'old_390_index':ROOT/'docs/evidence/issue28_continuous/review-5207290213/current-390.json'}
prior_v3=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-c02-auditor-successor-20261002/run.json').read_text())
protected['prior_v3_records']=Path(prior_v3['run_dir'])/'records.jsonl'
protected['prior_v3_manifest']=Path(prior_v3['run_dir'])/'manifest.json'
before={key:digest(path) for key,path in protected.items()}
assert not WORK.exists(),'C02_PRIVATE_ROOT_ALREADY_EXISTS'
capture=io.StringIO()
started=time.monotonic()
with (patch.object(socket.socket,'connect',side_effect=blocked),
      patch.object(socket,'getaddrinfo',side_effect=blocked),
      patch('sec_http.urlopen',side_effect=blocked),
      probe.legacy_disabled() as disabled):
    import vnext_normal_update
    with contextlib.redirect_stdout(capture):
        rc=vnext_normal_update.main(['--process','--company','jpmorgan_chase',
            '--metric','C02','--data-root',str(ROOT),'--state-root',str(WORK/'state')])
elapsed=time.monotonic()-started
(HERE/'cli-report.json').write_text(capture.getvalue())
report=json.loads(capture.getvalue())
company,=report['companies'];metric,=company['metrics']
assert rc==0 and metric['status']=='CANDIDATE_READY',metric
state=WORK/'state/jpmorgan_chase/metrics/C02-composition-member-v4'
attempt=metric['attempt_id'];run=state/'attempts'/attempt/'runs/C02'
records=[json.loads(line) for line in (run/'records.jsonl').read_bytes().splitlines()]
candidate=next(row for row in records if row['record_type']=='DETERMINISTIC_TEXT_CANDIDATE')
evidence=next(row for row in records if row['record_type']=='EVIDENCE_CHECK')
result=next(row for row in records if row['record_type']=='METRIC_RESULT' and row['metric_id']=='C02')
manifest=json.loads((run/'manifest.json').read_text())
indices={i for check in evidence['checks'] for i in check.get('selected_source_blocks',[])}
assert 3367 not in indices and 3436 not in indices and 3409 in indices
assert 'continued retention of PwC as the Firm’s independent external auditor' not in result['value']
assert 'The members of the Audit Committee are not professionally engaged' not in result['value']
assert evidence['status']=='PASS' and result['publication']=='PUBLISHED'
assert result['result_id']==metric['last_verified_candidate']['results']['C02']['result_id']
binding=json.loads((HERE/'binding-after.json').read_text())
assert manifest['requirement_closure_hash']==binding['parent_closure']
after={key:digest(path) for key,path in protected.items()}
assert before==after and report['calls']=={'provider':0,'paid':0,'sec':0}
old=json.loads((ROOT/'docs/evidence/issue28_continuous/collab-c02-jpm-auditor-20261002/audit.json').read_text())
assert result['result_id'] not in (old['old_private_result_id'],old['old_archived_390_result_id'])
summary={'record_type':'ISSUE28_C02_MEMBER_SUCCESSOR_PRIVATE_NORMAL_UPDATE',
    'tested_tree':'UNCOMMITTED_WORKTREE_WITH_BOUND_RUNTIME_BYTES',
    'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'code_root':str(ROOT),'source_root':str(ROOT),'state_root':str(state),
    'installed_data_root':str(state/'attempts'/attempt/'data'),
    'run_dir':str(run),'attempt_id':attempt,'run_id':manifest['run_id'],
    'requirement_closure_hash':binding['parent_closure'],
    'status':metric['status'],'result_id':result['result_id'],
    'grouped_excerpt_count':len(candidate['selected']),
    'selected_original_block_count':len(indices),
    'repaired_block_3367_absent':True,'repaired_block_3436_absent':True,'member_positive_3409_preserved':True,
    'native_evidence_status':evidence['status'],'value_chars':len(result['value']),
    'elapsed_seconds':round(elapsed,3),'legacy_exports_disabled':disabled,
    'protected_old_runs_index_ledger_active_unchanged':before==after,
    'protected_sha256':after,'calls':report['calls'],'new_real_calls':[0,0,0],
    'whole_content_accepted':False,'current_390_credit':False,'production_authorized':False}
(HERE/'run.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:summary[key] for key in ('status','result_id',
    'grouped_excerpt_count','selected_original_block_count','elapsed_seconds','calls')}),flush=True)
