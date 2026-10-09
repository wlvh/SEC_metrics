"""Prove the new A05 row differs only in its bound formula explanation."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OLD_EVIDENCE = ROOT/'docs/evidence/issue28_continuous/ordinary-jpm-a05-current-20261002'
old = json.loads((OLD_EVIDENCE/'result.json').read_text())
new = json.loads((HERE/'result.json').read_text())
cold = json.loads((HERE/'cold.json').read_text())
prior = json.loads((HERE/'old-runtime.json').read_text())
fast = json.loads((HERE/'fast-summary.json').read_text())
negative = json.loads((HERE/'negative.json').read_text())
old_attempt = (Path('/private/tmp/issue28-jpm-a05-current-20261002/state')/
    'jpmorgan_chase/metrics/A05/attempts'/old['attempt_id'])
new_attempt = (Path('/private/tmp/issue28-a05-formula-successor-20261002/state')/
    'jpmorgan_chase/metrics/A05-formula-v1/attempts'/new['attempt_id'])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


old_rows = old_attempt/'rows/A05'
new_rows = new_attempt/'rows/A05'
old_row, = list(csv.DictReader((old_rows/'metrics_matrix.csv').open()))
new_row, = list(csv.DictReader((new_rows/'metrics_matrix.csv').open()))
changed = {key:{'old':old_row[key],'new':new_row[key]}
           for key in old_row if old_row[key] != new_row[key]}
assert set(changed) == {'formula'} and old_row['formula'] == ''
assert new_row['formula'] == new['formula'] == cold['formula']
assert old_row['value'] == new_row['value'] == new['result_value']
assert ((old_rows/'metric_evidence.csv').read_bytes() ==
        (new_rows/'metric_evidence.csv').read_bytes())
assert old['result_id'] == new['result_id'] == cold['result_id']
assert prior['old_row_sha256'] == sha(old_rows/'metrics_matrix.csv')
assert cold['public_row_sha256'] == new['public_row_sha256'] == sha(
    new_rows/'metrics_matrix.csv')
assert fast['suite_status'] == 'PASSED' and fast['selector_count'] == 146
assert negative['valid_native_replay_passed'] and len(negative['checks']) == 4
assert all(sha(ROOT/path) == digest for path,digest in
           new['changed_code_file_sha256'].items())
new_validation = json.loads((new_attempt/'runs/A05/validation.json').read_text())
assert new_validation['status'] == 'NOT_RUN'
body = {'record_type':'ISSUE28_A05_FORMULA_SUCCESSOR_FINAL_TREE_CHECK',
    'product_file_hashes_same_as_private_run':True,
    'old_and_new_result_id':new['result_id'],
    'public_row_changed_fields':changed,
    'public_evidence_csv_exactly_same':True,
    'old_installed_runtime_read':True,
    'cold_reentry_same_formula_and_row':True,
    'native_replay_negative_count':len(negative['checks']),
    'fast_selectors_passed':fast['selector_count'],
    'new_run_validation_status':new_validation['status'],
    'new_real_calls':[0,0,0],
    'current_390_credit':False,
    'production_authorized':False}
(HERE/'final-tree.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','only_changed_public_field':'formula',
    'evidence_csv_same':True,'fast':fast['selector_count'],
    'product_hashes_same':True}))
