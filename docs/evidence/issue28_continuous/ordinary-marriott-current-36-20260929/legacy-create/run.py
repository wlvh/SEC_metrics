"""Fresh-create Marriott's 36 ordinary Runs while old producers are retired."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-36-no-legacy-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = Path('/private/tmp/issue28-marriott-current-36-20260929/sources/'
    '2758b48cba3a4b2a5deac013872e3e0243b7f55549a75f0ccc4e3f487a44b8fb')
PARENT = HERE.parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


prior = json.loads((PARENT/'result.json').read_text())
assert prior['status'] == 'UPDATES_READY' and len(prior['metric_rows']) == 36
originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
assert not WORK.exists()
with probe.legacy_disabled() as disabled:
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.ordinary_b03_scope_update import run_company
    from vnext.requirements import load_requirement_snapshot

    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs', processing_root=SOURCE,
        requirement=requirement)
    assert verified['snapshot_id'] == prior['source_snapshot_id']
    outcome = run_company(state_root=WORK/'state', source_root=SOURCE,
        source_identity_root=ACQUIRED/'source-inputs',
        company_id='marriott_international',
        metric_ids=prior['metric_ids'])

rows = []
old_ids = {row['metric_id']: row['result_id'] for row in prior['metric_rows']}
for item in outcome['metrics']:
    result = (item.get('last_verified_candidate') or {}).get('results', {}).get(
        item['metric_id'])
    rows.append({'metric_id': item['metric_id'], 'status': item['status'],
        'result_id': None if result is None else result['result_id'],
        'same_result_as_prior_private_run': result is not None and
            result['result_id'] == old_ids[item['metric_id']]})
    print(item['metric_id'], item['status'], flush=True)
after = {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_MARRIOTT_36_FRESH_CREATE_WITH_OLD_PRODUCERS_DISABLED',
    'source_snapshot_id': verified['snapshot_id'],
    'company_id': 'marriott_international',
    'status': outcome['status'], 'rows': rows,
    'candidate_ready_count': sum(row['status'] == 'CANDIDATE_READY'
                                  for row in rows),
    'same_result_id_count': sum(row['same_result_as_prior_private_run']
                                for row in rows),
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': before == after,
    'calls': [outcome['calls'][key] for key in ('provider', 'paid', 'sec')],
    'new_complete_business_coordinates': 0,
    'all390_acceptance': False,
    'formal_old_entrypoints_retired': False}
(HERE/'result.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status': body['status'],
    'candidate_ready_count': body['candidate_ready_count'],
    'same_result_id_count': body['same_result_id_count'],
    'original_files_unchanged': before == after,
    'calls': body['calls']}, sort_keys=True), flush=True)
assert body['status'] == 'UPDATES_READY'
assert body['candidate_ready_count'] == body['same_result_id_count'] == 36
assert body['original_claims_source_and_active_unchanged']
assert body['calls'] == [0, 0, 0]
