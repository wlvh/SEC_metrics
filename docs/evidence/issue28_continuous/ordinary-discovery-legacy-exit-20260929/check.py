"""Discover all ten current #28 source dependencies with old producers disabled."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
spec = importlib.util.spec_from_file_location('legacy_probe', ROOT /
    'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


originals = {'claims': ACQUIRED/'claims.jsonl',
    'source_log': ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active': ROOT/'outputs/active_publication.json'}
before = {key: digest(path) for key, path in originals.items()}
with (patch.object(socket.socket, 'connect',
                   side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo',
                   side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')),
      probe.legacy_disabled() as disabled):
    from vnext.normal_source_requirements import inspect_source_requirements
    report = inspect_source_requirements(repo_root=ACQUIRED/'source-inputs')
    rows = []
    for item in report['companies']:
        requirements = item.get('requirements', [])
        rows.append({'company_id': item['company_id'],
            'status': item['status'],
            'requirement_count': len(requirements),
            'metadata_refresh_urls': [row['source_url'] for row in requirements
                if row['refresh_for_new_discovery']],
            'not_directly_saved': [{'source_url': row['source_url'],
                'saved_status': row['saved_status'], 'roles': row['roles']}
                for row in requirements
                if row['saved_status'] != 'VERIFIED_SAVED_SOURCE']})
after = {key: digest(path) for key, path in originals.items()}
body = {'record_type': 'ISSUE28_NORMAL_SOURCE_DISCOVERY_LEGACY_DISABLED',
    'tested_product_head': '76ebe42ea28eedaac640c70d127475296361d1f3',
    'company_count': len(rows), 'companies': rows,
    'old_semantic_exports_disabled': disabled,
    'original_claims_source_and_active_unchanged': before == after,
    'new_real_calls': [0, 0, 0],
    'all39_metric_result_acceptance': False,
    'new_fiscal_year_online_update_proven': False}
(HERE/'result.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'company_count': len(rows),
    'statuses': {status: sum(row['status'] == status for row in rows)
        for status in sorted({row['status'] for row in rows})},
    'metadata_refresh_count': sum(len(row['metadata_refresh_urls']) for row in rows),
    'not_directly_saved_count': sum(len(row['not_directly_saved']) for row in rows),
    'old_exports_disabled': disabled}, sort_keys=True), flush=True)
assert len(rows) == 10 and disabled == 116
assert all(row['status'] == 'SAVED_SOURCE_DEPENDENCIES_AVAILABLE' for row in rows)
assert before == after
