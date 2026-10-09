"""Read-only current #28 saved-source gap census; never fetch."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext.normal_annual_input import _registry_rows
from vnext.normal_source_requirements import discover_saved_source_requirements
from vnext.normal_source_authority import ROOT

source = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    for company in [r['company_id'] for r in _registry_rows(repo_root=ROOT)]:
        try:
            result = discover_saved_source_requirements(
                repo_root=source, company_id=company)
            missing = [r for r in result['requirements']
                       if r['saved_status'] != 'VERIFIED_SAVED_SOURCE']
            refresh = [r for r in result['requirements']
                       if r['refresh_for_new_discovery']]
            row = {'company': company, 'status': result['status'],
                   'requirements': len(result['requirements']),
                   'missing_count': len(missing),
                   'metadata_refresh_count': len(refresh),
                   'missing': [{'status': r['saved_status'],
                                'roles': r['roles'], 'url': r['source_url']}
                               for r in missing]}
        except Exception as error:
            row = {'company': company, 'error_type': type(error).__name__,
                   'error': str(error)}
        print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)
