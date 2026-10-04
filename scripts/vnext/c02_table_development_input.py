"""Explicit ordinary-source C02 development input; no extraction or acceptance.

The received formatter is fixed at the provider commit. Source admission and
the table parser stay on this route's own implementation and identities.
"""
import hashlib
from pathlib import Path

from .c02_table_context_417ccfb7 import FORMAT, model_view, wire
from .continuous_request_context import measure_request
from .normal_text_input_v2 import prepare_normal_business_text_input
from .table_grid import build_table_grid
from .text_business_candidates import governance_source_document


def _need(ok, reason):
    if not ok:
        raise ValueError('C02_ORDINARY_TABLE_INPUT_' + reason)


def development_request(*, document, derived, target, task_text):
    """Render the complete input; callers must separately authenticate sources."""
    _need(type(task_text) is str and task_text.strip(), 'TASK_REQUIRED')
    _need(document['source_state'] == 'COMPLETE_LOCAL_DOCUMENT', 'INCOMPLETE_SOURCE')
    view = model_view(document, derived)
    filing = document['source_filing']
    prompt = (
        'You receive all visible blocks and all HTML table text/header grids of '
        + ', '.join(document['registrant_names']) + ', ' + filing['form']
        + ' filed ' + filing['filingDate'] + ', accession ' + filing['accessionNumber']
        + '. The associated annual reporting interval is '
        + target['period_start'] + ' through ' + target['period_end']
        + ', not a board measurement at the interval end.\n\n'
        + task_text + FORMAT)
    request = {'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': wire(view).decode('utf-8')}],
        'response_format': {'type': 'json_object'}, 'temperature': 0,
        'max_tokens': 4096, 'stream': False, 'thinking': {'type': 'disabled'}}
    body = wire(request)
    measurement = measure_request(body, require_reference=True)
    # A complete over-limit input remains inspectable. Nothing is trimmed,
    # transmitted, or represented as accepted just because rendering succeeded.
    return {'view': view, 'request_body': body, 'measurement': measurement}


def prepare_ordinary_table_development_input(*, data_root, company_id, task_text):
    """Use the ordinary saved-source admission without changing its defaults."""
    prepared = prepare_normal_business_text_input(
        repo_root=Path(data_root), company_id=company_id, metric_id='C02')
    args = prepared['text_arguments']
    _need(args is not None, 'SOURCE_PREPARATION_BLOCKED')
    sources = [s for s in args['source_references']
               if args['source_filings'][s['source_reference_id']]['form']
               in {'DEF 14A', '10-K/A'}]
    _need(len(sources) == 1, 'GOVERNANCE_SOURCE_NOT_UNIQUE')
    source, = sources
    raw = args['raw_bytes_by_id'][source['raw_asset_id']]
    doc = governance_source_document(
        raw_bytes=raw, raw_blob=args['raw_blobs'][source['raw_asset_id']],
        source_reference=source, company_id=company_id,
        cik=args['target']['entity'],
        filing=args['source_filings'][source['source_reference_id']])
    for block in doc['blocks']:
        span = raw[block['raw_start_byte']:block['raw_end_byte']]
        _need(hashlib.sha256(span).hexdigest() == block['raw_span_sha256'],
              'BLOCK_RAW_SPAN_CHANGED')
    grid = build_table_grid(html_bytes=raw, parent_raw_asset_ids=[doc['raw_asset_id']],
                           storage_uri='development/c02-complete-table-grid.json')
    rendered = development_request(document=doc, derived=grid,
                                   target=args['target'], task_text=task_text)
    return {**rendered, 'document': doc, 'table_grid': grid, 'raw_source': raw,
            'input_binding': prepared['input_binding'],
            'source_reference': source,
            'raw_blob': args['raw_blobs'][source['raw_asset_id']],
            'business_calls': [0, 0, 0], 'model_answer_tested': False,
            'result_created': False, 'production_authorized': False}
