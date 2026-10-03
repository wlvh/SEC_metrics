"""Check whether peer's FY2021 A05 recast finding affects our current JPM A05."""
import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from vnext.zero_ai_r2 import _load_deterministic_catalog

PEER = '94cbc3e7e6af372d0ad8349585241fdbd2d0ed4e'
PEER_FILE = 'scripts/vnext/historical_results.py'
PEER_REGISTER = 'docs/evidence/issue47_history/known_result_defects.json'
source = subprocess.check_output(['git', 'show', PEER + ':' + PEER_FILE],
                                 cwd=ROOT, text=True)
tree = ast.parse(source)
names = {'_paired_concept_lists', '_claim_view', 'paired_measure_problem'}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
         and node.name in names]
assert {node.name for node in nodes} == names
namespace = {'Decimal': Decimal, 'PAIRED_MEASURE_REASON':
             'NORMAL_PAIRED_MEASURE_NOT_COMPARABLE'}
exec(compile(ast.Module(body=nodes, type_ignores=[]), PEER_FILE, 'exec'), namespace)
peer_guard = namespace['paired_measure_problem']
register = json.loads(subprocess.check_output(
    ['git', 'show', PEER + ':' + PEER_REGISTER], cwd=ROOT, text=True))
assert any(d['defect_id'] ==
           'A05_JPMORGAN_2021_PRIOR_YEAR_ASSETS_AS_FIRST_REPORTED_AGAINST_A_RECAST'
           for d in register['defects'])


archive = ROOT / 'docs/evidence/issue28_continuous/ordinary-document-identity'
index = json.loads((archive / 'material-index.json').read_text())['files']
record_path = 'live-restored-jpm-native/runs/jpmorgan_chase/A05/records.jsonl'
record_meta = index[record_path]
with tarfile.open(archive / 'material.tar.gz') as saved:
    record_bytes = saved.extractfile(record_meta['archive_member']).read()
assert hashlib.sha256(record_bytes).hexdigest() == record_meta['sha256']
records = [json.loads(line) for line in record_bytes.splitlines()]
selected_claims = [r for r in records
                   if r['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM']
assert len(selected_claims) == 3
metric = next(r for r in records if r['record_type'] == 'METRIC_RESULT'
              and r['metric_id'] == 'A05')
source_reference = next(r for r in records if r['record_type'] == 'SOURCE_REFERENCE'
                        and r['source_role'] == 'companyfacts'
                        and r['accession'] == '0001628280-26-008131')
fact_path = next(path for path, meta in index.items()
                 if path.startswith('live-restored-jpm-native/data/jpmorgan_chase/')
                 and meta.get('repository_path', '').endswith(
                     '/' + source_reference['document_name'])
                 and 'sha256:' + meta['sha256'] == source_reference['raw_asset_id'])
fact_meta = index[fact_path]
fact_bytes = (ROOT / fact_meta['repository_path']).read_bytes()
assert hashlib.sha256(fact_bytes).hexdigest() == fact_meta['sha256']
fact = json.loads(fact_bytes)
current_claims = [{'locator': {'concept': 'Assets', 'period_start': row['end'],
                               'period_end': row['end']},
                   'attributes': {'accession': row['accn']},
                   'unit': 'USD', 'value': str(row['val'])}
                  for row in fact['facts']['us-gaap']['Assets']['units']['USD']
                  if row['accn'] == source_reference['accession']
                  and row['end'] == '2024-12-31']
assert len(current_claims) == 1
route = _load_deterministic_catalog(repo_root=ROOT)['metrics']['A05']
accessions = {'current': '0001628280-26-008131',
              'prior': '0000019617-25-000270'}
problem, bridged = peer_guard(
    route=route, claims=selected_claims,
    current_claims=current_claims,
    accessions=accessions)
current_root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
ledger = current_root.parent / 'claims.jsonl'
source_log = current_root / 'evidence/requests_log.csv'
before = tuple(hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (ledger, source_log))
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    current = resolve_ordinary_companyfacts_metrics(
        repo_root=current_root, company_id='jpmorgan_chase')
assert before == tuple(hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (ledger, source_log))
current_a05 = current['metrics']['A05']
current_accessions = {'current': current['filings']['current']['accessionNumber'],
                      'prior': current['filings']['prior']['accessionNumber']}
current_problem, current_bridged = peer_guard(
    route=route, claims=current_a05['claims'],
    current_claims=current['claims_by_accession_role']['current'],
    accessions=current_accessions)
assert current['prior_error'] is None
assert current_a05['result']['value'] == metric['value']
assert current_problem is None and problem is None
body = {'record_type': 'ISSUE28_A05_CURRENT_JPM_PEER_RECAST_IMPACT',
        'peer_fixed_commit': PEER,
        'peer_register_git_blob': subprocess.check_output(
            ['git', 'rev-parse', PEER + ':' + PEER_REGISTER], cwd=ROOT,
            text=True).strip(),
        'peer_guard_git_blob': subprocess.check_output(
            ['git', 'rev-parse', PEER + ':' + PEER_FILE], cwd=ROOT,
            text=True).strip(),
        'company_id': 'jpmorgan_chase',
        'period_end': metric['period_end'],
        'current_result_id': metric['result_id'],
        'current_value': metric['value'],
        'current_reason_code': metric['reason_code'],
        'archive_record_sha256': record_meta['sha256'],
        'companyfacts_raw_asset_id': source_reference['raw_asset_id'],
        'selected_claims': [{'concept': c['locator']['concept'],
                             'value': str(c['value']),
                             'accession': c['attributes']['accession'],
                             'period_start': c['locator']['period_start'],
                             'period_end': c['locator']['period_end']}
                            for c in selected_claims],
        'target_filing_prior_assets': current_claims[0]['value'],
        'accessions': accessions,
        'peer_guard_problem': problem,
        'peer_bridge_count': len(bridged),
        'current_cumulative_source_root': str(current_root),
        'current_resolver_prior_error': current['prior_error'],
        'current_resolver_a05_result_id': current_a05['result']['result_id'],
        'current_resolver_a05_value': current_a05['result']['value'],
        'current_resolver_a06_reason': current['metrics']['A06']['result']['reason_code'],
        'current_resolver_peer_guard_problem': current_problem,
        'current_resolver_peer_bridge_count': len(current_bridged),
        'current_and_archive_result_id_same':
            current_a05['result']['result_id'] == metric['result_id'],
        'ledger_and_source_log_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'peer_result_credit_not_copied': True,
        'scope_limit': 'One archived JPM FY2025 A05 native Run and independently rebuilt current cumulative #28 source graph; old repository source root conflict is not current cumulative root, peer FY2021 Result not imported.'}
(HERE / 'impact.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'period_end': body['period_end'],
                  'current_value': body['current_value'],
                  'peer_guard_problem': problem,
                  'new_real_calls': [0, 0, 0]}))
