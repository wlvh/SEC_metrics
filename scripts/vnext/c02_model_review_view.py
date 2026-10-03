"""Source-linked semantic review view over unchanged C02 pending objects.

Model assertions and unresolved citations remain proposals. This explicit view
does not decide, normalize scope, create observations/Run, or grant live calls.
The original mapper and its saved pending identities remain byte-identical.
"""
import json
import re
from pathlib import Path

from .canonical import content_hash, sha256_bytes
from .c02_model_processing import ROOT, read_development_assessment
from .review import build_review_unit
from .text_business_candidates import governance_source_document

VERSION = 'C02_MODEL_SOURCE_LINKED_REVIEW_V1'


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode()


def _literal(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', str(value))


def source_review_view(*, assessment, document, raw_bytes):
    """Build the source display, including references unique to uncertainty."""
    meta = assessment['processing']
    asset, candidate, evidence, parent = assessment['records']
    _need(asset['tables'] == [meta] and parent['status'] == 'PENDING'
          and parent['system_approval_eligible'] is False,
          'C02_REVIEW_PARENT_PROCESSING_CHANGED')
    _need(sha256_bytes(content=raw_bytes) == meta['source_sha256']
          and document['source_reference_id'] == meta['source_reference_id'],
          'C02_REVIEW_ORIGINAL_SOURCE_CHANGED')
    model = meta['model_facts_and_unresolved']
    selected = list(candidate['selected'].items())
    citations, entries = {}, []
    for name, rows in (('FACT', model['facts']), ('UNRESOLVED', model['unresolved'])):
        for index, row in enumerate(rows):
            refs = []
            for i in row['source_blocks']:
                _need(type(i) is int and 0 <= i < len(document['blocks']),
                      'C02_REVIEW_REFERENCE_INVALID')
                b = document['blocks'][i]
                _need(b['block_index'] == i and sha256_bytes(content=raw_bytes[
                    b['raw_start_byte']:b['raw_end_byte']]) == b['raw_span_sha256'],
                    'C02_REVIEW_SOURCE_SPAN_CHANGED')
                owners = [role for role, claim in selected
                    if claim['source_reference_id'] == document['source_reference_id']
                    and claim['raw_start_byte'] <= b['raw_start_byte']
                    and b['raw_end_byte'] <= claim['raw_end_byte']]
                citations[i] = {**{k: b[k] for k in ('block_index', 'text',
                    'raw_start_byte', 'raw_end_byte', 'raw_span_sha256')},
                    'selected_excerpt_roles': owners}
                refs.append(i)
            entries.append({'entry_kind': name, 'entry_index': index,
                            'original_model_entry': row, 'source_blocks': refs})
    _need(entries, 'C02_REVIEW_EMPTY_SOURCE_DISPLAY')
    source_context = {'version': VERSION, 'parent_candidate_hash': candidate['candidate_hash'],
        'parent_review_unit_hash': parent['review_unit_hash'],
        'request_sha256': meta['request_sha256'], 'response_sha256': meta['response_sha256'],
        'source_sha256': meta['source_sha256'], 'source_reference_id': meta['source_reference_id'],
        'entries': entries, 'citations': [citations[i] for i in sorted(citations)],
        'semantic_acceptance': False, 'all_original_model_entries_preserved': True}
    context = json.loads(assessment['review_context_bytes'])
    context['source_linked_review'] = source_context
    context_bytes = _bytes(context)
    lines = ['# C02 development proposals: source-linked semantic review',
             'Pending only. No approval, verified observation, Result or Run.', '']
    for entry in entries:
        row = entry['original_model_entry']
        title = f"{entry['entry_kind']} {entry['entry_index']}"
        text = (f"{row['kind']}: {row['statement']}; time {row['stated_time']}"
                if entry['entry_kind'] == 'FACT' else row['reason'])
        lines += ['## ' + title, _literal(text),
                  'Source: ' + ', '.join(f'B{i}' for i in entry['source_blocks']), '']
    for i, citation in sorted(citations.items()):
        lines += [f'## B{i}',
                  'Candidate excerpts: ' + _literal(', '.join(citation['selected_excerpt_roles']) or
                    'none; uncertainty evidence only, no verified claim added'),
                  'Original span SHA256: ' + citation['raw_span_sha256'],
                  _literal(citation['text']), '']
    # The whole native ReviewUnit still owns every selected grouped excerpt,
    # including intervening context not itself cited by a model proposition.
    rendered = ('\n'.join(lines).encode() + b'\n\n# Original pending excerpts (unchanged)\n\n'
                + assessment['rendered_review_bytes'])
    compiled_spec = context['compiled_spec']
    unit = build_review_unit(candidate=candidate, evidence_check=evidence,
        source_bindings=context['source_bindings'], compiled_spec=compiled_spec,
        review_context_hash=sha256_bytes(content=context_bytes),
        rendered_review_hash=sha256_bytes(content=rendered), renderer_semantic_version=VERSION)
    _need(unit['status'] == 'PENDING' and unit['system_approval_eligible'] is False,
          'C02_REVIEW_VIEW_CREDIT_CHANGED')
    identity = {'version': VERSION, 'source_context': source_context,
                'review_context_sha256': sha256_bytes(content=context_bytes),
                'rendered_sha256': sha256_bytes(content=rendered),
                'review_unit_hash': unit['review_unit_hash']}
    return {'view_hash': content_hash(value=identity), 'identity': identity,
            'review_context_bytes': context_bytes, 'rendered_review_bytes': rendered,
            'review_unit': unit, 'native_result_or_run_created': False,
            'provider_credit': False, 'new_business_calls': [0, 0, 0]}


def build_development_review_view(*, parent_directory, data_root, company_id,
                                 expected_candidate_hash, expected_review_unit_hash):
    parent = read_development_assessment(directory=parent_directory, data_root=data_root,
        company_id=company_id, expected_candidate_hash=expected_candidate_hash,
        expected_review_unit_hash=expected_review_unit_hash)
    from .normal_run_v3 import prepare_case
    args = prepare_case(data_root=Path(data_root), company_id=company_id,
                        metric_id='C02')['text_arguments']
    meta = parent['processing']
    reference = next(r for r in args['source_references']
                     if r['source_reference_id'] == meta['source_reference_id'])
    raw = args['raw_bytes_by_id'][reference['raw_asset_id']]
    document = governance_source_document(raw_bytes=raw,
        raw_blob=args['raw_blobs'][reference['raw_asset_id']], source_reference=reference,
        company_id=company_id, cik=args['target']['entity'], filing=meta['source_filing'])
    return source_review_view(assessment=parent, document=document, raw_bytes=raw)


def read_development_review_view(*, directory, parent_directory, data_root, company_id,
                                expected_candidate_hash, expected_review_unit_hash,
                                expected_view_hash):
    """Rebuild all source links; a self-resealed view is not its own authority."""
    _need(type(expected_view_hash) is str and expected_view_hash,
          'C02_REVIEW_EXTERNAL_VIEW_ID_REQUIRED')
    folder = Path(directory)
    saved = json.loads((folder/'view.json').read_text())
    _need(type(saved) is dict and saved.get('view_hash') == expected_view_hash,
          'C02_REVIEW_EXPECTED_VIEW_ID_CHANGED')
    out = build_development_review_view(parent_directory=parent_directory,
        data_root=data_root, company_id=company_id,
        expected_candidate_hash=expected_candidate_hash,
        expected_review_unit_hash=expected_review_unit_hash)
    _need(out['view_hash'] == expected_view_hash,
          'C02_REVIEW_EXPECTED_VIEW_ID_CHANGED')
    _need(saved == {
              k: out[k] for k in ('view_hash', 'identity', 'review_unit',
                                  'native_result_or_run_created', 'provider_credit', 'new_business_calls')}
          and (folder/'context.json').read_bytes() == out['review_context_bytes']
          and (folder/'review.md').read_bytes() == out['rendered_review_bytes'],
          'C02_REVIEW_SAVED_VIEW_CHANGED')
    return out
