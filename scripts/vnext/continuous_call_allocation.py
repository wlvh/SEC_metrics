"""One ordinary reservation for the approved October 14 history batch.

This holds part of the existing allowance. It neither adds credit nor provides
transport/source permission. Claims and original stop rules remain in CallLedger.
"""
from .canonical import content_hash, strict_json_file
from .continuous_call_policy import need
from .invocation_control import _exclusive_write_json
from pathlib import Path

RECORD_PATH = 'history-20261014-allocation.json'


def _validate(ledger, value):
    need(value.get('record_type') == 'CONTINUOUS_CALL_ALLOCATION_V1'
         and value.get('allocation_id') == content_hash(value={
             k:v for k,v in value.items() if k != 'allocation_id'})
         and value.get('binding_id') == ledger.binding['binding_id']
         and value.get('budget_root') == str(ledger.root)
         and value.get('execution_mode') == ('LIVE' if ledger.live else 'RECORDED_TEST_ONLY')
         and value.get('executor') == 'issue47', 'ALLOCATION_RECORD_INVALID')
    tasks = value.get('tasks')
    need(type(tasks) is list and tasks and all(type(t) is dict
         and type(t.get('task_id')) is str and t['task_id']
         and t.get('channel') in {'PROVIDER','SEC'} for t in tasks),
         'ALLOCATION_TASKS_INVALID')
    need(len({t['task_id'] for t in tasks}) == len(tasks), 'ALLOCATION_TASKS_DUPLICATE')
    provider = sum(t['channel'] == 'PROVIDER' for t in tasks)
    sec = len(tasks)-provider
    need(value.get('maximum_counts') == [provider,provider,sec],
         'ALLOCATION_TASK_COUNTS_DIFFER')
    if ledger.live:
        scope = strict_json_file(path=Path(__file__).resolve().parents[2]/
                                 'config/history_call_allocation_20261014.json')
        fields = ('maximum_counts','approval_url','execution_scope_url',
                  'maximum_request_input_tokens','maximum_total_input_tokens','maximum_output_tokens')
        need(all(value.get(key) == scope[key] for key in fields)
             and all(t.get('metric_id') in scope['counts_by_metric']
                     for t in tasks if t['channel'] == 'PROVIDER')
             and all(sum(t['channel'] == 'PROVIDER' and t.get('metric_id') == metric for t in tasks) == count
                     for metric,count in scope['counts_by_metric'].items())
             and next(t for t in tasks if t['channel'] == 'SEC').get('url') ==
                 scope['sec_url'],
             'ALLOCATION_APPROVED_HISTORY_SCOPE_DIFFER')
    for key in ('maximum_request_input_tokens','maximum_total_input_tokens','maximum_output_tokens'):
        need(type(value.get(key)) is int and value[key] > 0, 'ALLOCATION_INPUT_LIMIT_INVALID')
    baseline = value.get('counts_at_reservation')
    need(type(baseline) is list and len(baseline) == 3
         and all(type(n) is int and n >= 0 for n in baseline),
         'ALLOCATION_BASELINE_INVALID')
    return value


def read(ledger):
    path = ledger.root/RECORD_PATH
    return _validate(ledger, strict_json_file(path=path)) if path.exists() else None


def observe(ledger, claims, counts):
    value = read(ledger)
    marked = [c for c in claims if c.get('budget_allocation_id') is not None]
    need(value is not None or not marked, 'ALLOCATION_RECORD_MISSING')
    if value is None:
        return None
    tasks = {t['task_id']:t for t in value['tasks']}
    consumed = set(); used = [0,0,0]; inputs = 0; input_limit_exceeded = False
    for intent in marked:
        task = intent.get('budget_allocation_task')
        need(intent['budget_allocation_id'] == value['allocation_id']
             and intent.get('allocation_executor') == value['executor']
             and type(task) is dict and task.get('task_id') in tasks
             and task == tasks[task['task_id']] and task['channel'] == intent['channel'],
             'ALLOCATION_CLAIM_SCOPE_CHANGED')
        need(task['task_id'] not in consumed, 'ALLOCATION_TASK_CONSUMED')
        consumed.add(task['task_id'])
        delta = [1,1,0] if task['channel'] == 'PROVIDER' else [0,0,1]
        used = [a+b for a,b in zip(used,delta)]
        estimate = intent.get('estimated_input_tokens')
        if task['channel'] == 'PROVIDER':
            need(type(estimate) is int and 0 < estimate <= value['maximum_request_input_tokens'],
                 'ALLOCATION_REQUEST_INPUT_EXCEEDED')
            # Pending or null usage stays unknown, never zero. Its reserved
            # estimate remains charged; the existing stop blocks more egress.
            wire = ledger.root/'calls'/('%04d' % intent['ordinal'])/'wire/journal.json'
            actual = strict_json_file(path=wire).get('usage',{}).get('input_tokens') if wire.exists() else None
            inputs += max(estimate, actual) if type(actual) is int else estimate
            input_limit_exceeded |= type(actual) is int and actual > value['maximum_request_input_tokens']
        else:
            need(estimate is None, 'ALLOCATION_SEC_INPUT_INVALID')
    reserved = [a-b for a,b in zip(value['maximum_counts'],used)]
    need(all(n >= 0 for n in reserved), 'ALLOCATION_COUNT_EXCEEDED')
    need(all(b <= c for b,c in zip(value['counts_at_reservation'],counts)),
         'ALLOCATION_COUNT_WENT_BACKWARDS')
    need(all(c+r <= m for c,r,m in zip(counts,reserved,ledger.binding['limits'])),
         'ALLOCATION_COUNT_EXCEEDED')
    return {'allocation_id':value['allocation_id'],'reserved_counts':reserved,
            'used_counts':used,'consumed_tasks':sorted(consumed),'input_tokens_accounted':inputs,
            'observed_request_input_limit_exceeded':input_limit_exceeded,
            'remaining_unallocated':[m-c-r for m,c,r in zip(ledger.binding['limits'],counts,reserved)]}


def reserve(ledger, value):
    """Idempotent fixed batch registration, while holding the original lock."""
    need(ledger._locked, 'CONTINUOUS_LEDGER_LOCK_REQUIRED')
    value = _validate(ledger, value)
    existing = read(ledger)
    if existing is not None:
        need(existing == value, 'ALLOCATION_ALREADY_REGISTERED_DIFFERENTLY')
        ledger.snapshot()
        return existing
    state = ledger.snapshot()
    need(state['counts'] == value['counts_at_reservation'], 'ALLOCATION_BASELINE_CHANGED')
    need(not state['stopped_channels'], 'ALLOCATION_EXISTING_CHANNEL_STOPPED')
    need(all(c+r <= m for c,r,m in zip(state['counts'],value['maximum_counts'],ledger.binding['limits'])),
         'ALLOCATION_COUNT_EXCEEDED')
    _exclusive_write_json(path=ledger.root/RECORD_PATH,value=value)
    return value


def claim_fields(ledger, state, *, channel, allocation_id, task, executor, input_tokens):
    """Validate reservation ownership/scope; never make a socket call."""
    if allocation_id is None:
        need(task is None and executor is None and input_tokens is None,
             'ALLOCATION_CONTEXT_WITHOUT_ID')
        delta = [1,1,0] if channel == 'PROVIDER' else [0,0,1]
        remaining = state.get('allocation',{}).get('remaining_unallocated')
        need(remaining is None or all(d <= r for d,r in zip(delta,remaining)),
             'CONTINUOUS_RESERVED_BALANCE_EXHAUSTED')
        return {}
    value = read(ledger)
    need(value is not None and value['allocation_id'] == allocation_id
         and executor == value['executor'] and type(task) is dict
         and task in value['tasks'] and task['channel'] == channel,
         'ALLOCATION_REQUEST_SCOPE_INVALID')
    progress = state['allocation']
    need(task['task_id'] not in progress['consumed_tasks'], 'ALLOCATION_TASK_CONSUMED')
    need(not progress['observed_request_input_limit_exceeded'], 'ALLOCATION_OBSERVED_INPUT_EXCEEDED')
    if channel == 'PROVIDER':
        need(type(input_tokens) is int and 0 < input_tokens <= value['maximum_request_input_tokens'],
             'ALLOCATION_REQUEST_INPUT_EXCEEDED')
        need(progress['input_tokens_accounted']+input_tokens <= value['maximum_total_input_tokens'],
             'ALLOCATION_TOTAL_INPUT_EXCEEDED')
    else:
        need(input_tokens is None, 'ALLOCATION_SEC_INPUT_INVALID')
    return {'budget_allocation_id':allocation_id,'budget_allocation_task':task,
            'allocation_executor':executor,'estimated_input_tokens':input_tokens}
