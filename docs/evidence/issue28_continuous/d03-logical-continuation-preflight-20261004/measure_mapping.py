"""Actual saved-source mapping/resource execution; no model invocation."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import traceback

import task_mapping
from sec_http import write_immutable_bytes

HERE = Path(__file__).resolve().parent
BASE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence')
PRIVATE = BASE/'d03-complete-task-mapping-20261004'
SAMPLES = [
    ('marriott', 'd03-complete-six-responses-20261004/source.json',
     '5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b'),
    ('jpm', 'd03-jpm-positive-20261004/source.json',
     '11189144bf0bff60c8995086f9fb2bfa253a38a1206d557a059b9c771f8486a9'),
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blocked(*a, **k):
    raise AssertionError('NETWORK_OR_SUBPROCESS_FORBIDDEN')


def run():
    socket.socket = socket.create_connection = subprocess.Popen = blocked
    started = time.monotonic(); summaries = []
    for company, rel, digest in SAMPLES:
        start = time.monotonic()
        raw = (BASE/rel).read_bytes(); assert sha(raw) == digest
        source = json.loads(raw)
        result = task_mapping.plan(source, digest)
        requests = []
        for task in result['tasks']:
            body = task['request_body']; path = PRIVATE/company/'requests'/(sha(body)+'.json')
            write_immutable_bytes(path=path, content=body)
            requests.append({'request_path': str(path), 'request_sha256': sha(body),
                             'owned_references': [list(r) for r in task['owned_references']],
                             'native_context_references': task['payload']['native_context_references'],
                             'measure': task['measure']})
        summary = {k: v for k, v in result.items() if k != 'tasks'}
        summary.update(company=company, source_path=str(BASE/rel),
                       source_units=len(source['units']), requests=requests,
                       seconds=round(time.monotonic()-start,3))
        summaries.append(summary)
        print(json.dumps({k: summary[k] for k in ['company','status','original_reference_count',
             'proposed_initial_request_count','complete_owner_mapping','seconds']}),flush=True)
    report = {'record_type':'D03_ACTUAL_COMPLETE_SOURCE_ITEM_MAPPING_RESOURCE_ONLY',
              'samples': summaries, 'seconds':round(time.monotonic()-started,3),
              'code_root':str(HERE.parents[3]), 'actual_saved_source_root':str(BASE),
              'private_request_root':str(PRIVATE),
              'old_response_or_unit_contract_rebound':False,
              'new_model_response':False,'new_native_or_company_credit':False,
              'business_calls':[0,0,0],
              'additional_call_opportunities_granted':0,'semantic_acceptance':False}
    (HERE/'actual-task-mapping.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    try:
        run()
    except Exception:
        (HERE/'mapping-measure-done.json').write_text(json.dumps({'status':'FAILED','traceback':traceback.format_exc()})+'\n')
        raise
    else:
        (HERE/'mapping-measure-done.json').write_text(json.dumps({'status':'PASSED_RESOURCE_EXECUTION_NOT_MODEL'})+'\n')
