"""First #54 experiment: original recorded acquisition, target-only delta."""
import json
from pathlib import Path
import shutil
import socket
import sys
import time
from unittest.mock import patch

code = Path('/workspace/work/sec-company-compute')
root = Path('/workspace/work/probe-b')
sys.path[:0] = [str(code), str(code / 'scripts')]
from sec_urls import submissions_url
from sec_http import parse_request_log_rows, validate_request_log_manifest
from vnext.canonical import canonical_json_bytes, sha256_file
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.normal_governance_input import _Sources
from vnext.normal_source_requirements import discover_saved_source_requirements
from vnext.ordinary_source_authority import checkpoint_installation, EXPORT_PATH

root.mkdir()
company = 'jpmorgan_chase'
url = submissions_url(cik=19617)
source = _Sources(code, company, '19617').read(url, role='sec_submissions_inventory', media_type='application/json')
start = time.monotonic()
with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
    session = recorded_sec_session(root=root / 'ledger', response=source['raw_bytes'])
    captured = session.capture(company_id=company, url=url, refresh_metadata=True)
    (root / 'capture.json').write_bytes(canonical_json_bytes(value=captured))
    print('CAPTURE', captured['status'], 'seconds', time.monotonic()-start, flush=True)
    checkpoint, dependencies = checkpoint_installation(source_root=session.data_root)
    (root / 'checkpoint.json').write_bytes(canonical_json_bytes(value=checkpoint))
    discovery = discover_saved_source_requirements(repo_root=session.data_root, company_id=company)
    (root / 'discovery.json').write_bytes(canonical_json_bytes(value=discovery))
    urls = {r['source_url'] for r in discovery['requirements']}
    paths = {'config/company_registry.csv', 'evidence/requests_log.csv', 'evidence/requests_log_manifest.json', *dependencies}
    rows = parse_request_log_rows(text=(session.data_root / 'evidence/requests_log.csv').read_text())
    for row in rows:
        if row['source_url'] in urls:
            paths.update(row[k] for k in ('repo_relative_path', 'headers_repo_relative_path') if row[k])
    export = root / 'company-source'
    for path in sorted(paths):
        origin = session.data_root / path
        if origin.is_file():
            target = export / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
    for directory in ('config', 'catalog'):
        shutil.copytree(code / directory, export / directory, dirs_exist_ok=True)
    (export / EXPORT_PATH).write_bytes(canonical_json_bytes(value=checkpoint))
    validate_request_log_manifest(log_path=export / 'evidence/requests_log.csv')
    summary = {'company_id': company, 'capture_status': captured['status'], 'captures': len(checkpoint['captures']), 'capture_companies': sorted({c['receipt']['company_id'] for c in checkpoint['captures']}), 'calls': captured['calls'], 'source_credit': checkpoint['source_credit'], 'ledger_sha256': sha256_file(path=export / 'evidence/requests_log.csv'), 'export_paths': len(paths), 'export_bytes': sum(p.stat().st_size for p in export.rglob('*') if p.is_file()), 'preparation_seconds': time.monotonic()-start}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)
