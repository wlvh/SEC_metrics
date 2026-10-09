"""Create an Enphase private no-network C02 successor Run from saved originals."""
import csv
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import sha256_file
from vnext.normal_run_v3 import install_normal_inputs, create_normal_run
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot

WORK = Path('/private/tmp/issue28-c02-composition-enphase-v3-20261001')
DATA = WORK / 'data'
RUN = WORK / 'run'
SOURCE_LOG = ROOT / 'evidence/requests_log.csv'
assert not WORK.exists()
before = sha256_file(path=SOURCE_LOG)
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v13')
with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen', side_effect=AssertionError('HTTP_FORBIDDEN'))):
    case = install_normal_inputs(data_root=DATA,
        company_id='enphase_energy', metric_id='C02',
        c02_composition=True)
    created = create_normal_run(data_root=DATA, run_dir=RUN,
        company_id='enphase_energy', metric_id='C02',
        c02_composition=True)
    rendered = render_ordinary_run(data_root=DATA, run_dir=RUN)
assert before == sha256_file(path=SOURCE_LOG)
result = created['result']
candidate = next(json.loads(line) for line in (RUN / 'records.jsonl').read_text().splitlines()
                 if json.loads(line)['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
blocks = {x['block_index'] for x in candidate['selected'].values()}
assert 294 not in blocks and 210 in blocks
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
assert 'A Board member (when requested), together with our General Counsel' not in result['value']
matrix = next(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
assert matrix['metric_id'] == 'C02' and matrix['status'] == 'TEXT_QUAL'
body = {
    'record_type': 'ISSUE28_C02_COMPOSITION_PRIVATE_RUN',
    'company_id': 'enphase_energy', 'period_end': result['period_end'],
    'requirement_closure_hash': requirement['requirement_closure_hash'],
    'installed_case_spec': case['spec_paths']['C02'],
    'run_id': created['manifest']['run_id'], 'result_id': result['result_id'],
    'publication': result['publication'], 'quality': result['quality'],
    'candidate_count': len(blocks),
    'excluded_known_wrong_block_294': True,
    'included_director_nomination_block_210': True,
    'public_row_status': matrix['status'],
    'source_log_unchanged': True, 'calls': [0, 0, 0],
    'full_content_independently_reviewed': False,
    'full_390_or_production_credit': False,
}
(HERE / 'enphase-summary.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(body, sort_keys=True), flush=True)
