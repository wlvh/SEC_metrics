"""Read one retained D02 Item 8 answer for its exact current request.

This does not call a model, alter the old ledger, write a Run or establish a
whole-company litigation result. Source preparation and complete aggregation
remain the consumer's responsibilities.
"""
from pathlib import Path, PurePosixPath

from scripts.securegpt_sdk import assistant_content, response_usage
from .canonical import content_hash, sha256_bytes, strict_json_loads
from . import legal_review_contract as contract

PROCESSING_FILES=(
    'scripts/vnext/saved_legal_review.py',
    'scripts/vnext/legal_review_contract.py',
    'scripts/securegpt_sdk.py',
    'scripts/vnext/canonical.py',
)


def _need(condition, reason):
    if not condition:
        raise ValueError('SAVED_LEGAL_REVIEW_'+reason)


def read_saved_legal_review(*, call_root, request):
    """Read the old call's seven files, retaining original execution identity.

    ``request`` must come from the consumer's actual source preparation, not
    from a quote-only regression projection or a saved answer. Unknown token
    usage remains unknown; an empty subreview is never a complete D02 result.
    """
    root=Path(call_root)
    _need(request.get('record_type')==contract.REQUEST_TYPE
          and request.get('contract')==contract.CONTRACT, 'CONTRACT_NOT_SUPPORTED')
    _need(request.get('request_id')==content_hash(value={
        k:v for k,v in request.items() if k!='request_id'}), 'REQUEST_ID_CHANGED')
    terminal=strict_json_loads(text=(root/'terminal.json').read_text())
    _need(terminal.get('status')=='SUCCEEDED', 'ORIGINAL_EXECUTION_NOT_SUCCEEDED')
    evidence=terminal['evidence']
    def read(name):
        raw=(root/name).read_bytes()
        _need(evidence.get(name)==sha256_bytes(content=raw), 'BYTES_CHANGED:'+name)
        return raw
    saved_request=strict_json_loads(text=read('semantic-request.json').decode('utf-8'))
    source=strict_json_loads(text=read('source.json').decode('utf-8'))
    _need(saved_request==request and source.get('request')==request,
          'CURRENT_REQUEST_DIFFERS_FROM_SAVED_REQUEST')
    _need(source.get('company_id')==request['company_id']
          and source.get('metric_id')=='D02', 'SOURCE_COORDINATE_CHANGED')
    provider_paths=[p for p in evidence if p.startswith('invocation_control/requests/')
                    and p.endswith('.bin')]
    _need(len(provider_paths)==1, 'PROVIDER_REQUEST_AMBIGUOUS')
    provider_path=provider_paths[0]
    _need('..' not in PurePosixPath(provider_path).parts, 'PROVIDER_REQUEST_PATH_INVALID')
    provider_raw=read(provider_path)
    provider=strict_json_loads(text=provider_raw.decode('utf-8'))
    _need(provider.get('messages')==contract.provider_messages(request),
          'PROVIDER_MESSAGES_DIFFER')
    journal=strict_json_loads(text=read('wire/journal.json').decode('utf-8'))
    _need(journal.get('status_code')==200 and not journal.get('error_class')
          and journal.get('request_sha256')==sha256_bytes(content=provider_raw)
          and journal.get('intent_id')==terminal.get('intent_id'), 'WIRE_EXECUTION_DIFFERS')
    raw_response=read('wire/raw-response.bin')
    answer=read('wire/assistant-output.bin')
    _need(journal.get('raw_response_sha256')==sha256_bytes(content=raw_response)
          and journal.get('assistant_output_sha256')==sha256_bytes(content=answer),
          'WIRE_CONTENT_DIFFERS')
    response=strict_json_loads(text=raw_response.decode('utf-8'))
    _need(type(response.get('choices')) is list and len(response['choices'])==1
          and response['choices'][0].get('finish_reason')=='stop', 'RESPONSE_NOT_COMPLETE')
    _need(response.get('id')==journal.get('provider_request_id'), 'PROVIDER_RESPONSE_DIFFERS')
    _need(assistant_content(response).encode('utf-8')==answer, 'ASSISTANT_OUTPUT_DIFFERS')
    decisions,added=contract.validate_answer(request=request,raw_output=answer)
    included,reason,unsettled=contract.reviewed_blocks(request=request,decisions=decisions,added=added)
    usage=response_usage(response)
    for name in ('input_tokens','output_tokens'):
        previous=(journal.get('usage') or {}).get(name)
        _need(usage[name] is None or previous is None or usage[name]==previous,
              'TOKEN_USAGE_DIFFERS:'+name)
    known_usage=all(usage[name] is not None for name in ('input_tokens','output_tokens'))
    return {'record_type':'SAVED_D02_ITEM8_REVIEW_READ',
        'request_id':request['request_id'],'source_id':request['source_id'],
        'company_id':request['company_id'],'target_cik':request['target_cik'],
        'period_end':request['period_end'],'filing':request['filing'],
        'call_root':str(root),'source_proofs':source['source_proofs'],
        'decisions':decisions,'also_in_scope':added,'included_block_ids':included,
        'withheld_reason':reason,'unsettled_block_ids':unsettled,
        'original_execution_mode':journal['mode'],'original_terminal_id':terminal['terminal_id'],
        'original_execution_id':journal['execution_id'],'original_wire_id':journal['wire_id'],
        'original_counts':terminal['counts'],'original_counts_kind':terminal['counts_kind'],
        'provider_parameters':{k:v for k,v in provider.items() if k!='messages'},
        'usage':usage,'usage_known':known_usage,
        'response_form_valid':True,'semantic_correctness_verified':False,
        'current_source_verified':False,
        'complete_company_result':False,'new_calls':{'provider':0,'paid':0,'sec':0},
        'run_created':False,'production_authorized':False}
