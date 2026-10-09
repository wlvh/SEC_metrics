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
          and type(binding.get('limits')) is list and len(binding['limits']) == 3
          and all(type(value) is int and value >= 0 for value in binding['limits'])
          and binding['limits'][:2] == [0, 0], 'FORMAT_UNSUPPORTED')
    claims_path = root/'claims.jsonl'
    claims_bytes = claims_path.read_bytes()
    mirror = root.parent/('.'+root.name+'.claims.jsonl')
    _need(mirror.is_file() and mirror.read_bytes() == claims_bytes, 'CLAIM_MIRROR_DIFFERS')
    claims = _lines(claims_path)
    source_root = root/'source-inputs'
    log = source_root/'evidence/requests_log.csv'
    validate_request_log_manifest(log_path=log)
    source_rows = parse_request_log_rows(text=log.read_text())
    slots = sorted((root/'calls').iterdir())
    _need([p.name for p in slots] == ['%04d' % (i+1) for i in range(len(claims))],
          'CLAIM_SLOT_SET_DIFFERS')
    previous = None; digests = set(); blocked = []; rows = []; first_row_index = None
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
            if first_row_index is None: first_row_index = index
            _need(index == first_row_index + intent['ordinal'] - 1, 'RECEIPT_LOG_SEQUENCE_DIFFERS')
            row = source_rows[index]
            expected = 'SUCCEEDED' if row['status_code'] == '200' and not row['error'] else 'FAILED_TERMINAL'
            _need(row['status_code'] != '0' and receipt['status'] == terminal['status'] == expected,
                  'LOGGED_OUTCOME_DIFFERS')
        if reason: blocked.append({'ordinal': intent['ordinal'], 'reason': reason})
        rows.append({'ordinal': intent['ordinal'], 'channel': 'SEC',
                     'status': None if terminal is None else terminal['status'],
                     'request_digest': intent['request_digest'], 'intent_id': intent['intent_id']})
    if not blocked and first_row_index is not None:
        _need(len(source_rows) == first_row_index + len(claims), 'UNOWNED_LOG_TAIL')
    limit = binding['limits'][2]
    for path in sorted(root.parent.glob('.'+root.name+'.extension-*.json')):
        extension = strict_json_file(path=path); state = extension['ledger_state']; prefix = state['claims']
        _need(type(extension.get('extension_ordinal')) is int and extension['extension_ordinal'] > 0
              and path.name == '.'+root.name+'.extension-'+str(extension['extension_ordinal'])+'.json',
              'EXTENSION_ORDINAL_INVALID')
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
              and resume.get('budget_root') == resumes[-1].get('budget_root')
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


class ExistingHistoricalSecLedger:
    """One bounded SEC purpose on an already initialized historical ledger.

    Keeps its original intent/terminal formats so the saved reader can still
    account for appended slots. No ledger initialization or permission minting.
    """
    def __init__(self, *, root, context):
        self.root = Path(root).resolve()
        self.context = dict(context)
        self._locked = False
        state = inspect_existing_historical_sec(self.root)
        self.binding = state['binding']
        self.live = self.binding['execution_mode'] == 'LIVE'
        self.source_root = Path(state['source_root'])
        self.bounded_capture = dict(state['bounded_capture']) if type(state['bounded_capture']) is dict else None
        self._check_purpose(state)

    def _check_purpose(self, state):
        purpose = state['bounded_capture']
        _need(purpose == self.bounded_capture, 'BOUNDED_PURPOSE_CHANGED')
        _need(type(purpose) is dict and purpose.get('maximum_additional_sec_calls') == 1
              and purpose.get('retry_count') == 0, 'BOUNDED_PURPOSE_REQUIRED')
        before, maximum = purpose['counts_before'], purpose['maximum_counts']
        _need(type(before) is list and type(maximum) is list and len(before) == len(maximum) == 3
              and all(type(n) is int and n >= 0 for n in before+maximum)
              and maximum == [before[0], before[1], before[2]+1], 'BOUNDED_COUNTS_INVALID')
        _need(self.context['company_id'] == purpose['company_id']
              and self.context['maximum_counts'] == maximum
              and self.context['execution_mode'] == self.binding['execution_mode']
              and self.context['purpose'] in self.binding['purposes']
              and self.context['requirement_id'] == self.binding['requirement_id'], 'CONTEXT_SCOPE_DIFFERS')
        _need(all(a <= b for a,b in zip(maximum,state['limits'])), 'BOUND_EXCEEDS_EXISTING_LIMIT')
        return purpose

    def locked(self):
        from contextlib import contextmanager
        import fcntl
        import os
        @contextmanager
        def hold():
            _need(not self._locked, 'ALREADY_LOCKED')
            handle = os.open(self.root, os.O_RDONLY)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX); self._locked = True
                yield self
            finally:
                self._locked = False
                fcntl.flock(handle, fcntl.LOCK_UN); os.close(handle)
        return hold()

    def snapshot(self):
        state = inspect_existing_historical_sec(self.root)
        _need(state['binding'] == self.binding, 'BINDING_CHANGED')
        self._check_purpose(state)
        return state

    def check_request(self, *, source, url, refresh):
        purpose = self._check_purpose(self.snapshot())
        _need(Path(source).resolve() == self.source_root and url == purpose['source_url']
              and refresh is False, 'REQUEST_OUTSIDE_BOUNDED_PURPOSE')
        _need(not self.snapshot()['blocked'], 'UNRESOLVED_ATTEMPT')

    def _write_new(self, path, value):
        from .invocation_control import _exclusive_write_json
        _exclusive_write_json(path=path, value=value)

    def claim(self, *, channel, request_digest, requirement, plan_id, purpose):
        import os
        from .canonical import canonical_json_bytes, content_hash
        _need(self._locked and channel == 'SEC', 'LOCKED_SEC_CLAIM_REQUIRED')
        state = self.snapshot(); bounded = self._check_purpose(state)
        _need(not state['blocked'], 'UNRESOLVED_ATTEMPT')
        _need(state['counts'] == bounded['counts_before'], 'BOUNDED_OPPORTUNITY_CONSUMED')
        _need(purpose in self.binding['purposes'] and requirement['requirement_id'] == self.binding['requirement_id'],
              'CLAIM_SCOPE_DIFFERS')
        _need(request_digest not in {row['request_digest'] for row in state['rows']}, 'REPEATED_REQUEST')
        ordinal = state['claim_count'] + 1
        body = {'record_type':'ISSUE_47_HISTORICAL_CALL_INTENT','requirement_id':self.binding['requirement_id'],
                'channel':'SEC','ordinal':ordinal,'execution_mode':self.binding['execution_mode'],
                'allowance_binding_id':self.binding['binding_id'],
                'previous_intent_id':state['rows'][-1]['intent_id'] if state['rows'] else None,
                'request_digest':request_digest,'plan_id':plan_id,'purpose':purpose,
                'automatic_retry_count':0,'counts_before':state['counts'],'production_authorized':False}
        intent = {**body,'intent_id':content_hash(value=body)}
        line = canonical_json_bytes(value=intent).rstrip(b'\n')+b'\n'
        mirror = self.root.parent/('.'+self.root.name+'.claims.jsonl')
        _need(mirror.is_file() and mirror.read_bytes() == (self.root/'claims.jsonl').read_bytes(), 'CLAIM_MIRROR_DIFFERS')
        for path in (mirror,self.root/'claims.jsonl'):
            handle = os.open(path, os.O_WRONLY|os.O_APPEND)
            try:
                offset = 0
                while offset < len(line):
                    written = os.write(handle,line[offset:]); _need(written>0,'CLAIM_WRITE_FAILED');offset+=written
                os.fsync(handle)
            finally: os.close(handle)
        slot = self.root/'calls'/('%04d'%ordinal)
        self._write_new(slot/'intent.json',intent)
        return slot,intent

    def finish_sec(self, *, path, intent, receipt):
        from .canonical import content_hash
        _need(self._locked and path == self.root/'calls'/('%04d'%intent['ordinal'])
              and strict_json_file(path=path/'intent.json') == intent
              and receipt['intent_id'] == intent['intent_id'], 'FINISH_RELATION_DIFFERS')
        body = {'record_type':'ISSUE_47_HISTORICAL_CALL_TERMINAL','intent_id':intent['intent_id'],
                'sec_receipt_id':receipt['receipt_id'],'status':receipt['status'],
                'stop_reason':receipt['stop_reason'],'execution_mode':self.binding['execution_mode'],
                'counts':[0,0,1],'counts_kind':'ACTUAL_OR_UNKNOWN_CHARGED' if self.live else 'RECORDED_TEST_SIMULATION',
                'production_authorized':False}
        terminal = {**body,'terminal_id':content_hash(value=body)}
        self._write_new(path/'terminal.json',terminal)
        return terminal
