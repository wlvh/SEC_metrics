"""One fixed allowance over existing WB-3/SEC evidence, with a process lock.

Each slot retains its intent, native execution directory and terminal. A lost
terminal consumes its possible call and blocks that channel until reconciled;
changing checkout, phase or request identity cannot reset the allowance.
No prices or monetary limits participate in admission.
"""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import os

from .canonical import canonical_json_bytes, content_hash, strict_json_file, strict_json_loads
from .continuous_call_policy import load_delegation, need
from .invocation_control import _exclusive_write_json
from .sources import resolve_repository_file

_FACTORY = object()
_STOP = {'HTTP_402', 'UNKNOWN_REMOTE_OUTCOME', 'SOURCE_AUTHENTICITY_FAILED', 'USAGE_UNKNOWN'}


def _read(root, relative):
    return strict_json_file(path=resolve_repository_file(repo_root=root, repo_relative_path=relative))


def _identified(body, field):
    return {**body, field: content_hash(value=body)}


def _identity(value, field):
    need(value.get(field) == content_hash(value={k:v for k,v in value.items() if k != field}),
         'CONTINUOUS_LEDGER_RECORD_CHANGED:' + field)


class CallLedger:
    """Factory-owned mode and location; recorded ledgers cannot authorize live."""
    def __init__(self, *, factory, root, binding, live):
        need(factory is _FACTORY, 'CONTINUOUS_LEDGER_FACTORY_REQUIRED')
        self.root, self.binding, self.live = root, binding, live
        self._factory = factory
        self._locked = False

    @contextmanager
    def locked(self):
        need(not self._locked, 'CONTINUOUS_LEDGER_ALREADY_LOCKED')
        need(self._factory is _FACTORY and self.binding['execution_mode'] ==
             ('LIVE' if self.live else 'RECORDED_TEST_ONLY'), 'CONTINUOUS_LEDGER_MODE_CHANGED')
        need(self.root.is_absolute() and not any(p.is_symlink() for p in [self.root,*self.root.parents]),
             'CONTINUOUS_LEDGER_PATH_ALIAS')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Lock the stable directory, not a replaceable lock file.
        fd = os.open(self.root, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._locked = True
            binding_path = self.root/'binding.json'
            anchor = self.root.parent/('.'+self.root.name+'.initialized.json')
            if not binding_path.exists():
                need(not anchor.exists() and not list(self.root.iterdir()),
                     'CONTINUOUS_LEDGER_BINDING_MISSING_OR_RESET')
                _exclusive_write_json(path=anchor,value=self.binding)
                _exclusive_write_json(path=binding_path, value=self.binding)
            need(strict_json_file(path=anchor) == self.binding,
                 'CONTINUOUS_LEDGER_INITIALIZATION_ANCHOR_CHANGED')
            need(_read(self.root,'binding.json') == self.binding, 'CONTINUOUS_LEDGER_BINDING_CHANGED')
            yield self
        finally:
            self._locked = False
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def snapshot(self):
        need(self._locked, 'CONTINUOUS_LEDGER_LOCK_REQUIRED')
        directory = self.root/'calls'
        paths = sorted(directory.iterdir()) if directory.exists() else []
        claims_path = self.root/'claims.jsonl'
        claims = ([strict_json_loads(text=line) for line in
                   resolve_repository_file(repo_root=self.root,repo_relative_path='claims.jsonl').read_text().splitlines()]
                  if claims_path.exists() else [])
        need(len(paths)==len(claims), 'CONTINUOUS_LEDGER_CLAIM_SET_CHANGED')
        need([p.name for p in paths] == ['%04d' % (i+1) for i in range(len(paths))],
             'CONTINUOUS_LEDGER_SEQUENCE_CHANGED')
        total = [0,0,0]; stopped = set(); requests = set(); rows = []
        previous = None
        for path in paths:
            need(path.is_dir() and not path.is_symlink(), 'CONTINUOUS_LEDGER_SLOT_UNSAFE')
            intent = _read(path,'intent.json'); _identity(intent,'intent_id')
            need(claims[int(path.name)-1] == intent, 'CONTINUOUS_LEDGER_CLAIM_CHANGED')
            need(intent['ordinal'] == int(path.name) and intent['previous_intent_id'] == previous
                 and intent['binding_id'] == self.binding['binding_id']
                 and intent['channel'] in {'PROVIDER','SEC'}, 'CONTINUOUS_LEDGER_INTENT_BINDING_CHANGED')
            previous = intent['intent_id']; channel = intent['channel']
            key = (channel,intent['request_digest'])
            need(key not in requests, 'CONTINUOUS_LEDGER_DUPLICATE_REQUEST')
            requests.add(key)
            terminal_path = path/'terminal.json'
            maximum = [1,1,0] if channel == 'PROVIDER' else [0,0,1]
            if terminal_path.exists():
                terminal = _read(path,'terminal.json'); _identity(terminal,'terminal_id')
                need(terminal['intent_id'] == intent['intent_id'], 'CONTINUOUS_LEDGER_TERMINAL_BINDING_CHANGED')
                observed = terminal['counts']
                need(observed == maximum, 'CONTINUOUS_LEDGER_TERMINAL_COUNTS_CHANGED')
                # Native bytes, including failures, remain the count evidence.
                for relative, digest in terminal['evidence'].items():
                    from .canonical import sha256_file
                    need(sha256_file(path=resolve_repository_file(repo_root=path,repo_relative_path=relative)) == digest,
                         'CONTINUOUS_LEDGER_EVIDENCE_CHANGED:' + relative)
                if terminal['stop_reason'] in _STOP: stopped.add(channel)
                status = terminal['status']
            else:
                # An admitted but interrupted execution may have reached the
                # endpoint. It never silently releases its count or retries.
                observed = maximum; stopped.add(channel); status = 'UNKNOWN_PENDING_RECONCILIATION'
            total = [a+b for a,b in zip(total,observed)]
            rows.append({'ordinal':intent['ordinal'],'channel':channel,'status':status,'counts':observed})
        need(all(a<=b for a,b in zip(total,self.binding['limits'])), 'CONTINUOUS_TOTAL_COUNT_EXCEEDED')
        return {'counts':total,'stopped_channels':sorted(stopped),'requests':requests,
                'previous_intent_id':previous,'rows':rows}

    def claim(self, *, channel, request_digest, requirement, plan_id, purpose):
        state = self.snapshot()
        need(channel in {'PROVIDER','SEC'}, 'CONTINUOUS_CHANNEL_INVALID')
        need(channel not in state['stopped_channels'], 'CONTINUOUS_CHANNEL_STOPPED:' + channel)
        need((channel,request_digest) not in state['requests'], 'CONTINUOUS_UNCHANGED_REQUEST_REDRAW_FORBIDDEN')
        need(purpose in self.binding['purposes'], 'CONTINUOUS_PURPOSE_NOT_APPROVED')
        delta = [1,1,0] if channel == 'PROVIDER' else [0,0,1]
        need(all(a+b<=c for a,b,c in zip(state['counts'],delta,self.binding['limits'])),
             'CONTINUOUS_TOTAL_COUNT_EXHAUSTED')
        ordinal = len(state['rows'])+1
        intent = _identified({'record_type':'CONTINUOUS_CALL_INTENT','ordinal':ordinal,
            'binding_id':self.binding['binding_id'],'previous_intent_id':state['previous_intent_id'],
            'channel':channel,'request_digest':request_digest,'plan_id':plan_id,'purpose':purpose,
            'requirement_id':requirement['requirement_id'],
            'requirement_closure_hash':requirement['requirement_closure_hash'],
            'execution_mode':'LIVE' if self.live else 'RECORDED_TEST_ONLY'},'intent_id')
        path = self.root/'calls'/('%04d' % ordinal)
        # Separate append-only claim log detects a removed last slot as well
        # as middle gaps; a crash between writes rejects before further egress.
        fd = os.open(self.root/'claims.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        try:
            raw = canonical_json_bytes(value=intent).rstrip(b'\n')+b'\n'; offset = 0
            while offset<len(raw):
                written = os.write(fd,raw[offset:]); need(written>0,'CONTINUOUS_CLAIM_WRITE_FAILED'); offset+=written
            os.fsync(fd)
        finally: os.close(fd)
        _exclusive_write_json(path=path/'intent.json',value=intent)
        return path, intent

    def finish_provider(self, *, path, intent, execution, wire):
        """Count the original WB-3 marker, never the caller's success label."""
        from .canonical import sha256_file
        need(self._locked and path == self.root/'calls'/('%04d' % intent['ordinal']),
             'CONTINUOUS_LEDGER_SLOT_CHANGED')
        need(_read(path,'intent.json') == intent, 'CONTINUOUS_LEDGER_INTENT_CHANGED')
        identity = execution['execution_id'].split(':',1)[1]
        relative = 'invocation_control/executions/'+identity+'.json'
        need(_read(path,relative) == execution, 'CONTINUOUS_NATIVE_TERMINAL_CHANGED')
        _identity(execution,'execution_receipt_id')
        marker_relative = 'invocation_control/egress/'+identity+'/01.json'
        marker = _read(path,marker_relative); _identity(marker,'egress_marker_id')
        need(marker['ai_invocation_plan_id'] == intent['plan_id']
             and marker['execution_id'] == execution['execution_id'] and marker['attempt_ordinal'] == 1
             and marker['transport_kind'] == ('REAL_MODEL_PROVIDER' if self.live else 'MOCK'),
             'CONTINUOUS_NATIVE_MARKER_CHANGED')
        expected = {'real_model_provider_egress_count':int(self.live),
                    'paid_model_provider_call_count':int(self.live),'mock_transport_invocation_count':int(not self.live)}
        need(execution['counters'] == expected, 'CONTINUOUS_NATIVE_COUNT_CHANGED')
        need(_read(path,'wire/journal.json') == wire, 'CONTINUOUS_WIRE_CHANGED')
        stop = wire['error_class'] if wire['error_class'] in _STOP else ''
        if execution['status'] == 'UNKNOWN_REMOTE_OUTCOME': stop = 'UNKNOWN_REMOTE_OUTCOME'
        if wire['usage']['input_tokens'] is None or wire['usage']['output_tokens'] is None:
            stop = stop or 'USAGE_UNKNOWN'
        evidence = {p.relative_to(path).as_posix():sha256_file(path=p)
                    for p in path.rglob('*') if p.is_file()}
        terminal = _identified({'record_type':'CONTINUOUS_CALL_TERMINAL','intent_id':intent['intent_id'],
            'status':execution['status'],'stop_reason':stop,'counts':[1,1,0],
            'counts_kind':'ACTUAL_OR_UNKNOWN_CHARGED' if self.live else 'RECORDED_TEST_SIMULATION',
            'execution_receipt_id':execution['execution_receipt_id'],'evidence':evidence},'terminal_id')
        _exclusive_write_json(path=path/'terminal.json',value=terminal)
        return terminal


def live_ledger(*, requirement):
    approved = load_delegation(requirement=requirement,online=True)
    policy = requirement['policy']
    body = {'record_type':'CONTINUOUS_CALL_ALLOWANCE','delegation_url':approved['html_url'],
        'delegation_body_sha256':policy['delegation_body_sha256'],
        'root':policy['budget_root'],'limits':policy['maximum_additional_provider_paid_sec_calls'],
        'purposes':policy['scope']['purposes'],'execution_mode':'LIVE'}
    return CallLedger(factory=_FACTORY,root=Path(body['root']),binding=_identified(body,'binding_id'),live=True)


def recorded_ledger(*, root, limits=(240,240,80)):
    """Offline tests only; no type conversion to production execution."""
    root = root.resolve()
    from .continuous_call_policy import POLICY_PATH
    from .normal_source_authority import ROOT
    need(root != Path(strict_json_file(path=ROOT/POLICY_PATH)['budget_root']),
         'CONTINUOUS_TEST_CANNOT_USE_LIVE_LEDGER')
    body = {'record_type':'CONTINUOUS_CALL_ALLOWANCE','root':str(root),'limits':list(limits),
        'purposes':['remaining_development_feasibility','verification_after_engineering_repair',
                    'final_real_isolated_acceptance'],'execution_mode':'RECORDED_TEST_ONLY'}
    return CallLedger(factory=_FACTORY,root=root,binding=_identified(body,'binding_id'),live=False)
