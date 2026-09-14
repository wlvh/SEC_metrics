"""B13 registered source assessments enter the existing ordinary Run writer."""
from pathlib import Path

from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file
from .capacity_utilization_source import need
from .capacity_semantic_source import prepare_capacity_semantic_source
from .capacity_assessment_input import EXPORT_PATH, EXPORT_PATHS, load_registered_input
from .continuous_call_policy import REQUIREMENT_ID
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .requirements import load_requirement_snapshot
from .sources import raw_blob_record, source_reference_record, resolve_repository_file
from .specs import compile_spec_file

SPEC_PATH = 'catalog/r5/B13_capacity_disclosures_v1.md'


def prepare_case(*, data_root, company_id, assessment_mode=None, assessment_input_id=None, metric_id='B13'):
    need(metric_id in {'B13', 'D04'}, 'NATIVE_ASSESSED_METRIC_UNSUPPORTED')
    from .capacity_utilization_source import policy
    _, approved = policy()
    if metric_id == 'B13' and company_id not in approved['applicable_company_ids']:
        need(assessment_mode is None and assessment_input_id is None, 'B13_STRUCTURAL_ASSESSMENT_NOT_USED')
        return _prepare_structural_case(data_root=data_root, company_id=company_id)
    spec_path = SPEC_PATH
    if metric_id == 'B13':
        source = prepare_capacity_semantic_source(repo_root=data_root, company_id=company_id)
    else:
        from .d04_native_assessment import native_source, SPEC_PATH as spec_path
        from .r6_semantic_source import prepare_d04_semantic_source
        source = native_source(prepare_d04_semantic_source(repo_root=data_root, company_id=company_id))
    requirement = load_requirement_snapshot(snapshot_dir=data_root / 'requirements' / REQUIREMENT_ID)
    registered = load_registered_input(data_root=data_root, source=source, requirement=requirement,
                                       mode=assessment_mode, input_record_id=assessment_input_id)
    assessment = registered['assessment']
    need(assessment['proposed_branch'] in {'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW',
                                         'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'},
         metric_id + '_NATIVE_BRANCH_REQUIRES_IMPLEMENTATION:' + assessment['proposed_branch'])
    spec = compile_spec_file(path=data_root / spec_path, dependency_specs={})
    need(sha256_file(path=data_root / spec_path) == sha256_file(path=ROOT / spec_path), 'B13_INSTALLED_SPEC_CHANGED')
    annual = source['prepared_annual_input']; period = annual['table_input']['target_period']
    scope = spec['compiled']['required_claims']
    target = {'company_id': company_id, 'entity': annual['entity'], 'accession': annual['filing']['accessionNumber'],
        'period_start': period['period_start'], 'period_end': period['period_end'],
        'scope': scope, 'scope_key': content_hash(value=scope)}
    records = []; references = []; raw = {}; represented = set()
    for document in source['documents']:
        ref, blob = document['source_reference'], document['raw_blob']
        records.extend([blob, ref]); references.append(ref)
        raw[blob['raw_asset_id']] = resolve_repository_file(repo_root=data_root, repo_relative_path=blob['storage_uri']).read_bytes()
        represented.add((ref['source_url'], blob['raw_asset_id']))
    for proof in source['source_proofs']:
        key = (proof['source_url'], 'sha256:' + proof['content_sha256'])
        if key in represented:
            continue
        blob = raw_blob_record(repo_root=data_root, repo_relative_path=proof['request_repo_relative_path'],
                              media_type='application/json' if proof['document_name'].endswith('.json') else 'text/plain')
        ref = source_reference_record(raw_blob=blob, company_id=company_id, source_url=proof['source_url'],
            accession=proof['accession'] or 'SUBMISSIONS-' + annual['entity'],
            document_name=proof['document_name'], source_role='supporting_input',
            request_attempt_id=proof['request_attempt_id'])
        records.extend([blob, ref]); references.append(ref); represented.add(key)
    admission = verify_ordinary_source_proofs(data_root=data_root, proofs=source['source_proofs'])
    records = list({content_hash(value=record): record for record in records}.values())
    binding = {'company_id': company_id, 'source_id': source['semantic_source_id'],
               'prepared_annual_input': annual,
               'assessment_input_id': registered['input_record_id'],
               'assessment_set_id': assessment['assessment_set_id'], 'source_proofs': source['source_proofs'],
               'mode': registered['mode'], 'export_path': EXPORT_PATHS[metric_id], 'production_authorized': False}
    return {'kind': 'TEXT', 'primary_metric_id': metric_id, 'input_binding': binding,
        'source_records': records, 'expected_records': records, 'references': references,
        'source_proofs': source['source_proofs'], 'admission': admission,
        'spec_paths': {metric_id: spec_path}, 'compiled_specs': {metric_id: spec}, 'target_period': period,
        'text_arguments': {'compiled_spec': spec, 'target': target, 'source': source, 'assessment': assessment,
            'source_references': [d['source_reference'] for d in source['documents']], 'raw_bytes_by_id': raw},
        'registered_input': registered,
        'selection': {'status': (('NOT_AVAILABLE_SEC' if metric_id == 'B13' else 'TEXT_QUAL') if assessment['proposed_branch'] ==
                                'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW' else 'TEXT_QUAL'),
                      'reason_code': 'COMPLETE_NATIVE_CAPACITY_ASSESSMENT',
                      'assessment_mode': registered['mode'], 'numeric_utilization_inferred': False}}


def _prepare_structural_case(*, data_root, company_id):
    """The approved company set is applicability authority, not a disclosure scan."""
    from .normal_annual_input_v2 import prepare_saved_annual_input
    from .capacity_utilization_source import policy
    from .text_results import build_text_result_and_trace
    from .traits import repository_company_traits
    _, approved = policy()
    repository_company_traits(repo_root=data_root, company_id=company_id)
    need(company_id not in approved['applicable_company_ids'], 'B13_APPLICABLE_COMPANY_CANNOT_BE_STRUCTURAL')
    annual = prepare_saved_annual_input(repo_root=data_root, company_id=company_id)
    period = annual['table_input']['target_period']
    spec = compile_spec_file(path=data_root / SPEC_PATH, dependency_specs={})
    need(sha256_file(path=data_root / SPEC_PATH) == sha256_file(path=ROOT / SPEC_PATH), 'B13_INSTALLED_SPEC_CHANGED')
    scope = spec['compiled']['required_claims']
    target = {'company_id': company_id, 'entity': None, 'accession': None,
        'period_start': period['period_start'], 'period_end': period['period_end'],
        'scope': scope, 'scope_key': content_hash(value=scope)}
    records = []; references = []
    for proof in annual['source_proofs']:
        blob = raw_blob_record(repo_root=data_root, repo_relative_path=proof['request_repo_relative_path'],
            media_type='application/json' if proof['document_name'].endswith('.json') else 'text/plain')
        ref = source_reference_record(raw_blob=blob, company_id=company_id, source_url=proof['source_url'],
            accession=proof['accession'] or 'SUBMISSIONS-' + annual['entity'],
            document_name=proof['document_name'], source_role='supporting_input',
            request_attempt_id=proof['request_attempt_id'])
        records.extend([blob, ref]); references.append(ref)
    records = list({content_hash(value=r): r for r in records}.values())
    references = list({r['source_reference_id']: r for r in references}.values())
    admission = verify_ordinary_source_proofs(data_root=data_root, proofs=annual['source_proofs'])
    result, trace = build_text_result_and_trace(compiled_spec=spec, target=target,
        structural=True, reason_code='TRAIT_NOT_APPLICABLE')
    return {'kind': 'STRUCTURED', 'primary_metric_id': 'B13',
        'input_binding': {'company_id': company_id, 'prepared_annual_input': annual,
                          'approved_b13_scope': approved, 'source_proofs': annual['source_proofs']},
        'source_records': records, 'expected_records': [*records, trace, result], 'references': references,
        'source_proofs': annual['source_proofs'], 'admission': admission,
        'spec_paths': {'B13': SPEC_PATH}, 'compiled_specs': {'B13': spec}, 'target_period': period,
        'results': {'B13': result}, 'traces': {'B13': trace}, 'observations': [],
        'selection': {'status': 'N_A_STRUCTURAL', 'category': 'APPROVED_B13_COMPANY_SCOPE',
                      'reason_code': 'B13_OUTSIDE_APPROVED_APPLICABILITY', 'disclosure_absence_asserted': False}}


def install_inputs(*, data_root, company_id, source_root=ROOT, assessment_mode=None, assessment_input_id=None, metric_id='B13'):
    from .normal_run_v3 import _external, _install_case_inputs, _binding
    data_root = _external(data_root)
    source_root = ROOT if Path(source_root) == ROOT else _external(source_root)
    need(source_root != data_root and source_root not in data_root.parents and data_root not in source_root.parents,
         'B13_INPUT_OUTPUT_OVERLAP')
    case = prepare_case(data_root=source_root, company_id=company_id, assessment_mode=assessment_mode,
                        assessment_input_id=assessment_input_id, metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements' / REQUIREMENT_ID)
    extra = ({EXPORT_PATHS[metric_id]: canonical_json_bytes(value=case['registered_input'])}
             if 'registered_input' in case else None)
    _install_case_inputs(data_root=data_root, source_root=source_root, company_id=company_id, case=case,
        requirement=requirement, extra_input_bytes=extra)
    rebuilt = prepare_case(data_root=data_root, company_id=company_id, metric_id=metric_id)
    need(_binding(case, requirement) == _binding(rebuilt, requirement), 'B13_IMPORTED_NATIVE_INPUT_CHANGED')
    return rebuilt


def create_run(*, data_root, run_dir, company_id, metric_id='B13'):
    from .normal_run_v3 import _create_case_run
    case = prepare_case(data_root=Path(data_root), company_id=company_id, metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=Path(data_root) / 'requirements' / REQUIREMENT_ID)
    return _create_case_run(data_root=data_root, run_dir=run_dir, company_id=company_id, metric_id=metric_id,
                            case=case, requirement=requirement)


def validate_run_authority(*, repo_root, manifest, records, compiled_specs):
    from .normal_run_v3 import PREFIX, BINDING_DIRECTORY, _binding
    need(manifest['requirement_id'] == REQUIREMENT_ID and manifest['run_id'].startswith(PREFIX)
         and (compiled_specs is None or len(compiled_specs) == 1), 'B13_NATIVE_RUN_ROUTE_REQUIRED')
    original_key = manifest['run_id'][len(PREFIX):]
    saved = strict_json_file(path=resolve_repository_file(repo_root=repo_root,
        repo_relative_path=BINDING_DIRECTORY + '/' + original_key + '.json'))
    metric_id = saved['primary_metric_id']
    need(metric_id in {'B13', 'D04'}, 'NATIVE_ASSESSED_METRIC_UNSUPPORTED')
    case = prepare_case(data_root=repo_root, company_id=manifest['company_id'], metric_id=metric_id)
    requirement = load_requirement_snapshot(snapshot_dir=repo_root / 'requirements' / REQUIREMENT_ID)
    expected = _binding(case, requirement)
    key = content_hash(value=expected)[7:]
    need(manifest['run_id'] == PREFIX + key
         and strict_json_file(path=resolve_repository_file(repo_root=repo_root,
            repo_relative_path=BINDING_DIRECTORY + '/' + key + '.json')) == expected,
         'B13_NATIVE_RUN_BINDING_CHANGED')
    need((compiled_specs is None or compiled_specs == case['compiled_specs']) and manifest['source_references'] == case['references']
         and manifest['target_period'] == case['target_period']
         and manifest['spec_file_hashes'] == {p: sha256_file(path=repo_root / p) for p in case['spec_paths'].values()},
         'B13_NATIVE_RUN_SOURCE_SPEC_OR_PERIOD_CHANGED')
    if records is not None:
        actual_sources = [r for r in records if r['record_type'] in {'RAW_BLOB', 'SOURCE_REFERENCE'}]
        need(sorted(actual_sources, key=content_hash_key) == sorted(case['source_records'], key=content_hash_key),
             'B13_NATIVE_RUN_SOURCE_RECORDS_CHANGED')
        if case['kind'] == 'STRUCTURED':
            need(sorted(records, key=content_hash_key) == sorted(case['expected_records'], key=content_hash_key),
                 'B13_STRUCTURAL_RECORD_SET_CHANGED')
    return case


def content_hash_key(value):
    return content_hash(value=value)


def project_defined_absence(*, case, result, row, company):
    """Expose the reviewed source census without inventing a source quotation."""
    from .publication import EVIDENCE_FIELDS
    import json
    assessment = case['registered_input']['assessment']
    metric = result['metric_id']
    reason, status = {'B13': ('B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE', 'NOT_AVAILABLE_SEC'),
                      'D04': ('D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE', 'TEXT_QUAL')}[metric]
    need(result['reason_code'] == reason
         and result['value'] is None and result['publication'] == 'WITHHELD'
         and case['selection']['status'] == status
         and assessment['proposed_branch'] == 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
         and assessment['all_source_requests_accepted'] and not assessment['failed_requests']
         and not assessment['missing_request_ids'], 'B13_ABSENCE_PROJECTION_NOT_ESTABLISHED')
    row.update(status=status, value='',
        notes='No relevant disclosure in the complete saved annual primary and current annual amendments. '
              'This is a defined-scope source assessment; no utilization value is inferred.')
    if metric == 'D04':
        row['notes'] = '未披露持续经营疑虑：已检查保存的完整年报及本期修订、原生事实和续接对象；这不表示对未来财务状况作保证。'
    source = case['text_arguments']['source']; evidence = []
    for document in source['documents']:
        ref, blob = document['source_reference'], document['raw_blob']
        item = {key: '' for key in EVIDENCE_FIELDS}
        item.update(company=company['display_name'], cik=company['primary_cik'], metric_id=metric,
            source_url=ref['source_url'], repo_relative_path=blob['storage_uri'],
            content_sha256=ref['raw_asset_id'][7:], accession=ref['accession'], document_name=ref['document_name'],
            concept_or_section='Defined source scope', unit='text',
            period_start=result['period_start'], period_end=result['period_end'],
            context_or_dimension=json.dumps({'assessment_set_id': assessment['assessment_set_id'],
                'scope': source['source_check_scope'], 'source_unit_ids': document['source_unit_ids'],
                'assessment_mode': assessment['mode']}, sort_keys=True),
            evidence_quote='Host scope-check record; no source quotation or numeric value is asserted.',
            extraction_method='complete_native_' + metric.lower() + '_assessment', parser_version='capacity_run')
        evidence.append(item)
    return row, evidence


def prepare_text_contexts(*, repo_root, manifest, records, compiled_specs, **unused):
    from . import capacity_text_results as api
    case = validate_run_authority(repo_root=repo_root, manifest=manifest, records=records, compiled_specs=compiled_specs)
    candidates = [r for r in records if r['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE']
    if case['kind'] == 'STRUCTURED':
        need(not candidates, 'B13_STRUCTURAL_TEXT_CANDIDATE_FORBIDDEN')
        return {}
    expected = api.create_deterministic_text_candidate(**case['text_arguments'])
    need(candidates == [expected], 'B13_NATIVE_TEXT_CANDIDATE_SET_CHANGED')
    return {expected['candidate_hash']: case['text_arguments']}
