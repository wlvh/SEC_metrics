"""Original V14 saved-assessment worker; never calls register or a provider."""
import json
from pathlib import Path
import shutil
import socket
import sys
from unittest.mock import patch


def need(condition, reason):
    if not condition: raise ValueError(reason)


def project_capture_identity(current, original):
    """Project observation-only IDs for the unchanged original strict checker.

    Actual current proofs/semantic source remain saved separately and unchanged.
    Only request_attempt_id and its document/unit hash derivatives may differ;
    changed references, payloads, ordering or coverage receive no projection.
    The original checker still compares all annual data, body sets and requests.
    """
    from copy import deepcopy
    from vnext.canonical import content_hash
    for value in (current, original):
        need(value['semantic_source_id'] == content_hash(value={
            k: v for k, v in value.items() if k != 'semantic_source_id'}),
            'COMPANY_PROCESSING_CAPTURE_PROJECTION_SOURCE_CHANGED')
    projected = deepcopy(current)
    docs = original['documents']
    if len(current['documents']) != len(docs) or len(current['units']) != len(original['units']):
        return current, None
    document_ids, unit_ids, observations = {}, {}, []
    for new, old in zip(current['documents'], docs):
        left, right = new['source_reference'], old['source_reference']
        if {k: v for k, v in left.items() if k != 'request_attempt_id'} != {
                k: v for k, v in right.items() if k != 'request_attempt_id'}:
            return current, None
        document_ids[new['document_id']] = old['document_id']
        observations.append({'source_reference_id': left['source_reference_id'],
            'current_request_attempt_id': left.get('request_attempt_id'),
            'original_request_attempt_id': right.get('request_attempt_id')})
    for new, old in zip(current['units'], original['units']):
        body = {k: v for k, v in new.items() if k != 'unit_id'}
        old_body = {k: v for k, v in old.items() if k != 'unit_id'}
        need(new['unit_id'] == content_hash(value=body)
             and old['unit_id'] == content_hash(value=old_body),
             'COMPANY_PROCESSING_CAPTURE_PROJECTION_UNIT_CHANGED')
        body['document_id'] = document_ids.get(body['document_id'])
        if body != old_body:
            return current, None
        unit_ids[new['unit_id']] = old['unit_id']
    for new, old in zip(projected['documents'], docs):
        new['document_id'] = document_ids[new['document_id']]
        if 'request_attempt_id' in old['source_reference']:
            new['source_reference']['request_attempt_id'] = old['source_reference']['request_attempt_id']
        else:
            new['source_reference'].pop('request_attempt_id', None)
        binding = new.get('registrant_name_binding', {})
        for key in ('cover_caption', 'cover_name'):
            caption = binding.get(key, {})
            if caption.get('document_id') in document_ids:
                caption['document_id'] = document_ids[caption['document_id']]
        new['source_unit_ids'] = [unit_ids.get(i, i) for i in new['source_unit_ids']]
    for unit in projected['units']:
        unit['document_id'] = document_ids[unit['document_id']]
        unit['unit_id'] = unit_ids[unit['unit_id']]
    projected['required_unit_ids'] = [unit_ids.get(i, i) for i in projected['required_unit_ids']]
    # Annual discovery also records the observations that supplied its facts
    # and table. Project only those IDs, with every other annual field still
    # checked by the original content comparison below.
    annual_observations = []
    def annual_attempts(new, old, location):
        for key in ('companyfacts_input', 'table_input'):
            left, right = new.get(key), old.get(key)
            if isinstance(left, dict) and isinstance(right, dict) and 'request_attempt_id' in left:
                annual_observations.append({'location': location+'/'+key,
                    'current_request_attempt_id': left['request_attempt_id'],
                    'original_request_attempt_id': right.get('request_attempt_id')})
                if 'request_attempt_id' in right:
                    left['request_attempt_id'] = right['request_attempt_id']
                else:
                    left.pop('request_attempt_id')
        if isinstance(new.get('original_input'), dict) and isinstance(old.get('original_input'), dict):
            annual_attempts(new['original_input'], old['original_input'], location+'/original_input')
    annual_attempts(projected['prepared_annual_input'], original['prepared_annual_input'], 'prepared_annual_input')
    projected['semantic_source_id'] = content_hash(value={k: v for k, v in projected.items()
                                                        if k != 'semantic_source_id'})
    body = {'record_type': 'CURRENT_CAPTURE_IDENTITY_PROJECTION',
        'actual_current_source_id': current['semantic_source_id'],
        'comparison_source_id': projected['semantic_source_id'],
        'original_source_id': original['semantic_source_id'], 'observations': observations,
        'document_ids': document_ids, 'unit_ids': unit_ids, 'annual_observations': annual_observations,
        'current_source_proofs_rewritten': False, 'original_records_rewritten': False}
    return projected, {**body, 'projection_id': content_hash(value=body)}


def main():
    action, program, packet, source, work = sys.argv[1:]
    program = Path(program); packet = Path(packet); source = Path(source); work = Path(work)
    from company_worker_guard import install_worker_guards
    install_worker_guards(program)
    sys.path[:0] = [str(program), str(program/'scripts')]
    from vnext.canonical import strict_json_file
    from vnext.requirements import load_requirement_snapshot
    from vnext.requirement_profile_v1 import validate_execution_authority
    if action == 'source-admission':
        # The old baseline remains owned by its own fixed tree; the empty
        # local runtime must never re-sign it as a new-history baseline.
        from vnext.company_source_authority import require_company
        metadata = strict_json_file(path=packet/'processing.json')
        admission = require_company(source_root=source, company_id=metadata['company_id'])
        identity = 'issue_54_v1'
        requirement = load_requirement_snapshot(snapshot_dir=program/'requirements'/identity)
        validate_execution_authority(repo_root=program, requirement=requirement)
        need(admission['original_checkpoint'] is None, 'COMPANY_PROCESSING_ORIGINAL_BASELINE_REQUIRED')
        print(json.dumps(admission))
        return
    if action == 'current':
        from vnext.company_source_authority import require_company
        from vnext.r6_semantic_source import prepare_d04_semantic_source
        from vnext.d04_native_assessment import native_source
        metadata = strict_json_file(path=packet/'processing.json')
        record = strict_json_file(path=packet/'config/ordinary_going_concern_assessment.json')
        identity = next(i for i in ('issue_54_v4', 'issue_54_v2', 'issue_54_v1')
                        if (program/'requirements'/i).is_dir())
        requirement = load_requirement_snapshot(snapshot_dir=program/'requirements'/identity)
        validate_execution_authority(repo_root=program, requirement=requirement)
        require_company(source_root=source, company_id=metadata['company_id'])
        with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_PROCESSING_NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_PROCESSING_DNS_FORBIDDEN')):
            current = native_source(prepare_d04_semantic_source(repo_root=source,
                company_id=metadata['company_id'], ordinary_registered=True),
                request_context_format=record.get('request_context_format'),
                complete_response_contract=bool(record.get('response_contract_version')))
        print(json.dumps({'source':current, 'requirement_closure_hash':requirement['requirement_closure_hash']}))
        return
    requirement = load_requirement_snapshot(snapshot_dir=program/'requirements/issue_28_v14')
    validate_execution_authority(repo_root=program, requirement=requirement)
    with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_PROCESSING_NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_PROCESSING_DNS_FORBIDDEN')):
        if action == 'equivalence':
            from vnext.capacity_update_input import source_equivalence
            current = strict_json_file(path=work/'current-semantic-source.json')
            original = strict_json_file(path=packet/'processing-source.json')
            projection = None
            # Only the new empty-history company adapter needs observation ID
            # projection. Previously accepted prefix histories keep old checks.
            creator = Path(__file__).resolve().parents[2]
            if (creator/'requirements/issue_54_v4').is_dir():
                current, projection = project_capture_identity(current, original)
            proof = source_equivalence(current=current, original=original)
            if projection is not None:
                from vnext.canonical import content_hash
                body = {k: v for k, v in proof.items() if k != 'equivalence_id'}
                body['capture_identity_projection'] = projection
                proof = {**body, 'equivalence_id': content_hash(value=body)}
            print(json.dumps(proof))
            return
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
            # Incoming program and sources may both be read-only. Only this
            # transient private view is writable, including copied source
            # directories so its cleanup cannot turn a completed Run into a
            # failed execution report.
            for path in [view, *view.rglob('*')]:
                path.chmod(path.stat().st_mode | (0o700 if path.is_dir() else 0o600))
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
