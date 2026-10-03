"""Actual saved sources through native pending records and independent reread."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.c02_model_processing import build_development_assessment, _bytes
from vnext.canonical import sha256_bytes

DATA = Path('/private/tmp/issue28-d01-running-header-processing-20261003/26223fc8410d0090b8cc9c8a5ad6e29061500002cd3d6764ed558c4fc462a6ac')
STATE = Path('/private/tmp/issue28-c02-native-pending-20261003')
PILOT = ROOT / 'docs/evidence/issue28_continuous/c02-model-input-pilot-20261003'
PYTHON = '/private/tmp/issue28-tokenizers-venv/bin/python'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protected = [ROOT / 'evidence/requests_log.csv',
    Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')]
protected = [p for p in protected if p.exists()]
before = {str(p): digest(p) for p in protected}
samples = [('enphase_energy', '/private/tmp/issue28-c02-blind-source-pilot2-20261003',
            PILOT / 'independent-input-76da71e/response-v2.log'),
           ('paramount_skydance_paramount_global', '/private/tmp/issue28-c02-paramount-blind-fixed-task-20261003',
            PILOT / 'independent-paramount-input-7733176/response.log')]
result = {'tested_head_plus_worktree': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'code_root': str(ROOT), 'data_root': str(DATA), 'state_root': str(STATE),
          'samples': [], 'new_business_calls': [0, 0, 0], 'native_result_or_run_created': False}
STATE.mkdir(exist_ok=True)

child = '''import json,sys
from pathlib import Path
sys.dont_write_bytecode=True
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:raise RuntimeError('NO_NETWORK_OR_PROCESS')
sys.addaudithook(guard)
from vnext.c02_model_processing import read_development_assessment, ROOT
from vnext.review import create_system_review_decision, ReviewError
from vnext.requirements import load_requirement_snapshot
out=read_development_assessment(directory=Path(sys.argv[1]),data_root=Path(sys.argv[2]),company_id=sys.argv[3],expected_candidate_hash=sys.argv[4],expected_review_unit_hash=sys.argv[5])
unit=out['records'][-1]
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v13')
try:create_system_review_decision(review_unit=unit,required_claims=unit['required_claims'],decided_at_utc='2026-10-03T00:00:00Z',requirement=requirement)
except ReviewError as e:refused=str(e)
else:raise AssertionError('Mechanical mapper permitted SYSTEM approval')
print(json.dumps({'status':'PENDING_NATIVE_OBJECTS_REPLAY_EXACT','review_status':unit['status'],'system_approval_refused':refused,'no_native_result_or_provider_attempt':True}))
'''
try:
    for company, input_dir, response_path in samples:
        input_dir = Path(input_dir)
        meta = json.loads((input_dir / 'metadata.json').read_text())
        request = (input_dir / 'request-body.json').read_bytes()
        response = response_path.read_bytes()
        folder = STATE / company
        if folder.exists():
            records = [json.loads(line) for line in (folder / 'records.jsonl').read_text().splitlines()]
            out = {'records': records, 'processing': json.loads((folder / 'processing/c02/metadata.json').read_text())}
            assert (folder / 'request-body.bin').read_bytes() == request
            assert (folder / 'response.bin').read_bytes() == response
            build_seconds = None  # Preserve passed construction; repair cold harness only.
        else:
            start = time.monotonic()
            out = build_development_assessment(data_root=DATA, company_id=company,
                request_body=request, response_body=response,
                source_reference_id=meta['source_reference']['source_reference_id'],
                expected_request_sha256=sha256_bytes(content=request),
                expected_response_sha256=sha256_bytes(content=response))
            (folder / 'processing/c02').mkdir(parents=True)
            (folder / 'request-body.bin').write_bytes(request)
            (folder / 'response.bin').write_bytes(response)
            (folder / 'records.jsonl').write_bytes(b'\n'.join(_bytes(x) for x in out['records']) + b'\n')
            (folder / 'processing/c02/metadata.json').write_bytes(_bytes(out['processing']))
            (folder / 'review-context.json').write_bytes(out['review_context_bytes'])
            (folder / 'review.md').write_bytes(out['rendered_review_bytes'])
            build_seconds = round(time.monotonic() - start, 3)
        candidate, unit = out['records'][1], out['records'][-1]
        args = [PYTHON, '-B', '-c', child, str(folder), str(DATA), company,
                candidate['candidate_hash'], unit['review_unit_hash']]
        start = time.monotonic()
        with (HERE / (company + '-cold.log')).open('w') as log:
            done = subprocess.run(args, env={**os.environ, 'PYTHONPATH': str(ROOT / 'scripts')},
                cwd=STATE, stdout=log, stderr=subprocess.STDOUT)
        assert done.returncode == 0, 'READ_COLD_LOG'
        result['samples'].append({'company_id': company, 'folder': str(folder),
            'candidate_hash': candidate['candidate_hash'], 'review_unit_hash': unit['review_unit_hash'],
            'build_seconds': build_seconds, 'cold_seconds': round(time.monotonic() - start, 3),
            'source_admission': out['processing']['ordinary_source_admission'],
            'pending': unit['status'], 'system_approval_eligible': unit['system_approval_eligible'],
            'fact_count': len(out['processing']['model_facts_and_unresolved']['facts']),
            'unresolved': len(out['processing']['model_facts_and_unresolved']['unresolved']),
            'source_and_response_bytes_preserved': True})
        print(company, build_seconds, result['samples'][-1]['cold_seconds'], flush=True)
    result['status'] = 'PASS_NATIVE_PENDING_MAPPING_AND_INDEPENDENT_REPLAY'
finally:
    result['protected_original_bytes_unchanged'] = all(digest(Path(p)) == h for p, h in before.items())
    (HERE / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'done.json').write_text(json.dumps({'status': result.get('status', 'FAILED'), 'completed': True}) + '\n')
