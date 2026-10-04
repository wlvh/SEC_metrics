"""Actual table-input wire to pending native C02 proposals, never a Result.

This explicit successor does not rewrite the old plain-block mapper or wire.
The received layout, actual request and raw response have separate identities.
"""
import json
import re
from pathlib import Path

from git_workspace import first_symlink_in_path
from sec_http import write_immutable_bytes
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_loads, strict_json_file
from .c02_grouped_source import grouped_governance_source
from .c02_model_processing import _bytes, _response
from .c02_model_review_view import source_review_view
from .c02_table_context_417ccfb7 import FORMAT, PROVIDER_COMMIT, assert_matches, expanded_view
from .c02_table_development_input import prepare_ordinary_table_development_input
from .continuous_request_context import _load_tokenizer
from .records import validate_record
from .review import build_review_unit
from .specs import compile_spec_file
from .text_business_candidates import _excerpt
from .text_review import render_text_review

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'C02_BLOCK_TABLE_SOURCE_REFERENCES_V1'
SPEC_PATH = 'catalog/r6/C02_model_table_development_v1.md'


def _need(ok, reason):
    if not ok:
        raise ValueError('C02_TABLE_MODEL_' + reason)


def _checked_input(*, data_root, company_id, task_text, request_body,
                   response_body, expected_request_sha256, expected_response_sha256):
    _need(type(request_body) is bytes and type(response_body) is bytes, 'RAW_BYTES_REQUIRED')
    _need(sha256_bytes(content=request_body) == expected_request_sha256
          and sha256_bytes(content=response_body) == expected_response_sha256,
          'EXTERNAL_WIRE_CHANGED')
    prepared = prepare_ordinary_table_development_input(
        data_root=data_root, company_id=company_id, task_text=task_text)
    # Compare the actual two-message request, not a fabricated plain-block one.
    _need(request_body == prepared['request_body'] and prepared['measurement']['fits'],
          'REQUEST_OR_RESOURCE_CHANGED')
    request = strict_json_loads(text=request_body.decode('utf-8'))
    view = strict_json_loads(text=request['messages'][1]['content'])
    assert_matches(view, prepared['document'], prepared['table_grid'])
    tokenizer, _ = _load_tokenizer()
    _need(tokenizer is not None and len(tokenizer.encode(
        response_body.decode('utf-8'), add_special_tokens=False).ids) <= 4096, 'RESPONSE_LIMIT')
    facts, selected = _response(response_body, prepared['document'])
    return prepared, facts, selected


def _layout_review(view):
    """Display every table's text at its real coordinates without semantic picks."""
    _, tables = expanded_view(view)
    literal = lambda s: re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', str(s))
    lines = ['# Complete table text/header context',
             'Source images are not interpreted. Empty text is not non-membership.', '']
    for table in tables:
        lines += ['## ' + table['table_id'], literal(table['caption'])]
        for r, row in enumerate(table['cells']):
            cells = [f'c{c}{" (header)" if header else ""}: {literal(text)}'
                     for c, (text, header) in enumerate(row) if text or header]
            lines += [f'r{r}: ' + '; '.join(cells)]
    return '\n'.join(lines).encode('utf-8')


def build_table_development_assessment(*, data_root, company_id, task_text, request_body,
                                      response_body, expected_request_sha256,
                                      expected_response_sha256, origin):
    _need(origin in {'DEVELOPMENT_MODEL', 'RECORDED_PROGRAM_TEST'}, 'REAL_EXECUTION_FORBIDDEN')
    prepared, facts, selected = _checked_input(data_root=data_root, company_id=company_id,
        task_text=task_text, request_body=request_body, response_body=response_body,
        expected_request_sha256=expected_request_sha256,
        expected_response_sha256=expected_response_sha256)
    doc, raw, grid = prepared['document'], prepared['raw_source'], prepared['table_grid']
    source = prepared['source_reference']
    coverage = {'document_id': doc['text_document_id'],
        'source_reference_id': source['source_reference_id'],
        'scope': 'COMPLETE_TEXT_HEADER_INPUT_NOT_SEMANTIC_ABSENCE'}
    coverage['coverage_hash'] = content_hash(value=coverage)
    proposal = {'document_id': doc['text_document_id'],
        'source_reference_id': source['source_reference_id'],
        'candidates': [_excerpt(doc, doc['blocks'][i], 'GOVERNANCE_DISCLOSURES',
                                ['DEVELOPMENT_MODEL_REFERENCE']) for i in selected]}
    proposal['proposal_id'] = content_hash(value=proposal)
    _, grouped, grouped_coverage = grouped_governance_source(document=doc,
        proposal=proposal, coverage=coverage, raw_bytes=raw)
    quotes = grouped['candidates']
    _need(len(quotes) <= 64 and sum(len(q['text']) for q in quotes) <= 64000,
          'COMPLETE_QUOTATION_LIMIT')
    spec = compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})
    _need(spec['compiled']['disclosure_group'] == 'c02_model_table_development_v1'
          and spec['compiled']['quality_rule'] == {'model_development_method': POLICY}, 'SPEC_CHANGED')
    bindings_by_id = {s['source_reference_id']: s for s in prepared['input_binding']['source_references']}
    bindings = [bindings_by_id[sid] for sid in prepared['input_binding']['text_source_reference_ids']]
    processing = {'origin': origin, 'policy': POLICY,
        'request_sha256': expected_request_sha256, 'response_sha256': expected_response_sha256,
        'source_sha256': sha256_bytes(content=raw), 'source_reference_id': source['source_reference_id'],
        'source_filing': doc['source_filing'], 'model_facts_and_unresolved': facts,
        'spec_closure_hash': spec['spec_closure_hash'], 'mapper_sha256': sha256_file(path=Path(__file__)),
        'response_parser_sha256': sha256_file(path=ROOT/'scripts/vnext/c02_model_processing.py'),
        'formatter_provider_commit': PROVIDER_COMMIT,
        'formatter_sha256': sha256_file(path=ROOT/'scripts/vnext/c02_table_context_417ccfb7.py'),
        'input_builder_sha256': sha256_file(path=ROOT/'scripts/vnext/c02_table_development_input.py'),
        'task_text': task_text, 'task_sha256': sha256_bytes(content=task_text.encode()),
        'format_sha256': sha256_bytes(content=FORMAT.encode()),
        'request_context': prepared['measurement'], 'table_grid_id': grid['derived_asset_id'],
        'complete_view': prepared['view'], 'ordinary_input_binding': prepared['input_binding'],
        'annual_target': prepared['input_binding']['target'],
        'complete_source_partition_hash': grouped_coverage['complete_source_partition_hash'],
        'rendering_limitations': ['SOURCE_IMAGES_NOT_INTERPRETED', 'NOT_FULL_RAW_GRID_ROUNDTRIP'],
        'semantic_acceptance': False, 'model_answer_tested': origin == 'DEVELOPMENT_MODEL'}
    asset_body = {'parent_raw_asset_ids': [source['raw_asset_id']], 'transform_id': POLICY,
        'transform_semantic_version': '1', 'content_type': 'application/json', 'tables': [processing]}
    asset = validate_record(record={'record_type': 'DERIVED_ASSET', **asset_body,
        'derived_asset_id': content_hash(value=asset_body), 'storage_uri': 'processing/c02/table-metadata.json'})
    claims = {'excerpt_{:06d}'.format(i): {'value_kind': 'TEXT_V1', 'extent': 'FULL_BLOCK',
        'order': i, **{k: q[k] for k in ('text', 'source_reference_id', 'document_id',
            'section_id', 'block_index', 'raw_start_byte', 'raw_end_byte', 'raw_span_sha256')}}
        for i, q in enumerate(quotes)}
    body = {'disclosure_group': spec['compiled']['disclosure_group'],
        'source_reference_ids': [s['source_reference_id'] for s in bindings],
        'derived_asset_ids': [grid['derived_asset_id'], asset['derived_asset_id']],
        'selected': claims, 'competing_candidates': [], 'unresolved_competing_claims': facts['unresolved']}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE', **body,
        'candidate_hash': content_hash(value=body), 'status': 'REVIEW_REQUIRED',
        'attempt_id': 'development:c02:table:' + expected_response_sha256,
        'assistant_output_sha256': expected_response_sha256})
    eb = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS', 'normalized_values': claims,
        'checks': [{'check': 'AUTHENTICATED_ACTUAL_TABLE_WIRE', 'status': 'PASS',
                    'processing': processing, 'coverage': grouped_coverage},
                   {'check': 'MODEL_FACTS_REMAIN_UNVERIFIED', 'status': 'PASS',
                    'semantic_acceptance': False, 'development_only': True}],
        'reason_codes': [], 'identity_constraints': [], 'normalized_scope': {},
        'unresolved_scope_dimensions': spec['compiled']['scope_contract']['required_dimensions'],
        'system_approval_eligible': False}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK', **eb,
                                      'evidence_check_id': content_hash(value=eb)})
    rendered = render_text_review(compiled_spec=spec, candidate=candidate,
                                 evidence_check=evidence, source_bindings=bindings)
    context = {'compiled_spec': spec, 'candidate': candidate, 'evidence': evidence,
        'source_bindings': bindings, 'processing': processing, 'complete_table_grid': grid}
    cb = _bytes(context)
    rendered_bytes = ('# DEVELOPMENT ONLY: ' + origin + '\n').encode() + rendered['rendered_review_bytes']
    parent = build_review_unit(candidate=candidate, evidence_check=evidence,
        source_bindings=bindings, compiled_spec=spec, review_context_hash=sha256_bytes(content=cb),
        rendered_review_hash=sha256_bytes(content=rendered_bytes), renderer_semantic_version=POLICY)
    base = {'records': [asset, candidate, evidence, parent], 'processing': processing,
            'review_context_bytes': cb, 'rendered_review_bytes': rendered_bytes}
    linked = source_review_view(assessment=base, document=doc, raw_bytes=raw)
    display = linked['rendered_review_bytes'] + b'\n\n' + _layout_review(prepared['view'])
    unit = build_review_unit(candidate=candidate, evidence_check=evidence, source_bindings=bindings,
        compiled_spec=spec, review_context_hash=sha256_bytes(content=linked['review_context_bytes']),
        rendered_review_hash=sha256_bytes(content=display), renderer_semantic_version=POLICY+'_SOURCE_TABLE_REVIEW')
    return {'records': [grid, asset, candidate, evidence, parent, unit],
        'review_context_bytes': linked['review_context_bytes'], 'rendered_review_bytes': display,
        'processing': processing, 'request_body': request_body, 'response_body': response_body,
        'native_result_created': False, 'native_run_created': False, 'provider_attempt_created': False,
        'new_business_calls': [0, 0, 0]}


def _root(directory):
    path = Path(directory)
    _need(path.is_absolute(), 'ABSOLUTE_OUTPUT_REQUIRED')
    _need(first_symlink_in_path(path=path) is None, 'OUTPUT_ALIAS')
    path = path.resolve()
    ledger = Path(strict_json_file(path=ROOT/
        'config/issue28_continuous_calls_v1.json')['budget_root']).resolve()
    _need(path != ledger and ledger not in path.parents and path not in ledger.parents, 'LIVE_LEDGER_OUTPUT')
    _need(path != ROOT and ROOT not in path.parents and path not in ROOT.parents
          and not any((p/'outputs/active_publication.json').exists() for p in (path, *path.parents)),
          'OUTSIDE_CODE_AND_PUBLICATION_REQUIRED')
    return path


def save_table_development_assessment(*, directory, **arguments):
    root = _root(directory)
    data = Path(arguments['data_root']).resolve()
    _need(root != data and data not in root.parents and root not in data.parents,
          'SOURCE_OUTPUT_OVERLAP')
    out = build_table_development_assessment(**arguments)
    files = {'request-body.bin': out['request_body'], 'response.bin': out['response_body'],
        'processing/c02/table-metadata.json': _bytes(out['processing']),
        'review-context.json': out['review_context_bytes'], 'review.md': out['rendered_review_bytes'],
        'records.jsonl': b''.join(_bytes(r)+b'\n' for r in out['records'])}
    # Immutable resume reuses exact earlier bytes. Records are the final gate.
    for name, raw in files.items():
        target = root/name
        _need(first_symlink_in_path(path=target) is None, 'OUTPUT_ALIAS')
        write_immutable_bytes(path=target, content=raw)
    return out


def read_table_development_assessment(*, directory, data_root, company_id,
                                    expected_candidate_hash, expected_review_unit_hash):
    root = _root(directory)
    _need(not any(p.is_symlink() for p in root.rglob('*')), 'OUTPUT_ALIAS')
    meta = strict_json_loads(text=(root/'processing/c02/table-metadata.json').read_text())
    out = build_table_development_assessment(data_root=data_root, company_id=company_id,
        task_text=meta['task_text'], request_body=(root/'request-body.bin').read_bytes(),
        response_body=(root/'response.bin').read_bytes(), expected_request_sha256=meta['request_sha256'],
        expected_response_sha256=meta['response_sha256'], origin=meta['origin'])
    _need(out['records'][2]['candidate_hash'] == expected_candidate_hash
          and out['records'][5]['review_unit_hash'] == expected_review_unit_hash, 'EXPECTED_NATIVE_IDENTITIES')
    saved = [strict_json_loads(text=line) for line in (root/'records.jsonl').read_text().splitlines()]
    _need(out['records'] == saved and meta == out['processing']
          and out['review_context_bytes'] == (root/'review-context.json').read_bytes()
          and out['rendered_review_bytes'] == (root/'review.md').read_bytes(), 'SAVED_NATIVE_REPLAY_CHANGED')
    return out
