"""Create and independently read one B01 Run with legacy producers disabled."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path.insert(0, str(ROOT / 'scripts'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def legacy_disabled():
    import sec_pipeline as legacy
    from vnext.canonical import strict_json_file

    assert 'vnext.normal_run_v3' not in sys.modules
    inventory = strict_json_file(path=ROOT/
        'requirements/issue_15_v1/legacy_semantic_producer_inventory.json')
    names = [row['producer_id'].split('::')[1] for row in
             inventory['producers'] if row['kind'] == 'SEMANTIC_PRODUCER']
    metrics = set(strict_json_file(path=ROOT/
        'config/source_strategy_registry.json')['metrics'])
    assert len(names) == len(set(names)) == 116 and len(metrics) == 39
    assert set(metric for row in inventory['producers']
               if row['kind'] == 'SEMANTIC_PRODUCER'
               for metric in row['covered_metric_ids']) == metrics
    old_popen = subprocess.Popen

    def local_git_only(*args, **kwargs):
        command = args[0] if args else kwargs.get('args')
        if (not isinstance(command, (list, tuple)) or not command
                or Path(command[0]).name != 'git'
                or any(part in {'fetch', 'pull', 'push', 'clone',
                                'ls-remote', 'submodule'} for part in command)):
            raise AssertionError('NONLOCAL_SUBPROCESS_FORBIDDEN')
        return old_popen(*args, **kwargs)

    @contextmanager
    def scope():
        replacements = {name: legacy.retired_legacy_entrypoint(producer=name)
                        for name in names}
        with patch.multiple(legacy, **replacements), \
             patch.object(legacy, 'MIGRATED_VNEXT_METRIC_IDS',
                          frozenset(metrics)), \
             patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo',
                          side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',
                   side_effect=AssertionError('HTTP_FORBIDDEN')), \
             patch.object(subprocess, 'Popen', side_effect=local_git_only):
            try:
                getattr(legacy, names[0])()
            except legacy.LegacyPathStillActiveError:
                pass
            else:
                raise AssertionError('LEGACY_CONTROL_NOT_BLOCKED')
            yield len(names)

    return scope()


def create_source(root):
    from vnext.ordinary_processing_source import current_processing_source
    from vnext.requirements import load_requirement_snapshot
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements/issue_28_v14')
    fd = __import__('os').open(LEDGER, __import__('os').O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = current_processing_source(
            acquisition_root=LEDGER/'source-inputs',
            output_parent=root/'processing', requirement=requirement)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        __import__('os').close(fd)
    (root/'source.json').write_text(json.dumps({
        'processing_root': str(result['data_root']),
        'snapshot_id': result['snapshot_id'],
        'requirement_closure': requirement['requirement_closure_hash']})+'\n')


def native(root, *, cold_read):
    with legacy_disabled() as count:
        from vnext import normal_run_v3 as normal
        from vnext.ordinary_projection import render_ordinary_run
        from vnext.run_store import _mechanically_replay_open_run
        source = Path(json.loads((root/'source.json').read_text())['processing_root'])
        data, run = root/'data', root/'run'
        if not cold_read:
            normal.install_normal_inputs(data_root=data, source_root=source,
                company_id='salesforce', metric_id='B01')
            created = normal.create_normal_run(data_root=data, run_dir=run,
                company_id='salesforce', metric_id='B01')
            result = created['result']
        else:
            manifest, records, _ = _mechanically_replay_open_run(
                run_dir=run, repo_root=data, require_complete_results=True)
            normal.replay_case(data_root=data, manifest=manifest)
            result, = [row for row in records if row['record_type'] ==
                       'METRIC_RESULT' and row['metric_id'] == 'B01']
        rendered = render_ordinary_run(data_root=data, run_dir=run)
        assert result['publication'] == 'PUBLISHED'
        assert result['value'] == '41525000000'
        row = rendered['files']['metrics_matrix.csv']
        report = {'result_id': result['result_id'],
                  'value': result['value'],
                  'row_sha256': hashlib.sha256(row).hexdigest(),
                  'old_semantic_exports_disabled': count,
                  'cold_read': cold_read}
        (root/('cold.json' if cold_read else 'created.json')).write_text(
            json.dumps(report, sort_keys=True)+'\n')
        print(json.dumps(report, sort_keys=True), flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] in {'--create', '--read'}:
        native(Path(sys.argv[2]), cold_read=sys.argv[1] == '--read')
        return
    assert sys.argv[1:] == []
    before = {name: digest(path) for name, path in {
        'claims': LEDGER/'claims.jsonl',
        'source_log': LEDGER/'source-inputs/evidence/requests_log.csv',
        'active': ROOT/'outputs/active_publication.json'}.items()}
    with tempfile.TemporaryDirectory(prefix='issue28-b01-no-legacy-') as temp:
        root = Path(temp).resolve()
        create_source(root)
        for phase in ('--create', '--read'):
            subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            phase, str(root)], cwd=ROOT, check=True)
        created = json.loads((root/'created.json').read_text())
        cold = json.loads((root/'cold.json').read_text())
        assert created['result_id'] == cold['result_id']
        assert created['row_sha256'] == cold['row_sha256']
        source = json.loads((root/'source.json').read_text())
    after = {name: digest(path) for name, path in {
        'claims': LEDGER/'claims.jsonl',
        'source_log': LEDGER/'source-inputs/evidence/requests_log.csv',
        'active': ROOT/'outputs/active_publication.json'}.items()}
    assert before == after
    result = {'status': 'B01_NATIVE_RUN_AND_COLD_READ_WITH_LEGACY_EXPORTS_DISABLED',
        'company_id': 'salesforce', 'metric_id': 'B01',
        'source_snapshot_id': source['snapshot_id'],
        'v14_closure': source['requirement_closure'],
        'result_id': created['result_id'], 'value': created['value'],
        'public_row_sha256': created['row_sha256'],
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
