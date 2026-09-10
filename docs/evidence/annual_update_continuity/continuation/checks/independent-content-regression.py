"""Independent offline V9 content checks over preserved PR38 source/response.
No execution/qualification/publication credit; validators are never mocked.
"""
from pathlib import Path
import copy
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

ROOT = Path('/Users/lyuhongwang/Developer/SEC_metrics')
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.annual_regression import _fixture, AUDIT
from vnext.annual_regression_synthetic import header_case
from vnext.annual_evidence import check_annual_evidence, policy_choice
from vnext.reader import validate_reader_output
from vnext.canonical import content_hash, sha256_file, strict_json_file, strict_json_loads
from vnext.annual_continuity import code_identity, _requirement
from vnext.annual_runtime import verify_data_root
from vnext.sources import source_reference_record
from vnext.reader_input import build_reader_input_manifest, prepare_reader_request
from vnext.requirements import load_requirement_snapshot
from vnext.sources import load_raw_blob_bytes
from vnext.table_grid import build_table_grid
from vnext.records import validate_record

def file_proof(path):
    return {'path': str(path), 'sha256': sha256_file(path=path), 'size': path.stat().st_size}

code = code_identity()
requirement = _requirement()
assert requirement['requirement_id'] == 'issue_28_v8'
choice = policy_choice(requirement)
authority_root = ROOT
old = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v5')
records, attempt, response_path, payload = _fixture(ROOT)
grid = next(r for r in records if r['record_type'] == 'DERIVED_ASSET')
manifest = next(r for r in records if r['record_type'] == 'READER_INPUT_MANIFEST')
raw = next(r for r in records if r['record_type'] == 'RAW_BLOB')
sources = [r for r in records if r['record_type'] == 'SOURCE_REFERENCE']
period = strict_json_file(path=ROOT / AUDIT / 'manifest.json')['target_period']
task = payload['task_contract']
original_text = response_path.read_text()
original = strict_json_file(path=response_path)
original_files = [ROOT / AUDIT / 'records.jsonl', ROOT / AUDIT / 'manifest.json', response_path,
                  ROOT / AUDIT / attempt['reader_payload_path'], ROOT / raw['storage_uri']]
before = [file_proof(p) for p in original_files]
source_bytes = load_raw_blob_bytes(repo_root=ROOT, raw_blob=raw)
rebuilt_grid = build_table_grid(html_bytes=source_bytes,
    parent_raw_asset_ids=grid['parent_raw_asset_ids'], storage_uri=grid['storage_uri'])
assert rebuilt_grid == grid, 'Original DerivedAsset differs from complete original source reparse'
for item in [raw, grid, manifest, *sources]:
    assert validate_record(record=item) == item

cases = []

def evaluate(name, body, *, source_override=None, target_override=None, selected_requirement=None, expected='REJECTED'):
    candidate = evidence = None
    rejected_at = None
    try:
        candidate = validate_reader_output(response_text=body if isinstance(body, str) else json.dumps(body),
            attempt_id=attempt['attempt_id'], required_roles=task['required_roles'],
            scope_contract=task['scope_contract'], source_reference_ids=manifest['source_reference_ids'],
            derived_asset_ids=[grid['derived_asset_id']])
        evidence = check_annual_evidence(requirement=requirement if selected_requirement is None else selected_requirement,
            target_period=period if target_override is None else target_override, candidate=candidate,
            derived_asset=grid, reader_manifest=manifest, reader_payload_body=payload,
            source_references=sources if source_override is None else source_override,
            identity_constraints=task['identity_constraints'], scope_contract=task['scope_contract'])
        observed, reasons = evidence['status'], evidence['reason_codes']
        rejected_at = 'EVIDENCE' if observed != 'PASS' else None
    except ValueError as error:
        observed, reasons = 'REJECTED', [str(error)]
        rejected_at = 'READER' if candidate is None else 'EVIDENCE_EXCEPTION'
    cases.append({'case': name, 'expected': expected, 'observed': observed,
        'reason_codes': reasons, 'rejected_at': rejected_at,
        'response_was_original_bytes': isinstance(body, str) and body == original_text,
        'evidence_check_id': None if evidence is None else evidence['evidence_check_id'],
        'system_approval_eligible': None if evidence is None else evidence['system_approval_eligible']})
    if name == 'original_response_current_V9':
        assert candidate is not None and evidence is not None
        for suffix, value in [('candidate', candidate), ('evidence', evidence)]:
            (OUT / ('independent-content-original-' + suffix + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')

# These two cases use exactly the same original response text without trimming.
evaluate('original_response_retained_V6_raw_rule', original_text, selected_requirement=old)
evaluate('original_response_current_V9', original_text, expected='PASS')
table = next(t for t in grid['tables'] if t['table_id'] == original['candidates'][0]['locator']['table_id'])
def cell(row, col):
    return next(c for c in table['rows'][row]['cells'] if c['column_index'] == col)
def locator(row, col):
    c = cell(row, col)
    return {'derived_asset_id': grid['derived_asset_id'], 'table_id': table['table_id'],
        **{k:c[k] for k in ('row_index','column_index','origin_row_index','origin_column_index','rowspan','colspan')}}
def mutate(name, fn):
    value = copy.deepcopy(original)
    fn(value, value['candidates'][0])
    evaluate(name, value)

mutate('wrong_numeric_value', lambda b,c:c.update(claimed_raw_value='0'))
mutate('wrong_unit', lambda b,c:c.update(claimed_reported_unit='ratio'))
mutate('wrong_claim_period', lambda b,c:c.update(claimed_period='FY' + str(period['fiscal_year'] - 1)))
mutate('wrong_period_column', lambda b,c:c.update(locator=locator(26,21), claimed_raw_value=cell(26,21)['text']))
mutate('wrong_table', lambda b,c:c['locator'].update(table_id=grid['tables'][0]['table_id']))
mutate('wrong_origin_geometry', lambda b,c:c['locator'].update(origin_row_index=0))
mutate('wrong_scope_footnote_2_to_3', lambda b,c:c['scope_evidence_locators'][1].update(raw_text='Worldwide (3)'))
mutate('unknown_scope_alias', lambda b,c:c['claimed_scope'][2].update(raw_value='Worldwide (2)'))
mutate('wrong_operating_scope', lambda b,c:c['claimed_scope'][1].update(raw_value='Company-operated'))
mutate('different_row_same_label', lambda b,c:c['scope_evidence_locators'][1].update(locator=locator(17,0)))
mutate('wrong_region_value', lambda b,c:c.update(locator=locator(19,15), claimed_raw_value=cell(19,15)['text']))
assert original['candidates'][0]['claimed_raw_value'].strip() == '69.3' and cell(17,15)['text'].strip() == '69.5'
def wrong_group(b,c):
    c.update(locator=locator(17,15), claimed_raw_value=cell(17,15)['text'])
    c['scope_evidence_locators'][1]['locator'] = locator(17,0)
mutate('wrong_group_original_69_5_vs_69_3', wrong_group)
mutate('caller_added_whitespace', lambda b,c:c['scope_evidence_locators'][1].update(raw_text='Worldwide  (2)'))
mutate('conflicting_claims', lambda b,c:b.update(unresolved_competing_claims=[{'description':'scope conflict'}]))
evaluate('source_reference_missing', original_text, source_override=[])
foreign_run = ROOT / 'artifacts/vnext/qualification/cycles/0c4569437b1bac3ad353394c8d8b1f59b1a1ee7c229c8fa5ee51a22269b6a448/runs/6f40df80eb602219bc9137a946c4da81ae215f413bc157d712a0289a4871161d'
foreign_records = [strict_json_loads(text=line) for line in (foreign_run/'records.jsonl').read_text().splitlines()]
foreign_sources = [r for r in foreign_records if r['record_type']=='SOURCE_REFERENCE']
assert foreign_sources and foreign_sources != sources
for item in foreign_sources: validate_record(record=item)
evaluate('foreign_real_FY2024_source_reference', original_text, source_override=foreign_sources)
wrong_period = {**period,'fiscal_year':period['fiscal_year'] - 1,
    'period_start':str(period['fiscal_year'] - 1) + '-01-01','period_end':str(period['fiscal_year'] - 1) + '-12-31'}
evaluate('wrong_native_target_period', original_text, target_override=wrong_period)
for name in ('synthetic_supported_header','conflicting_year_header','conflicting_role_header','same_value_prior_year','conflicting_year_with_row_stub'):
    args = header_case(repo_root=authority_root, records=records, attempt=attempt, original=original, period=period, variant=name)
    evidence = check_annual_evidence(requirement=requirement, target_period=period, **args)
    cases.append({'case':name,'expected':'PASS' if name=='synthetic_supported_header' else 'REJECTED',
        'observed':evidence['status'],'reason_codes':evidence['reason_codes'],
        'evidence_scope':'SYNTHETIC_GRAPH_ONLY_NO_SOURCE_RUN_OR_REQUEST_CREDIT'})

# New strict same-value group counterexample, clearly synthetic and no SEC credit.
import html
claim = original['candidates'][0]
group = html.escape(claim['scope_evidence_locators'][0]['raw_text'])
geo = html.escape(claim['scope_evidence_locators'][1]['raw_text'])
number = html.escape(claim['claimed_raw_value'])
html_bytes = (f'<table><tr><td></td><td colspan="2">Occupancy</td></tr>'
    f'<tr><td></td><td colspan="2">{period["fiscal_year"]}</td></tr>'
    f'<tr><td>{group}</td><td></td><td></td></tr>'
    f'<tr><td>{geo}</td><td>{number}</td><td>%</td></tr>'
    '<tr><td>Comparable Company-Operated Properties</td><td></td><td></td></tr>'
    f'<tr><td>{geo}</td><td>{number}</td><td>%</td></tr></table>').encode()
synthetic_raw = {'record_type':'RAW_BLOB','raw_asset_id':'sha256:'+hashlib.sha256(html_bytes).hexdigest(),
    'byte_length':len(html_bytes),'media_type':'text/html','storage_uri':'evidence/SYNTHETIC-same-value-groups.html'}
synthetic_grid = build_table_grid(html_bytes=html_bytes,parent_raw_asset_ids=[synthetic_raw['raw_asset_id']],
    storage_uri='artifacts/SYNTHETIC-same-value-groups.json')
synthetic_source = source_reference_record(raw_blob=synthetic_raw, **{k:sources[0][k] for k in
    ('company_id','source_url','accession','document_name','source_role','request_attempt_id')})
synthetic_manifest = build_reader_input_manifest(derived_asset=synthetic_grid,source_reference_ids=[synthetic_source['source_reference_id']])
synthetic_request = prepare_reader_request(repo_root=authority_root,task_contract_id=attempt['task_contract_id'],
    manifest=synthetic_manifest,derived_asset=synthetic_grid)
synthetic_payload=json.loads(synthetic_request.request_bytes);synthetic_task=synthetic_payload['task_contract']
synthetic_table=synthetic_grid['tables'][0]
def sloc(row,col):
    c=synthetic_table['rows'][row]['cells'][col]
    return {'derived_asset_id':synthetic_grid['derived_asset_id'],'table_id':synthetic_table['table_id'],
        **{k:c[k] for k in ('row_index','column_index','origin_row_index','origin_column_index','rowspan','colspan')}}
assert synthetic_table['rows'][3]['cells'][1]['text']==synthetic_table['rows'][5]['cells'][1]['text']==claim['claimed_raw_value']
for name,row,expected in [('synthetic_same_value_correct_group',3,'PASS'),('synthetic_same_value_wrong_group',5,'REJECTED')]:
    body=copy.deepcopy(original)
    body['table_locator']={'derived_asset_id':synthetic_grid['derived_asset_id'],'table_id':synthetic_table['table_id']}
    c=body['candidates'][0];c['locator']=sloc(row,1)
    c['scope_evidence_locators'][0]['locator']=sloc(2,0)
    c['scope_evidence_locators'][1]['locator']=sloc(row,0)
    candidate=validate_reader_output(response_text=json.dumps(body),attempt_id=attempt['attempt_id'],
        required_roles=synthetic_task['required_roles'],scope_contract=synthetic_task['scope_contract'],
        source_reference_ids=synthetic_manifest['source_reference_ids'],derived_asset_ids=[synthetic_grid['derived_asset_id']])
    evidence=check_annual_evidence(requirement=requirement,target_period=period,candidate=candidate,
        derived_asset=synthetic_grid,reader_manifest=synthetic_manifest,reader_payload_body=synthetic_payload,
        source_references=[synthetic_source],identity_constraints=synthetic_task['identity_constraints'],scope_contract=synthetic_task['scope_contract'])
    cases.append({'case':name,'expected':expected,'observed':evidence['status'],'reason_codes':evidence['reason_codes'],
        'same_numeric_value':'69.3','evidence_scope':'SYNTHETIC_GRAPH_NO_SEC_SOURCE_RUN_OR_REQUEST_CREDIT'})
    (OUT/(name+'.json')).write_text(json.dumps({'synthetic_html':html_bytes.decode(),'response':body,'candidate':candidate,'evidence':evidence},ensure_ascii=False,indent=2,default=str)+'\n')

assert [file_proof(p) for p in original_files] == before, 'Original source/response/Run files changed'
assert code_identity() == code, 'Reviewed code changed during regression'
passed = all(c['expected']==c['observed'] for c in cases)
receipt = {'record_type':'INDEPENDENT_CONTINUITY_CONTENT_REGRESSION','reviewer_kind':'INDEPENDENT_MODEL_SUBTASK',
    'reviewer_task':'/root/runtime_boundary_review','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
    'status':'PASS' if passed else 'FAIL','head':code['exact_head'],'runtime_tree':code['runtime_tree'],'test_tree':code['test_tree'],
    'requirement':{k:requirement[k] for k in ('requirement_id','requirement_generation','requirement_closure_hash','hashes')},
    'policy_choice_hash':content_hash(value=choice),'policy_file':file_proof(ROOT/'config/annual_candidate_adoption_v3.json'),
    'validators':[file_proof(ROOT/'scripts/vnext'/name) for name in ('annual_evidence.py','evidence.py','reader.py','table_grid.py','scope_contract.py','annual_regression.py','annual_regression_synthetic.py')],
    'original_files_before_after_equal':True,'original_files':before,'foreign_source_records':file_proof(foreign_run/'records.jsonl'),
    'original_full_source_sha256':hashlib.sha256(source_bytes).hexdigest(),'original_grid_rebuilt_byte_structure_equal':True,
    'derived_asset_id':grid['derived_asset_id'],'reader_input_manifest_id':manifest['reader_input_manifest_id'],
    'original_target_period':period,'cases':cases,'case_count':len(cases),
    'same_value_wrong_group_verified_equal':True,
    'legacy_case_name_limit':{'case':'same_numeric_value_wrong_group','actual_original_target':'69.3','actual_foreign_group_value':'69.5','scope':'Old name did not prove equal-number wrong-group. Historical files untouched; this run records its precise scope and adds a true equal-number synthetic case.'},
    'attempt_1':{'script':file_proof(BASE/'independent-content-regression-attempt-1.py'),'log':file_proof(BASE/'independent-content-regression.log'),'status':'FAILED_REVIEWER_ASSERTION_EXPOSED_OLD_CASE_NAME_LIMIT'},
    'synthetic_request_authority_data_root':str(authority_root),'source_request_or_history_modified':False,
    'no_validator_mocks':True,'new_provider_paid_sec_calls':[0,0,0],
    'actual_execution_scope':'OS readonly.sb with deny network; current true reader/Evidence validators and original complete source parser. Only external audit artifacts and in-memory negative copies.',
    'credit':{'qualification':'NONE','native_Run':'NONE_CREATED','provider_response':'NO_NEW_RESPONSE','publication':'NONE','production_permission':'NONE'},
    'evidence_limit':'This proves current V9 routes the preserved known FY2025 response and rejects these explicit counterexamples. It does not prove unseen-material generalization, a new provider outcome, whole continuity acceptance, or production publication.',
    'script':file_proof(Path(__file__))}
receipt['regression_id'] = content_hash(value=receipt)
(OUT/'independent-content-regression.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'status':receipt['status'],'regression_id':receipt['regression_id'],'head':code['exact_head'],'cases':cases},ensure_ascii=False))
if not passed:raise SystemExit(1)
