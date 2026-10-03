"""Read six exact development packets as one source-coverage view.

This preserves each raw proposal, including repeated supporting context.
It neither merges investigations nor constructs a native business Result.
"""
import importlib.util
import json
import socket
import ssl  # Load its socket subclass before the execution-time network guard.
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def read_complete():
    old = module('d03_existing_checker', HERE/'postprocess.py')
    cases = module('d03_development_case', HERE/'case_processing.py')
    visible = module('d03_visible_case', HERE/'visible0/check.py')
    facts = module('d03_facts01_case', HERE/'facts01/check.py')
    plan = json.loads((HERE.parent/'d03-complete-context-plan-20261003/plan.json').read_text())
    source_raw = old.SOURCE.read_bytes()
    old.need(old.sha(source_raw) == plan['source_json_sha256'], 'COMPLETE_SOURCE_CHANGED')
    source = old.strict_json_loads(text=source_raw.decode())
    addresses = [
        ('visible0', visible.OUTPUT),
        ('facts01', facts.OUTPUT),
        ('facts23', Path('/private/tmp/issue28-d03-native-facts23-processing-20261003')),
        ('group3', Path('/private/tmp/issue28-d03-native-group3-processing-20261003')),
        ('', Path('/private/tmp/issue28-d03-native-checked-response-20261003')),
        ('group5', Path('/private/tmp/issue28-d03-native-group5-processing-20261003')),
    ]
    owners, rows, findings, unresolved = [], [], [], []
    for index, (label, folder) in enumerate(addresses):
        evidence = HERE/label
        expected = json.loads((evidence/'checked-output.json').read_text())
        digest = expected['processing_sha256']
        if index == 0:
            report = visible.read(digest)
        elif index == 1:
            report = facts.read(folder, digest)
        elif index == 4:
            report = old.read(folder, digest)
        else:
            report = cases.read(folder, digest, expected['report']['request_sha256'],
                                expected['report']['response_sha256'])
        old.need(report == expected['report'], 'COMPLETE_REPORT_CHANGED')
        request_raw = (folder/'request-body.bin').read_bytes()
        response_raw = (folder/'response.bin').read_bytes()
        old.need(old.sha(request_raw) == plan['requests'][index]['request_sha256'],
                 'COMPLETE_REQUEST_MAPPING_CHANGED')
        wire = old.strict_json_loads(text=request_raw.decode())
        payload = old.strict_json_loads(text=wire['messages'][1]['content'])
        value = old.strict_json_loads(text=response_raw.decode())
        old.need(value['reviewed_unit_ids'] == plan['requests'][index]['responsibility_unit_ids'],
                 'COMPLETE_RESPONSIBILITY_CHANGED')
        owners.extend(value['reviewed_unit_ids'])
        rows.append({'index': index, 'request_sha256': old.sha(request_raw),
            'response_sha256': old.sha(response_raw), 'processing_sha256': digest,
            'responsibility_unit_ids': value['reviewed_unit_ids'],
            'findings': len(value['findings']), 'unresolved': len(value['unresolved']),
            'output_reference_tokens': report['checks']['reference_tokens'],
            'scope_current_involvement': value['scope_current_involvement']})
        for item_index, item in enumerate(value['findings']):
            findings.append({'request_index': index, 'finding_index': item_index, 'original': item})
        for item_index, item in enumerate(value['unresolved']):
            unresolved.append({'request_index': index, 'unresolved_index': item_index, 'original': item})
    old.need(owners == source['required_unit_ids'] and len(owners) == len(set(owners)),
             'COMPLETE_UNIT_COVERAGE_MISSING_DUPLICATE')
    return {'origin': 'DEVELOPMENT_MODEL', 'source_sha256': old.sha(source_raw),
        'source_id': source['semantic_source_id'], 'requests': rows,
        'source_units_owned_once': len(owners), 'original_findings': findings,
        'original_unresolved': unresolved, 'finding_records_not_matter_count': len(findings),
        'semantic_merge_or_complete_company_acceptance': False,
        'native_result_or_run_created': False, 'new_calls': [0, 0, 0]}


if __name__ == '__main__':
    socket.socket = forbidden
    socket.create_connection = forbidden
    subprocess.Popen = forbidden
    subprocess.run = forbidden
    start = time.monotonic()
    value = read_complete()
    (HERE/'complete-set.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'source_units': value['source_units_owned_once'], 'requests': len(value['requests']),
        'original_finding_records': len(value['original_findings']),
        'original_unresolved': len(value['original_unresolved']),
        'seconds': round(time.monotonic()-start, 3), 'new_calls': [0, 0, 0]}))
