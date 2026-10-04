"""Prepare a development question while preserving a native navigation refusal.

The normal source adapter must authenticate the filing first. This helper then
retains the incomplete proposal and asks the existing review contract about
every block in its single Item 8 range. It does not make the native preparation
pass, map nonmatching captions, register a review, create a Run, or call a model.
The expanded pool is explicitly different from the normal runtime review pool.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(root, name, value):
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--report-end', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root / 'scripts'))
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import (
        _D02_PREPARATION, narrow_document_sections, referenced_note_candidates)
    from vnext.historical_legal_review import review_request
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    from vnext.continuous_request_context import measure_request
    from vnext.continuous_semantic_calls import request_body
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy

    with checkpoint_replayed_once():
        selection = resolve_period_selection(repo_root=args.source_root,
                                             company_id=args.company,
                                             report_end=args.report_end)
        source = prepare_historical_business_text_input(
            repo_root=args.source_root, company_id=args.company, metric_id='D02',
            period_selection=selection, _without_reviews=True)
        assert source['text_arguments'] is not None
        # This is the source preparation preceding the historical navigation
        # gate. Its output does not confer success on the corrected proposal.
        base = _D02_PREPARATION(metric_id='D02', **source['text_arguments'])
    assert len(base['documents']) == 1
    document = narrow_document_sections(document=next(iter(base['documents'].values())))
    raw = source['text_arguments']['raw_bytes_by_id'][document['raw_asset_id']]
    assert 'sha256:' + sha(raw) == document['raw_asset_id']
    for block in document['blocks']:
        assert sha(raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
    proposal = referenced_note_candidates(document=document, raw_bytes=raw)
    assert proposal['coverage_status'] == 'INCOMPLETE'
    assert proposal['coverage_reasons']
    ranges = [r for r in proposal['checked_ranges'] if r['section_id'] == 'ITEM_8']
    assert len(ranges) == 1
    scope = ranges[0]
    # Every original block, including captions, short cells, page furniture
    # and the auditor report. Definition decides relevance in a future answer;
    # the development source is not narrowed by a legal keyword.
    pool = list(range(scope['start_block'], scope['end_block_exclusive']))
    request = review_request(company_id=args.company,
                             target_cik=source['text_arguments']['target']['entity'],
                             period_end=args.report_end, document=document,
                             pool=pool, keyword_admitted=[])
    dry_path = args.code_root / 'docs/evidence/issue47_history/model-egress/dev-dry-run/dump_requests.py'
    spec = importlib.util.spec_from_file_location('issue47_fixed_transport_fields', dry_path)
    dry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dry)
    policy = TransportPolicy.from_mapping(value={**dry.TRANSPORT_FIELDS,
                                                 'endpoint_host': _DEEPSEEK_ENDPOINT_HOST})
    body = request_body(request, policy)
    measurement = measure_request(body)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'request-body.json').write_bytes(body)
    save(args.out, 'request.json', request)
    save(args.out, 'context-measurement.json', measurement)
    save(args.out, 'document.json', document)
    save(args.out, 'incomplete-proposal.json', proposal)
    # Portable proofs retain their actual fields, without raw byte mappings.
    source_fields = {key: value for key, value in source.items()
                     if key != 'text_arguments'}
    save(args.out, 'authenticated-source-preparation.json', source_fields)
    metadata = {
        'record_type': 'ISSUE47_INCOMPLETE_NAVIGATION_FULL_ITEM8_DEVELOPMENT_INPUT',
        'position': args.company + ':' + args.report_end,
        'raw_asset_id': document['raw_asset_id'],
        'source_reference_id': document['source_reference_id'],
        'source_reference': document['source_reference'],
        'all_document_raw_spans_verified': len(document['blocks']),
        'complete_item8_blocks': len(pool), 'item8_range': scope,
        'must_decide_count': len(request['must_decide']),
        'existing_contract': request['contract'],
        'request_sha256': sha(body), 'request_id': request['request_id'],
        'normal_navigation_status': proposal['coverage_status'],
        'normal_navigation_reasons': proposal['coverage_reasons'],
        'normal_runtime_review_pool_reproduced': False,
        'pool_policy': 'ALL_ORIGINAL_BLOCKS_IN_THE_ONE_LOCATED_ITEM8_RANGE',
        'source_table_grid_included': False,
        'source_images_interpreted': False,
        'complete_metric_semantic_reference_frozen': False,
        'method_independently_validated': False,
        'runtime_wired': False, 'registration_authorized': False,
        'production_authorized': False, 'provider_request_sent': False,
        'new_runs': 0, 'new_acceptances': 0, 'calls': [0, 0, 0],
        'executed_module_files': [
            {'path': str(Path(m.__file__)), 'sha256': sha(Path(m.__file__).read_bytes())}
            for m in [sys.modules['vnext.historical_text_input'],
                      sys.modules['vnext.historical_text_results'],
                      sys.modules['vnext.historical_legal_review'],
                      sys.modules['vnext.continuous_semantic_calls'],
                      sys.modules['vnext.continuous_request_context']]],
    }
    save(args.out, 'metadata.json', metadata)
    print(json.dumps({'blocks': len(pool), 'must_decide': len(request['must_decide']),
                      'input_tokens': measurement['input_tokens'],
                      'context_tokens': measurement['context_tokens'],
                      'fits': measurement['fits'], 'request_sha256': sha(body),
                      'native_navigation_status': proposal['coverage_status'],
                      'calls': [0, 0, 0]}), flush=True)


if __name__ == '__main__':
    main()
