"""Original V14 saved-assessment worker; never calls register or a provider."""
import json
from pathlib import Path
import shutil
import socket
import sys
from unittest.mock import patch


def need(condition, reason):
    if not condition: raise ValueError(reason)


def main():
    action, program, packet, source, work = sys.argv[1:]
    program = Path(program); packet = Path(packet); source = Path(source); work = Path(work)
    from company_worker_guard import install_worker_guards
    install_worker_guards(program)
    sys.path[:0] = [str(program), str(program/'scripts')]
    from vnext.canonical import strict_json_file
    from vnext.requirements import load_requirement_snapshot
    from vnext.requirement_profile_v1 import validate_execution_authority
    requirement = load_requirement_snapshot(snapshot_dir=program/'requirements/issue_28_v14')
    validate_execution_authority(repo_root=program, requirement=requirement)
    with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_PROCESSING_NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_PROCESSING_DNS_FORBIDDEN')):
        if action == 'export':
            from vnext.capacity_run import prepare_case
            record = strict_json_file(path=program/'config/ordinary_going_concern_assessment.json')
            case = prepare_case(data_root=program, company_id=record['company_id'], metric_id='D04')
            need(case['registered_input'] == record, 'COMPANY_PROCESSING_ORIGINAL_RECORD_CHANGED')
            # The unchanged runtime excludes SEC originals and processing state.
            from vnext.requirement_profile import requirement_authority_paths
            foundation = strict_json_file(path=program/'requirements/issue_15_v1/foundation_verification_receipt.json')
            paths = set(requirement_authority_paths(repo_root=program,requirement=requirement))
            paths.update(row['path'] for row in foundation['receipt_bindings'])
            cursor = requirement
            while cursor:
                paths.update(cursor.get('execution_authority', {}).get('files', {}))
                paths.update(cursor.get('baseline', {}).get('new_rule_files', {}))
                cursor = cursor.get('parent_snapshot')
            for directory in ('scripts','tools','requirements','catalog','config'):
                paths.update(p.relative_to(program).as_posix() for p in (program/directory).rglob('*')
                             if p.is_file() and '__pycache__' not in p.parts)
            index = strict_json_file(path=program/'docs/evidence/issue28_continuous/frozen-parent-v10-index.json')
            paths.update('docs/evidence/issue28_continuous/frozen-parent-v10/'+p for p in index['files'])
            paths.difference_update({'config/ordinary_capacity_assessment.json','config/ordinary_going_concern_assessment.json'})
            need(not any(p.startswith('evidence/') for p in paths), 'COMPANY_PROCESSING_PROGRAM_CONTAINS_SEC')
            work.mkdir()
            for relative in sorted(paths):
                target=work/relative; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((program/relative).read_bytes())
            print(json.dumps({'record':record,'source':case['text_arguments']['source'],
                              'requirement_id':requirement['requirement_id'],
                              'requirement_closure_hash':requirement['requirement_closure_hash']}))
            return
        metadata = strict_json_file(path=packet/'processing.json')
        need(metadata['requirement_closure_hash'] == requirement['requirement_closure_hash'], 'COMPANY_PROCESSING_ORIGINAL_RUNTIME_REQUIRED')
        from vnext import capacity_assessment_input as registered
        from vnext.capacity_run import install_inputs, create_run
        from vnext.ordinary_projection import render_ordinary_run
        if action == 'compute':
            view = work/'processing-source'
            # Rules come solely from the original fixed computation program.
            shutil.copytree(program, view, ignore=shutil.ignore_patterns('.git','__pycache__'))
            for path in [view, *view.rglob('*')]:
                path.chmod(path.stat().st_mode | (0o700 if path.is_dir() else 0o600))
            for directory in ('evidence',):
                shutil.copytree(source/directory,view/directory)
            shutil.copyfile(source/'config/company_registry.csv',view/'config/company_registry.csv')
            shutil.copyfile(packet/'config/ordinary_going_concern_assessment.json',view/'config/ordinary_going_concern_assessment.json')
            # This adapter is explicitly baseline-only. Its raw files retain
            # their original full ledger and ordinary baseline authentication.
            need(not (view/'config/ordinary_source_checkpoint.json').exists(), 'COMPANY_PROCESSING_BASELINE_VIEW_REQUIRED')
            registered.ROOT = view
            installed=install_inputs(data_root=work/'data',source_root=view,company_id=metadata['company_id'],
                metric_id='D04',assessment_mode=metadata['mode'],
                assessment_input_id=metadata['input_record_id'])
            created=create_run(data_root=work/'data',run_dir=work/'runs/D04',company_id=metadata['company_id'],metric_id='D04')
        else:
            registered.ROOT = work/'data'
            from vnext.capacity_assessment_input import load_registered_input
            load_registered_input(data_root=work/'data',source=strict_json_file(path=packet/'processing-source.json'),
                requirement=requirement,mode=metadata['mode'],input_record_id=metadata['input_record_id'])
            created=None
        rendered=render_ordinary_run(data_root=work/'data',run_dir=work/'runs/D04')
        if action == 'compute':
            completed = created['result']['publication'] == 'PUBLISHED'
            if not completed and created['result'].get('reason_code') == 'D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE':
                from vnext.capacity_run import project_defined_absence
                from vnext.normal_annual_input import _registry_rows
                company = next(c for c in _registry_rows(repo_root=work/'data') if c['company_id'] == metadata['company_id'])
                row, evidence = project_defined_absence(case=installed, result=created['result'], row={}, company=company)
                completed = (row['status'] == rendered['row']['status'] and row['value'] == rendered['row']['value']
                             and evidence == rendered['evidence'])
            rows=work/'rows/D04'; rows.mkdir(parents=True)
            for name,raw in rendered['files'].items():(rows/name).write_bytes(raw)
            shutil.rmtree(view)
            print(json.dumps({'result_id':created['result']['result_id'],'run_id':created['manifest']['run_id'],
                'publication':created['result']['publication'],'native_assessment_completed':completed,'mode':metadata['mode']}))
        else:
            import base64
            print(json.dumps({name:base64.b64encode(raw).decode('ascii') for name,raw in rendered['files'].items()}))


if __name__ == '__main__':
    main()
