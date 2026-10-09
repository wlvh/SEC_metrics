"""Read the existing historical SEC count without creating or rewriting state.

This is the old SEC record format's reader, not an allowance factory. Original
intents, receipts, the additive extension and conservative resume counts remain
separate. A caller still needs the bounded purpose before any capture.
"""
from pathlib import Path

from sec_http import parse_request_log_rows, validate_request_log_manifest
from .canonical import sha256_bytes, strict_json_file, strict_json_loads


def _need(condition, reason):
    if not condition:
        raise ValueError('EXISTING_HISTORICAL_SEC_' + reason)


def _lines(path):
    return [strict_json_loads(text=line) for line in path.read_text().splitlines()]


def inspect_existing_historical_sec(root):
    """Reconcile existing count, terminal/log relationships and effective cap.

    No lock or file is created. Live claim/capture must repeat the checks under
    the same original ledger lock; this read-only view grants no request.
    """
    root = Path(root).resolve()
    _need(root.is_dir(), 'ROOT_MISSING')
    binding = strict_json_file(path=root/'binding.json')
    _need(binding.get('record_type') == 'ISSUE_47_HISTORICAL_CALL_ALLOWANCE'
          and binding.get('limits', [])[:2] == [0, 0], 'FORMAT_UNSUPPORTED')
    claims_path = root/'claims.jsonl'
    claims_bytes = claims_path.read_bytes()
    claims = _lines(claims_path)
    source_root = root/'source-inputs'
    log = source_root/'evidence/requests_log.csv'
    validate_request_log_manifest(log_path=log)
    source_rows = parse_request_log_rows(text=log.read_text())
    slots = sorted((root/'calls').iterdir())
    _need([p.name for p in slots] == ['%04d' % (i+1) for i in range(len(claims))],
          'CLAIM_SLOT_SET_DIFFERS')
    previous = None; digests = set(); blocked = []; rows = []
    for slot, claim in zip(slots, claims):
        intent = strict_json_file(path=slot/'intent.json')
        _need(intent == claim and intent.get('record_type') == 'ISSUE_47_HISTORICAL_CALL_INTENT'
              and intent['allowance_binding_id'] == binding['binding_id']
              and intent['requirement_id'] == binding['requirement_id']
              and intent['execution_mode'] == binding['execution_mode']
              and intent['channel'] == 'SEC' and intent['ordinal'] == int(slot.name)
              and intent['previous_intent_id'] == previous, 'INTENT_RELATION_DIFFERS')
        _need(intent['request_digest'] not in digests, 'REPEATED_REQUEST')
        previous = intent['intent_id']; digests.add(intent['request_digest'])
        terminal = strict_json_file(path=slot/'terminal.json') if (slot/'terminal.json').is_file() else None
        receipt = strict_json_file(path=slot/'sec-receipt.json') if (slot/'sec-receipt.json').is_file() else None
        reason = None
        if terminal is None or receipt is None:
            reason = 'INCOMPLETE_ATTEMPT'
        elif (terminal['intent_id'] != intent['intent_id'] or receipt['intent_id'] != intent['intent_id']
              or terminal['sec_receipt_id'] != receipt['receipt_id']
              or terminal['execution_mode'] != binding['execution_mode']
              or receipt['execution_mode'] != binding['execution_mode']):
            reason = 'TERMINAL_RECEIPT_RELATION_DIFFERS'
        elif terminal['status'] not in {'SUCCEEDED', 'FAILED_TERMINAL'} or terminal.get('stop_reason'):
            reason = terminal.get('stop_reason') or 'UNKNOWN_OUTCOME'
        else:
            index = receipt['ledger_row_index']
            _need(type(index) is int and 0 <= index < len(source_rows)
                  and source_rows[index] == receipt['ledger_row'], 'RECEIPT_LOG_ROW_DIFFERS')
            row = source_rows[index]
            expected = 'SUCCEEDED' if row['status_code'] == '200' and not row['error'] else 'FAILED_TERMINAL'
            _need(row['status_code'] != '0' and receipt['status'] == terminal['status'] == expected,
                  'LOGGED_OUTCOME_DIFFERS')
        if reason: blocked.append({'ordinal': intent['ordinal'], 'reason': reason})
        rows.append({'ordinal': intent['ordinal'], 'status': None if terminal is None else terminal['status'],
                     'request_digest': intent['request_digest']})
    limit = binding['limits'][2]
    for path in sorted(root.parent.glob('.'+root.name+'.extension-*.json')):
        extension = strict_json_file(path=path); state = extension['ledger_state']; prefix = state['claims']
        size = prefix['size']
        _need(type(size) is int and size >= 0 and len(claims_bytes) >= size
              and sha256_bytes(content=claims_bytes[:size]) == prefix['sha256']
              and claims_bytes[:size].count(b'\n') == state['claim_count'], 'EXTENSION_PREFIX_DIFFERS')
        delta = extension['maximum_additional_provider_paid_sec_calls']
        _need(type(delta) is list and len(delta) == 3 and delta[:2] == [0, 0]
              and type(delta[2]) is int and delta[2] >= 0, 'EXTENSION_LIMIT_INVALID')
        limit += delta[2]
    resume_path = root.parent/('.'+root.name+'.resumes.jsonl')
    resumes = _lines(resume_path) if resume_path.is_file() else []
    reserve = 0
    for resume in resumes:
        charge = resume['lost_segment']['reserve_sec_calls']
        _need(resume['record_type'] == 'ISSUE_47_SEC_LEDGER_RESUME'
              and type(charge) is int and charge >= 0, 'RESUME_CHARGE_INVALID')
        reserve += charge
    bounded = resumes[-1].get('bounded_capture') if resumes else None
    if resumes:
        _need(resumes[-1].get('runtime_ledger_root', resumes[-1]['budget_root']) == str(root),
              'RESUME_LOCATION_DIFFERS')
    return {'binding': binding, 'counts': [0, 0, len(claims)+reserve], 'limits': [0, 0, limit],
            'claim_count': len(claims), 'conservative_sec_charge': reserve,
            'blocked': blocked, 'rows': rows, 'bounded_capture': bounded,
            'source_root': str(source_root), 'request_log_row_count': len(source_rows),
            'claims_sha256': sha256_bytes(content=claims_bytes), 'new_calls': {'provider':0, 'paid':0, 'sec':0},
            'capture_authorized_by_this_view': False}
