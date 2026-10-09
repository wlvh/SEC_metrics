"""Current V15 SEC source factory and one mock HTTP request; zero real calls."""
import io
import json
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from sec_http import SecHttpClient, parse_request_log_rows
from vnext.canonical import content_hash
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot

plan = json.loads((ROOT/'docs/evidence/issue28_continuous/paramount-c04-source-inspection/'
                   'registration-form-discovery/four-url-plan.json').read_text())
selected = next(row for row in plan['requirements']
                if row['filing_form'] == '8-K12B/A'
                and row['roles'] == ['registration_event_primary'])
url = selected['source_url']
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
with tempfile.TemporaryDirectory(prefix='issue28-sec-current-two-stage-') as temporary:
    root = Path(temporary).resolve()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_RECORDED_SOCKET')):
        session = recorded_sec_session(root=root/'ledger',
            response=b'<html><body>Recorded transport only.</body></html>')
        captured = session.capture(company_id='paramount_skydance_paramount_global',
                                   url=url)
        assert captured['status'] == 'SUCCEEDED' and captured['calls'] == [0, 0, 0]
        with session.ledger.locked():
            state = session.ledger.snapshot()
        assert state['counts'] == [0, 0, 1] and not state['stopped_channels']
    wire_root = root/'wire'
    wire_root.mkdir()
    client = SecHttpClient(workdir=wire_root,
        config_path=ROOT/'config/sec_config.json',
        log_path=wire_root/'evidence/requests_log.csv')
    client.config = {**client.config, 'max_retries': 0}
    class Reply(io.BytesIO):
        status = 200
        headers = {'Content-Type': 'text/html'}
    def reply(*, request, timeout):
        assert request.full_url == url and request.get_method() == 'GET'
        assert timeout == 60 and request.get_header('User-agent')
        return Reply(b'<html><body>Mock SEC source</body></html>')
    with patch('sec_http.urlopen', side_effect=reply) as opener:
        observed = client.fetch(url=url, purpose='ISOLATED_CURRENT_SEC_WIRING',
                                local_path=wire_root/'response.html')
        assert opener.call_count == 1 and observed.status_code == 200
    rows = parse_request_log_rows(text=(wire_root/'evidence/requests_log.csv').read_text())
    assert len(rows) == 1 and rows[0]['retry_attempt'] == '0'
    print(json.dumps({'status': 'PASS_CURRENT_SEC_FACTORY_AND_MOCK_HTTP',
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'execution_authority_hash': content_hash(value=requirement['execution_authority']),
        'source_url': url, 'recorded_counts': state['counts'],
        'actual_http_path_verified': True,
        'checkpoint_registration_verified': bool(captured['checkpoint_id']),
        'zero_retry_verified': True, 'real_calls': [0, 0, 0]}))
