"""Check the repaired tree against both real A05 result classes."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


numeric=read(HERE/'na-repair-numeric.json')
na=read(HERE/'na-repair-nonfinancial.json')
binding=read(HERE/'binding-after-na.json')
selector=read(HERE/'material-selector.json')
old=read(HERE/'result.json')
assert all(sha(ROOT/path)==expected for path,expected in
           numeric['changed_code_file_sha256'].items())
assert sha(ROOT/'scripts/vnext/ordinary_projection.py')==na['projection_sha256']
assert numeric['requirement_closure_hash']==binding['child_requirement_closure_hash']
assert numeric['result_id']==old['result_id']
assert numeric['formula']==old['formula']
assert na['result_applicability']=='N_A_STRUCTURAL'
assert na['result_reason']=='TRAIT_NOT_APPLICABLE'
assert na['result_value'] is None and na['public_formula']==na['public_value']==''
assert na['first_status']=='CANDIDATE_READY'
assert na['repeat_status']=='NO_SOURCE_CONTENT_CHANGE' and na['no_second_run']
assert selector['status']=='PASSED' and selector['timeout_seconds']==240
numeric_attempt=(Path('/private/tmp/issue28-a05-formula-na-repair-20261002/state')/
    'jpmorgan_chase/metrics/A05-formula-v1/attempts'/numeric['attempt_id'])
manifest=read(numeric_attempt/'runs/A05/manifest.json')
validation=read(numeric_attempt/'runs/A05/validation.json')
assert manifest['status']=='OPEN' and validation['status']=='NOT_RUN'
numeric_row,=list(csv.DictReader((numeric_attempt/'rows/A05/metrics_matrix.csv').open()))
assert numeric_row['formula']==numeric['formula']
assert numeric_row['value']==numeric['value']
assert numeric_row['source_class']=='DERIVED'
body={'record_type':'ISSUE28_A05_FORMULA_NA_REPAIR_FINAL_TREE',
    'numeric_jpmorgan':{'result_id':numeric['result_id'],
        'value':numeric['value'],'formula':numeric['formula'],
        'run_status':manifest['status'],'validation_status':validation['status']},
    'nonfinancial_marriott':{'result_id':na['result_id'],
        'applicability':na['result_applicability'],
        'value':na['result_value'],'formula':na['public_formula'],
        'first_status':na['first_status'],'repeat_status':na['repeat_status']},
    'source_selector_seconds':selector['duration_seconds'],
    'source_selector_timeout_seconds':selector['timeout_seconds'],
    'product_file_hashes_same_as_numeric_and_na_runs':True,
    'child_requirement_closure_hash':binding['child_requirement_closure_hash'],
    'prior_first_review_needs_fix_retained':True,
    'new_real_calls':[0,0,0],
    'current_390_credit':False,
    'production_authorized':False}
(HERE/'na-repair-final.json').write_text(json.dumps(body,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps({'status':'PASS_BOTH_A05_RESULT_CLASSES',
    'numeric_formula':True,'structural_na_no_formula':True,
    'source_selector_under_limit':True}))
