import json
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import case_processing as case

REQUEST_SHA = '596ef5aa691c7c65c0c10e9ef24656a8fc3bc350b3db81ead74c05773975a7c7'
RESPONSE_SHA = '70fe1a24627ff171efadbfbc24eca50841a73418d92a65343467d7df69722e12'
OUTPUT = Path('/private/tmp/issue28-d03-native-facts23-processing-20261003')


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_AND_SUBPROCESS_FORBIDDEN')


if __name__ == '__main__':
    start = time.monotonic()
    if len(sys.argv) > 1 and sys.argv[1] == 'cold':
        socket.socket = forbidden
        socket.create_connection = forbidden
        subprocess.Popen = forbidden
        subprocess.run = forbidden
        saved = json.loads((HERE/'checked-output.json').read_text())
        report = case.read(OUTPUT, saved['processing_sha256'], REQUEST_SHA, RESPONSE_SHA)
        assert report == saved['report']
        out = {'report_equal': True, 'seconds': round(time.monotonic()-start, 3),
               'native_credit': False, 'calls': [0, 0, 0]}
        (HERE/'cold-output.json').write_text(json.dumps(out, indent=2)+'\n')
    else:
        request = Path('/private/tmp/issue28-d03-complete-context-plan-20261003-checked/2/request-body.json').read_bytes()
        response = (HERE/'independent-input/response.log').read_bytes()
        identity, report = case.record(OUTPUT, request, response, REQUEST_SHA, RESPONSE_SHA)
        assert case.read(OUTPUT, identity, REQUEST_SHA, RESPONSE_SHA) == report
        controls = []
        for name, arguments in [
            ('wrong_request_external_id', (request, response, '0'*64, RESPONSE_SHA)),
            ('wrong_response_external_id', (request, response, REQUEST_SHA, '0'*64))]:
            try:
                case.checked_report(*arguments)
            except ValueError as error:
                controls.append({'case': name, 'rejected': str(error)})
            else:
                raise AssertionError(name+' accepted')
        out = {'tested_base_sha': '07634fe8b6aefa583eaba37353c9446c815f02a8',
            'uncommitted_evidence_adapter': True, 'processing_sha256': identity,
            'report': report, 'controls': controls, 'seconds': round(time.monotonic()-start, 3)}
        (HERE/'checked-output.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(out, ensure_ascii=False))
