"""Create and cold-read one D02 text Run with old semantic producers blocked."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
PREVIOUS = ROOT/'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py'
spec = importlib.util.spec_from_file_location('issue28_b01_exit_probe', PREVIOUS)
old_probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_probe)
sys.path.insert(0, str(ROOT/'scripts'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_one(root, *, cold_read):
    with old_probe.legacy_disabled() as count:
        from vnext import normal_run_v3 as normal
        from vnext.ordinary_projection import render_ordinary_run
        from vnext.run_store import _mechanically_replay_open_run
        source = Path(json.loads((root/'source.json').read_text())['processing_root'])
        data, run = root/'data', root/'run'
        if not cold_read:
            normal.install_normal_inputs(data_root=data, source_root=source,
                company_id='marriott_international', metric_id='D02')
            created = normal.create_normal_run(data_root=data, run_dir=run,
                company_id='marriott_international', metric_id='D02')
            result = created['result']
        else:
            manifest, records, _ = _mechanically_replay_open_run(
                run_dir=run, repo_root=data, require_complete_results=True)
            normal.replay_case(data_root=data, manifest=manifest)
            result, = [record for record in records
                       if record['record_type'] == 'METRIC_RESULT'
                       and record['metric_id'] == 'D02']
        rendered = render_ordinary_run(data_root=data, run_dir=run)
        assert result['publication'] == 'PUBLISHED'
        assert result['value_kind'] == 'TEXT_V1'
        assert result['value'] and len(result['value']) > 100
        row = rendered['files']['metrics_matrix.csv']
        report = {'result_id': result['result_id'],
            'value_sha256': hashlib.sha256(result['value'].encode()).hexdigest(),
            'value_characters': len(result['value']),
            'public_row_sha256': hashlib.sha256(row).hexdigest(),
            'old_semantic_exports_disabled': count, 'cold_read': cold_read}
        (root/('cold.json' if cold_read else 'created.json')).write_text(
            json.dumps(report, sort_keys=True)+'\n')
        print(json.dumps(report, sort_keys=True), flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] in {'--create', '--read'}:
        run_one(Path(sys.argv[2]), cold_read=sys.argv[1] == '--read')
        return
    assert sys.argv[1:] == []
    ledger = old_probe.LEDGER
    before = {name: digest(path) for name, path in {
        'claims': ledger/'claims.jsonl',
        'source_log': ledger/'source-inputs/evidence/requests_log.csv',
        'active': ROOT/'outputs/active_publication.json'}.items()}
    with tempfile.TemporaryDirectory(prefix='issue28-d02-no-legacy-') as temp:
        root = Path(temp).resolve()
        old_probe.create_source(root)
        for phase in ('--create', '--read'):
            subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            phase, str(root)], cwd=ROOT, check=True)
        created = json.loads((root/'created.json').read_text())
        cold = json.loads((root/'cold.json').read_text())
        assert created['result_id'] == cold['result_id']
        assert created['value_sha256'] == cold['value_sha256']
        assert created['public_row_sha256'] == cold['public_row_sha256']
        source = json.loads((root/'source.json').read_text())
    after = {name: digest(path) for name, path in {
        'claims': ledger/'claims.jsonl',
        'source_log': ledger/'source-inputs/evidence/requests_log.csv',
        'active': ROOT/'outputs/active_publication.json'}.items()}
    assert before == after
    result = {'status': 'D02_TEXT_RUN_AND_COLD_READ_WITH_LEGACY_EXPORTS_DISABLED',
        'company_id': 'marriott_international', 'metric_id': 'D02',
        'source_snapshot_id': source['snapshot_id'],
        'v14_closure': source['requirement_closure'],
        'result_id': created['result_id'],
        'value_sha256': created['value_sha256'],
        'value_characters': created['value_characters'],
        'public_row_sha256': created['public_row_sha256'],
        'legacy_exports_disabled': created['old_semantic_exports_disabled'],
        'independent_process_cold_read': True,
        'original_source_ledger_and_active_bytes_unchanged': True,
        'new_real_calls': [0, 0, 0], 'all390_proven': False,
        'old_entrypoints_formally_retired': False}
    Path(__file__).with_name('result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
