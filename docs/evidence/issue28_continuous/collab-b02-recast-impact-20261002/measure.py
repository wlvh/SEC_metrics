"""Compare #28 current B02 saved-source claims with the fixed peer recast guard."""
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
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics
from vnext.paired_measure_v1 import paired_measure_problem as current_guard

PEER = '49b4127127ec04828b872f08b5b1adf51fb17419'
PEER_FILE = 'scripts/vnext/historical_results.py'
PEER_GIT_BLOB = subprocess.check_output(
    ['git', 'rev-parse', PEER + ':' + PEER_FILE], cwd=ROOT, text=True).strip()
source = subprocess.check_output(['git', 'show', PEER + ':' + PEER_FILE], cwd=ROOT,
                                 text=True)
tree = ast.parse(source)
names = {'_paired_concept_lists', '_claim_view', 'paired_measure_problem'}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
         and node.name in names]
assert {node.name for node in nodes} == names
namespace = {'Decimal': Decimal, 'PAIRED_MEASURE_REASON':
             'NORMAL_PAIRED_MEASURE_NOT_COMPARABLE'}
exec(compile(ast.Module(body=nodes, type_ignores=[]), PEER_FILE, 'exec'), namespace)
peer_guard = namespace['paired_measure_problem']


def sha(data):
    return hashlib.sha256(data).hexdigest()


companies = [row['company_id'] for row in csv.DictReader(
    (ROOT / 'config/company_registry.csv').open())]
assert len(companies) == len(set(companies)) == 10
route = json.loads((ROOT / 'catalog/deterministic_metrics.json').read_text())['metrics']['B02']
ledger = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/claims.jsonl')
source_log = ROOT / 'evidence/requests_log.csv'
before = sha(ledger.read_bytes()), sha(source_log.read_bytes())
rows = []
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    for company in companies:
        candidate = resolve_ordinary_companyfacts_metrics(repo_root=ROOT,
                                                            company_id=company)
        b02 = candidate['metrics']['B02']
        accessions = {'current': candidate['prepared_input']['filing']['accessionNumber'],
                      'prior': (candidate['filings']['prior'] or {}).get('accessionNumber')}
        args = {'route': route, 'claims': b02['claims'],
                'current_claims': candidate['claims_by_accession_role']['current'],
                'accessions': accessions}
        old_problem, old_bridged = current_guard(**args)
        peer_problem, peer_bridged = peer_guard(**args)
        row = {'company_id': company,
               'period_end': b02['result']['period_end'],
               'current_result_id': b02['result']['result_id'],
               'current_value': b02['result']['value'],
               'current_reason_code': b02['result']['reason_code'],
               'current_accession': accessions['current'],
               'prior_accession': accessions['prior'],
               'selected_claim_count': len(b02['claims']),
               'old_guard_problem': old_problem,
               'peer_same_concept_guard_problem': peer_problem,
               'old_bridge_count': len(old_bridged),
               'peer_bridge_count': len(peer_bridged)}
        rows.append(row)
after = sha(ledger.read_bytes()), sha(source_log.read_bytes())
assert before == after
body = {'record_type': 'ISSUE28_B02_CURRENT_SOURCE_PEER_RECAST_IMPACT',
        'peer_fixed_commit': PEER, 'peer_guard_git_blob': PEER_GIT_BLOB,
        'own_guard_path': 'scripts/vnext/paired_measure_v1.py',
        'rows': rows,
        'positive_current_b02_count': sum(row['current_value'] is not None for row in rows),
        'newly_withheld_by_peer_guard': [row['company_id'] for row in rows
                                         if row['old_guard_problem'] is None
                                         and row['peer_same_concept_guard_problem'] is not None],
        'ledger_and_source_log_unchanged': True, 'new_real_calls': [0, 0, 0],
        'peer_result_credit_not_copied': True,
        'scope_limit': 'Ten current saved-source B02 candidate graphs only; no historic years or new Run/Result.'}
(HERE / 'impact.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'current_positive': body['positive_current_b02_count'],
                  'newly_withheld': body['newly_withheld_by_peer_guard'],
                  'new_real_calls': [0, 0, 0]}))
