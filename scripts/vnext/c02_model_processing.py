"""Map a development model's C02 references into native pending review.

SEC source discovery/authentication is the existing ordinary input route.
Requests/responses are separate processing artifacts, never SEC sources or
fabricated provider attempts. This entry cannot make a Result, Run or decision.
The ordinary selector, default API and real invocation controller are unchanged.
"""
import json
import re
from pathlib import Path

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_loads
from .c02_grouped_source import grouped_governance_source
from .continuous_request_context import measure_request, _load_tokenizer
from .records import validate_record
from .review import build_review_unit
from .specs import compile_spec_file
from .text_business_candidates import governance_source_document, _excerpt
from .text_review import render_text_review

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = 'catalog/r6/C02_model_source_development_v1.md'
POLICY = 'C02_MODEL_SOURCE_REFERENCES_V1'
KINDS = {'board_size', 'board_membership', 'board_independence', 'board_leadership',
         'committee_structure', 'committee_membership', 'committee_independence',
         'member_qualification', 'membership_change'}


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _bytes(value):
    # Stable semantic hashing remains canonical; evidence strings remain exact.
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def _response(raw, document):
    value = strict_json_loads(text=raw.decode('utf-8'))
    _need(type(value) is dict and set(value) == {'facts', 'unresolved'}, 'C02_MODEL_RESPONSE_SHAPE')
    _need(type(value['facts']) is list and 0 < len(value['facts']) <= 64
          and type(value['unresolved']) is list, 'C02_MODEL_FACT_BOUND_NO_TRUNCATION')
    selected, seen = set(), set()
    for entries, fields in [(value['facts'], {'kind', 'statement', 'source_blocks', 'stated_time'}),
                            (value['unresolved'], {'source_blocks', 'reason'})]:
        for item in entries:
            _need(type(item) is dict and set(item) == fields, 'C02_MODEL_ENTRY_SHAPE')
            ids = item['source_blocks']
            _need(type(ids) is list and ids and all(type(i) is int for i in ids)
                  and len(ids) == len(set(ids))
                  and all(0 <= i < len(document['blocks']) for i in ids), 'C02_MODEL_REFERENCE_INVALID')
            _need(all(type(item[k]) is str and item[k].strip()
                      for k in fields - {'source_blocks'}), 'C02_MODEL_FIELD_INVALID')
            if 'kind' in item:
                _need(item['kind'] in KINDS, 'C02_MODEL_KIND_INVALID')
                key = (item['kind'], item['statement'], tuple(sorted(ids)), item['stated_time'])
                _need(key not in seen, 'C02_MODEL_DUPLICATE_FACT_NO_CLEANUP')
                seen.add(key)
                selected.update(ids)
    return value, sorted(selected)


def build_development_assessment(*, data_root, company_id, request_body,
                                 response_body, source_reference_id,
                                 expected_request_sha256, expected_response_sha256,
                                 origin='DEVELOPMENT_MODEL'):
    """Authenticate ordinary sources, then make mechanical native objects.

    Explicit external request/response digests prevent same-shape replacement.
    Semantics remain a proposal: no SYSTEM review or real-execution upgrade.
    """
    _need(origin == 'DEVELOPMENT_MODEL', 'C02_REAL_EXECUTION_NOT_AUTHORIZED')
    _need(type(request_body) is bytes and type(response_body) is bytes,
          'C02_MODEL_RAW_BYTES_REQUIRED')
    _need(sha256_bytes(content=request_body) == expected_request_sha256
          and sha256_bytes(content=response_body) == expected_response_sha256,
          'C02_MODEL_EXTERNAL_PROCESSING_IDENTITY_CHANGED')
    from .normal_run_v3 import prepare_case
    case = prepare_case(data_root=Path(data_root), company_id=company_id, metric_id='C02')
    args = case['text_arguments']
    source = next((s for s in args['source_references']
                   if s['source_reference_id'] == source_reference_id), None)
    _need(source is not None, 'C02_MODEL_SOURCE_NOT_IN_ORDINARY_INPUT')
    filing = args['source_filings'][source_reference_id]
    _need(filing['form'] in {'DEF 14A', '10-K/A'}, 'C02_MODEL_GOVERNANCE_SOURCE_REQUIRED')
    raw = args['raw_bytes_by_id'][source['raw_asset_id']]
    doc = governance_source_document(raw_bytes=raw,
        raw_blob=args['raw_blobs'][source['raw_asset_id']], source_reference=source,
        company_id=company_id, cik=args['target']['entity'], filing=filing)
    _need(doc['source_state'] == 'COMPLETE_LOCAL_DOCUMENT', 'C02_MODEL_COMPLETE_SOURCE_REQUIRED')
    text = '\n'.join('[B{}]\n{}\n'.format(i, b['text']) for i, b in enumerate(doc['blocks']))
    request = strict_json_loads(text=request_body.decode('utf-8'))
    measured = measure_request(request_body, require_reference=True)
    _need(measured['fits'] and request['messages'][1]['content'] == text,
          'C02_MODEL_REQUEST_SOURCE_OR_RESOURCE_CHANGED')
    tokenizer, _ = _load_tokenizer()
    _need(len(tokenizer.encode(response_body.decode('utf-8'), add_special_tokens=False).ids) <= 4096,
          'C02_MODEL_RESPONSE_OUTPUT_LIMIT')
    facts, selected = _response(response_body, doc)
    coverage = {'document_id': doc['text_document_id'],
                'source_reference_id': source_reference_id,
                'scope': 'COMPLETE_MODEL_INPUT_NOT_SEMANTIC_ABSENCE'}
    coverage['coverage_hash'] = content_hash(value=coverage)
    proposal = {'document_id': doc['text_document_id'],
        'source_reference_id': source_reference_id,
        'candidates': [_excerpt(doc, doc['blocks'][i], 'GOVERNANCE_DISCLOSURES',
                        ['DEVELOPMENT_MODEL_REFERENCE']) for i in selected]}
    proposal['proposal_id'] = content_hash(value=proposal)
    _, grouped, grouped_coverage = grouped_governance_source(document=doc,
        proposal=proposal, coverage=coverage, raw_bytes=raw)
    quotes = grouped['candidates']
    _need(len(quotes) <= 64 and sum(len(q['text']) for q in quotes) <= 64000,
          'C02_MODEL_COMPLETE_QUOTATION_LIMIT')
    spec = compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})
    _need(spec['compiled']['disclosure_group'] == 'c02_model_source_development_v1'
          and spec['compiled']['quality_rule'] == {'model_development_method': POLICY},
          'C02_MODEL_DRAFT_SPEC_CHANGED')
    processing = {'origin': origin, 'policy': POLICY, 'request_sha256': expected_request_sha256,
        'response_sha256': expected_response_sha256, 'source_sha256': sha256_bytes(content=raw),
        'spec_closure_hash': spec['spec_closure_hash'], 'mapper_sha256': sha256_file(path=Path(__file__)),
        'request_context': measured, 'model_facts_and_unresolved': facts,
        'ordinary_source_admission': case['admission'], 'annual_target': args['target'],
        'source_filing': filing, 'source_reference_id': source_reference_id,
        'complete_source_partition_hash': grouped_coverage['complete_source_partition_hash']}
    asset_body = {'parent_raw_asset_ids': [source['raw_asset_id']], 'transform_id': POLICY,
        'transform_semantic_version': '1', 'content_type': 'application/json', 'tables': [processing]}
    asset = validate_record(record={'record_type': 'DERIVED_ASSET', **asset_body,
        'derived_asset_id': content_hash(value=asset_body), 'storage_uri': 'processing/c02/metadata.json'})
    claims = {'excerpt_{:06d}'.format(i): {'value_kind': 'TEXT_V1', 'extent': 'FULL_BLOCK',
        'order': i, **{k: q[k] for k in ('text', 'source_reference_id', 'document_id',
            'section_id', 'block_index', 'raw_start_byte', 'raw_end_byte', 'raw_span_sha256')}}
        for i, q in enumerate(quotes)}
    # All observations are source quotes; semantic model statements live in the
    # processing asset and rendered pending context, not verified quantities.
    body = {'disclosure_group': spec['compiled']['disclosure_group'],
        'source_reference_ids': [s['source_reference_id'] for s in args['source_references']],
        'derived_asset_ids': [asset['derived_asset_id']], 'selected': claims,
        'competing_candidates': [], 'unresolved_competing_claims': facts['unresolved']}
    candidate = validate_record(record={'record_type': 'OBSERVATION_CANDIDATE', **body,
        'candidate_hash': content_hash(value=body), 'status': 'REVIEW_REQUIRED',
        'attempt_id': 'development:c02:' + expected_response_sha256,
        'assistant_output_sha256': expected_response_sha256})
    evidence_body = {'candidate_hash': candidate['candidate_hash'], 'status': 'PASS',
        'normalized_values': claims, 'checks': [{'check': 'ORIGINAL_BYTES_AND_COMPLETE_INPUT',
            'status': 'PASS', 'processing': processing, 'coverage': grouped_coverage},
            {'check': 'MODEL_FACTS_REMAIN_UNVERIFIED', 'status': 'PASS',
             'development_only': True, 'semantic_acceptance': False}],
        'reason_codes': [], 'identity_constraints': [], 'normalized_scope': {},
        'unresolved_scope_dimensions': spec['compiled']['scope_contract']['required_dimensions'],
        'system_approval_eligible': False}
    evidence = validate_record(record={'record_type': 'EVIDENCE_CHECK', **evidence_body,
        'evidence_check_id': content_hash(value=evidence_body)})
    rendered = render_text_review(compiled_spec=spec, candidate=candidate,
        evidence_check=evidence, source_bindings=args['source_references'])
    context = {'compiled_spec': spec, 'candidate': candidate, 'evidence': evidence,
               'source_bindings': args['source_references'], 'processing': processing}
    context_bytes = _bytes(context)
    literal = lambda value: re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', str(value))
    supplement = ['# DEVELOPMENT MODEL ONLY: pending semantic review', ''] + [
        literal(f['kind']) + ': ' + literal(f['statement']) + '; time ' + literal(f['stated_time'])
        for f in facts['facts']]
    rendered_bytes = '\n'.join(supplement).encode() + b'\n\n' + rendered['rendered_review_bytes']
    unit = build_review_unit(candidate=candidate, evidence_check=evidence,
        source_bindings=args['source_references'], compiled_spec=spec,
        review_context_hash=sha256_bytes(content=context_bytes),
        rendered_review_hash=sha256_bytes(content=rendered_bytes), renderer_semantic_version=POLICY)
    return {'records': [asset, candidate, evidence, unit], 'review_context_bytes': context_bytes,
        'rendered_review_bytes': rendered_bytes, 'processing': processing,
        'native_result_created': False, 'native_run_created': False,
        'provider_attempt_created': False, 'new_business_calls': [0, 0, 0]}


def read_development_assessment(*, directory, data_root, company_id,
                                expected_candidate_hash, expected_review_unit_hash):
    """Rebuild saved pending objects from original sources and exact raw wire.

    External expected native identities are required; a package's self-hash is
    not authority to substitute another answer. No saved decision is consumed.
    """
    folder = Path(directory)
    saved = [strict_json_loads(text=line) for line in (folder / 'records.jsonl').read_text().splitlines()]
    _need(len(saved) == 4, 'C02_MODEL_SAVED_RECORD_SET_CHANGED')
    asset, candidate, evidence, unit = [validate_record(record=r) for r in saved]
    _need([r['record_type'] for r in saved] ==
          ['DERIVED_ASSET', 'OBSERVATION_CANDIDATE', 'EVIDENCE_CHECK', 'REVIEW_UNIT'],
          'C02_MODEL_SAVED_RECORD_TYPES_CHANGED')
    _need(candidate['candidate_hash'] == expected_candidate_hash
          and unit['review_unit_hash'] == expected_review_unit_hash,
          'C02_MODEL_EXPECTED_NATIVE_IDENTITIES_CHANGED')
    meta = strict_json_loads(text=(folder / 'processing/c02/metadata.json').read_text())
    _need(asset['tables'] == [meta], 'C02_MODEL_SAVED_PROCESSING_CHANGED')
    out = build_development_assessment(data_root=data_root, company_id=company_id,
        request_body=(folder / 'request-body.bin').read_bytes(),
        response_body=(folder / 'response.bin').read_bytes(),
        source_reference_id=meta['source_reference_id'],
        expected_request_sha256=meta['request_sha256'], expected_response_sha256=meta['response_sha256'],
        origin=meta['origin'])
    _need(out['records'] == saved
          and out['review_context_bytes'] == (folder / 'review-context.json').read_bytes()
          and out['rendered_review_bytes'] == (folder / 'review.md').read_bytes(),
          'C02_MODEL_SAVED_NATIVE_REPLAY_CHANGED')
    return out
