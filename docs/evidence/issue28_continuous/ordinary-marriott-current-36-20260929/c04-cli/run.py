"""Exercise the ordinary CLI's C04 successor on saved #28 source, offline."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-marriott-c04-cli-20260929')
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = Path('/private/tmp/issue28-marriott-current-36-20260929/sources/'
    '2758b48cba3a4b2a5deac013872e3e0243b7f55549a75f0ccc4e3f487a44b8fb')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts'), str(ROOT/'tools')]

spec = importlib.util.spec_from_file_location('legacy_probe', ROOT/
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
phase = sys.argv[1]
assert phase in {'create', 'read'}
with probe.legacy_disabled() as disabled:
    from vnext.continuous_call_policy import REQUIREMENT_ID
    from vnext.ordinary_processing_source import verify_processing_source
    from vnext.requirements import load_requirement_snapshot

    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    verified = verify_processing_source(
        acquisition_root=ACQUIRED/'source-inputs', processing_root=SOURCE,
        requirement=requirement)
    assert verified['snapshot_id'] == 'sha256:' + SOURCE.name
    if phase == 'create':
        import vnext_normal_update

        assert not WORK.exists()
        WORK.mkdir()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = vnext_normal_update.main(['--process', '--company',
                'marriott_international', '--metric', 'C04', '--data-root',
                str(SOURCE), '--state-root', str(WORK/'state')])
        report = json.loads(output.getvalue())
        (HERE/'cli-report.json').write_text(json.dumps(report,
            ensure_ascii=False, indent=2) + '\n')
        metric, = report['companies'][0]['metrics']
        assert rc == 0 and report['companies'][0]['status'] == 'UPDATES_READY'
        assert metric['metric_id'] == 'C04' and metric['status'] == 'CANDIDATE_READY'
    else:
        from vnext import c04_update_cycle as c04
        from vnext import normal_run_v3 as normal
        from vnext import ordinary_update_cycle as ordinary

        path = WORK/'state/marriott_international/metrics/C04-registration-v3'
        configuration = ordinary._read(path/'configuration.json')
        assert configuration['route'] == c04.ROUTE
        state = ordinary._state(path, configuration)
        assert state['successful_attempt'] is not None
        terminal = ordinary._terminal(path, state['successful_attempt'])
        result = c04._verify_candidate(path, terminal, configuration)['C04']
        assert result['publication'] == 'PUBLISHED'
        from vnext.canonical import strict_json_file

        attempt = ordinary._attempt(path, state['successful_attempt'])
        run = attempt/'runs/C04'
        manifest = strict_json_file(path=run/'manifest.json')
        key = manifest['run_id'][len(normal.PREFIX):]
        binding = strict_json_file(path=attempt/'data'/normal.BINDING_DIRECTORY/
            (key+'.json'))
        assert binding['input_binding']['c04_registration_successor'][
            'event_forms'] == list(c04.EVENT_FORMS)
        details = {'route': configuration['route'],
            'run_id': manifest['run_id'], 'result_id': result['result_id'],
            'publication': result['publication'],
            'reason_code': result['reason_code'],
            'bound_event_forms': binding['input_binding'][
                'c04_registration_successor']['event_forms'],
            'old_semantic_exports_disabled': disabled,
            'source_snapshot_id': verified['snapshot_id']}
        (HERE/'cold.json').write_text(json.dumps(details,
            ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(details, sort_keys=True), flush=True)
after = {key: digest(path) for key, path in originals.items()}
assert before == after
