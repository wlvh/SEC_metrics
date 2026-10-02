"""Export one company's native candidate rows and replay inputs."""
import os
from pathlib import Path
import shutil
from uuid import uuid4

from .canonical import canonical_json_bytes, strict_json_file
from .company_handoff import binding, external, locked_company, recover_import
from .company_source_authority import need


def export_results(*, state_root, output_root, company_id):
    output = external(output_root)
    need(not output.exists(), 'COMPANY_RESULT_EXPORT_OUTPUT_EXISTS')
    with locked_company(state_root) as root:
        current = recover_import(root)
        need(current and current['company_id'] == company_id,
             'COMPANY_RESULT_EXPORT_WRONG_COMPANY')
        need(root not in output.parents and output not in root.parents,
             'COMPANY_RESULT_EXPORT_STATE_OVERLAP')
        report = strict_json_file(path=root/'company-results.json')
        need(report['company_id'] == company_id, 'COMPANY_RESULT_REPORT_WRONG_COMPANY')
        staged = output.parent/('.'+output.name+'.preparing-'+uuid4().hex)
        staged.mkdir(parents=True)
        try:
            native = []
            for metric in report['metrics']:
                candidate = metric.get('last_verified_candidate')
                if not candidate:
                    continue
                rows = Path(candidate['rows_root'])
                work = rows.parent
                need(root in work.parents and work.name == candidate['attempt_id'],
                     'COMPANY_RESULT_CANDIDATE_PATH_CHANGED')
                manifests = list((work/'runs').glob('*/manifest.json'))
                need(len(manifests) == 1, 'COMPANY_RESULT_NATIVE_RUN_SET_CHANGED')
                for manifest_path in manifests:
                    manifest = strict_json_file(path=manifest_path)
                    need(manifest['company_id'] == company_id,
                         'COMPANY_RESULT_NATIVE_RUN_WRONG_COMPANY')
                    historical = manifest['requirement_id'] == 'issue_54_v3'
                    if historical:
                        from .historical_projection import render_historical_run
                        from .normal_history_plan import checkpoint_replayed_once
                        from .publication import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
                        with checkpoint_replayed_once():
                            rendered = render_historical_run(data_root=work/'data',
                                run_dir=manifest_path.parent, frozen=manifest['status'] == 'FROZEN')
                        expected = {'metrics_matrix.csv': _csv_bytes(rows=[rendered['row']], fieldnames=METRIC_FIELDS),
                                    'metric_evidence.csv': _csv_bytes(rows=rendered['evidence'], fieldnames=EVIDENCE_FIELDS)}
                        row_directory = rows
                    else:
                        from .ordinary_projection import render_ordinary_run
                        rendered = render_ordinary_run(data_root=work/'data',
                            run_dir=manifest_path.parent, frozen=manifest['status'] == 'FROZEN')
                        expected = rendered['files']
                        row_directory = rows/metric['metric_id']
                    for name, raw in expected.items():
                        need((row_directory/name).read_bytes() == raw,
                             'COMPANY_RESULT_ROWS_CHANGED:'+name)
                need(not any(p.is_symlink() for p in work.rglob('*')),
                     'COMPANY_RESULT_NATIVE_INPUT_ALIAS')
                destination = staged/'native'/metric['metric_id']/work.name
                shutil.copytree(work, destination)
                native.append({'metric_id': metric['metric_id'],
                               'attempt_id': work.name,
                               'path': destination.relative_to(staged).as_posix()})
            (staged/'company-results.json').write_bytes(canonical_json_bytes(value=report))
            if (root/'latest_import.json').exists():
                shutil.copyfile(root/'latest_import.json', staged/'latest_import.json')
            files = {p.relative_to(staged).as_posix(): binding(p)
                     for p in sorted(staged.rglob('*')) if p.is_file()}
            index = {'record_type': 'COMPANY_RESULT_EXPORT_V1', 'company_id': company_id,
                     'current_source_checkpoint_id': current['checkpoint_id'],
                     'report_source_checkpoint_id': report['source_checkpoint_id'],
                     'report_matches_current_source': current['checkpoint_id'] == report['source_checkpoint_id'],
                     'native_candidates': native, 'files': files,
                     'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0},
                     'production_authorized': False}
            (staged/'export.json').write_bytes(canonical_json_bytes(value=index))
            os.rename(staged, output)
        except Exception:
            shutil.rmtree(staged)
            raise
        return {'status': 'EXPORTED', 'company_id': company_id,
                'output_root': str(output), 'native_candidates': native,
                'bytes': sum(v['size'] for v in files.values())}
