"""Bounded current-source A05 impact check for the fixed peer recast guard."""
import ast
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
SOURCE = ACQUIRED / 'source-inputs'
PEER = '94cbc3e7e6af372d0ad8349585241fdbd2d0ed4e'
FILE = 'scripts/vnext/historical_results.py'
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from vnext.zero_ai_r2 import _load_deterministic_catalog

tree = ast.parse(subprocess.check_output(['git', 'show', PEER + ':' + FILE],
                                         cwd=ROOT, text=True))
names = {'_paired_concept_lists', '_claim_view', 'paired_measure_problem'}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
         and node.name in names]
assert {node.name for node in nodes} == names
scope = {'Decimal': Decimal, 'PAIRED_MEASURE_REASON':
         'NORMAL_PAIRED_MEASURE_NOT_COMPARABLE'}
exec(compile(ast.Module(body=nodes, type_ignores=[]), FILE, 'exec'), scope)
peer_guard = scope['paired_measure_problem']
route = _load_deterministic_catalog(repo_root=ROOT)['metrics']['A05']
companies = [row['company_id'] for row in csv.DictReader(
    (ROOT/'config/company_registry.csv').open())]
assert len(companies) == len(set(companies)) == 10
protected = (ACQUIRED/'claims.jsonl', SOURCE/'evidence/requests_log.csv')
before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
rows = []
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for company in companies:
        candidate = resolve_ordinary_companyfacts_metrics(
            repo_root=SOURCE, company_id=company)
        metric = candidate['metrics']['A05']
        accessions = {'current': candidate['filings']['current']['accessionNumber'],
                      'prior': (candidate['filings']['prior'] or {}).get('accessionNumber')}
        problem, bridged = peer_guard(
            route=route, claims=metric['claims'],
            current_claims=candidate['claims_by_accession_role']['current'],
            accessions=accessions)
        rows.append({'company_id': company,
                     'period_end': metric['result']['period_end'],
                     'result_id': metric['result']['result_id'],
                     'value': metric['result']['value'],
                     'reason_code': metric['result']['reason_code'],
                     'selected_claim_count': len(metric['claims']),
                     'selected_claims': [
                         {'concept': claim['locator']['concept'],
                          'period_end': claim['locator']['period_end'],
                          'accession': claim['attributes']['accession'],
                          'value': str(claim['value'])}
                         for claim in metric['claims']],
                     'accessions': accessions,
                     'peer_guard_problem': problem,
                     'peer_bridge_count': len(bridged),
                     'prior_error': candidate['prior_error']})
after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
assert before == after
body = {'record_type': 'ISSUE28_CURRENT_TEN_A05_PEER_RECAST_IMPACT',
        'peer_fixed_commit': PEER,
        'source_root': str(SOURCE),
        'rows': rows,
        'numeric_a05_count': sum(row['value'] is not None for row in rows),
        'peer_guard_new_problem_company_ids': [row['company_id'] for row in rows
            if row['value'] is not None and row['peer_guard_problem'] is not None],
        'source_log_and_claim_ledger_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'scope_limit': 'Ten current #28 A05 source candidates under current cumulative source root; no new native Run or independent full content acceptance.'}
(HERE/'current-ten.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'numeric_a05_count': body['numeric_a05_count'],
                  'new_problem_company_ids':
                  body['peer_guard_new_problem_company_ids'],
                  'new_real_calls': [0, 0, 0]}), flush=True)
