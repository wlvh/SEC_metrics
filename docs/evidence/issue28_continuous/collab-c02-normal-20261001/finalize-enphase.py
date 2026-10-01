"""Read the already successful Run after the first receipt expected the wrong row label."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]

from vnext.canonical import sha256_file
from vnext.ordinary_projection import render_ordinary_run
from vnext.run_store import _mechanically_replay_open_run
from vnext.requirements import load_requirement_snapshot

WORK = Path('/private/tmp/issue28-c02-composition-enphase-v3-20261001')
DATA = WORK / 'data'
RUN = WORK / 'run'
manifest, records, _ = _mechanically_replay_open_run(
    run_dir=RUN, repo_root=DATA, require_complete_results=True)
rendered = render_ordinary_run(data_root=DATA, run_dir=RUN)
result = next(r for r in records if r.get('record_type') == 'METRIC_RESULT'
              and r.get('metric_id') == 'C02')
candidate = next(r for r in records if r.get('record_type') == 'DETERMINISTIC_TEXT_CANDIDATE')
blocks = {r['block_index'] for r in candidate['selected'].values()}
row = next(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
assert result['publication'] == 'PUBLISHED' and result['quality'] == 'EXACT'
assert row['metric_id'] == 'C02' and row['status'] == 'TEXT_QUAL'
assert len(blocks) == 35 and 294 not in blocks and 210 in blocks
source_log = 'evidence/requests_log.csv'
current_blob = subprocess.check_output(['git', 'hash-object', source_log],
                                       cwd=ROOT, text=True).strip()
head_blob = subprocess.check_output(['git', 'rev-parse', 'HEAD:' + source_log],
                                    cwd=ROOT, text=True).strip()
assert current_blob == head_blob
requirement = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v13')
assert manifest['requirement_closure_hash'] == requirement['requirement_closure_hash']
body = {'record_type': 'ISSUE28_C02_COMPOSITION_PRIVATE_RUN',
        'company_id': 'enphase_energy', 'period_end': result['period_end'],
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'run_id': manifest['run_id'], 'result_id': result['result_id'],
        'publication': result['publication'], 'quality': result['quality'],
        'candidate_count': len(blocks), 'excluded_known_wrong_block_294': True,
        'included_director_nomination_block_210': True,
        'public_row_status': row['status'], 'source_log_unchanged': True,
        'calls': [0, 0, 0], 'full_content_independently_reviewed': False,
        'full_390_or_production_credit': False,
        'evidence_script_first_failure': 'recorded-enphase.log expected internal EXACT instead of public TEXT_QUAL after the Run had succeeded',
        'source_log_sha256': sha256_file(path=ROOT / source_log)}
(HERE / 'enphase-summary.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'result_id': result['result_id'], 'run_id': manifest['run_id'],
                  'candidate_count': len(blocks), 'public': row['status']}, sort_keys=True))
