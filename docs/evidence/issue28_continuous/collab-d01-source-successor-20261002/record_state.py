"""Record the bounded #28 D01 successor without granting 390 or production credit."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
state_path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
state = json.loads(state_path.read_text())
register = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                       'known_result_defects.json').read_text())
binding = json.loads((HERE / 'binding-after-d01-successor.json').read_text())
measure = json.loads((HERE / 'measure-current.json').read_text())
fast = json.loads((HERE / 'fast-suite.json').read_text())
assert fast['status'] == 'PASSED' and len(fast['tests']) == 145
assert len(measure['rows']) == 10
assert [r['company_id'] for r in measure['rows'] if r.get('added') or r.get('removed')] == [
    'marriott_international', 'paramount_skydance_paramount_global']
assert register['current_trusted_summary']['newly_excluded_coordinate_count'] == 12
assert register['current_trusted_summary']['newly_excluded_result_id_count'] == 18
assert (HERE / 'native-final.exit').read_text().strip() == '0'
assert (HERE / 'native-marriott-final.exit').read_text().strip() == '0'
paramount = json.loads((HERE / 'final-paramount-private-update.json').read_text())
marriott = json.loads((HERE / 'final-marriott-private-update.json').read_text())
assert paramount['requirement_closure_hash'] == marriott['requirement_closure_hash'] == binding[
    'parent_requirement_closure_hash']
for short in ('paramount', 'marriott'):
    assert json.loads((HERE / ('final-' + short + '-cold-read.json')).read_text())[
        'result_id'] == json.loads((HERE / ('final-' + short + '-private-update.json')).read_text())[
            'result_id']
register['current_trusted_summary']['d01_private_successor']['final_bound_runs'] = {
    'paramount_run_id': paramount['run_id'],
    'marriott_run_id': marriott['run_id'],
    'requirement_closure_hash': binding['parent_requirement_closure_hash'],
    'cold_reads': 'BOTH_INDEPENDENT_PROCESS_PASS',
}
(ROOT / 'docs/evidence/issue28_continuous/known_result_defects.json').write_text(
    json.dumps(register, ensure_ascii=False, indent=2) + '\n')
state['collab_28_47_v1']['peer_read_commit'] = measure['fixed_peer_read']
state['collab_28_47_v1']['peer_register_git_blob'] = '7bf9d63d03a198409c668205135d50655dad1725'
state['d01_emphasis_successor_20261002'] = {
    'status': 'TWO_CURRENT_SAVED_SOURCE_DEFECTS_MAPPED_AND_PRIVATE_NATIVE_REPAIRS_PASS',
    'peer_read_commit': measure['fixed_peer_read'],
    'peer_source_paths': ['scripts/vnext/historical_text_emphasis.py',
                          'scripts/vnext/historical_risk_results.py'],
    'own_changed_functions': {
        'scripts/vnext/d01_emphasis_source.py': ['UnderlineBlocks',
                                                  'build_text_document_admitting_underline',
                                                  'join_headings_split_across_a_page'],
        'scripts/vnext/d01_emphasis_results.py': ['prepare_text_sources',
                                                   'create_deterministic_text_candidate',
                                                   'build_text_evidence',
                                                   'reviewed_text_observations',
                                                   'replay_text_result'],
        'scripts/vnext/normal_run_v3.py': ['prepare_case', 'install_normal_inputs',
                                           'create_normal_run', 'replay_case', 'text_api'],
        'scripts/vnext/ordinary_remaining_cases.py': ['prepare_current_source_case'],
        'scripts/vnext/ordinary_update_cycle.py': ['_descriptor', '_inspect', 'run_once'],
    },
    'shared_compatibility': 'New D01 parameter defaults false; default input binding and frozen V12 files unchanged. Explicit normal update chooses successor. Old installed Runs read by their own identity.',
    'bindings': binding,
    'current_saved_source_diff': {'companies_checked': 10,
                                  'changed_company_ids': ['marriott_international',
                                                          'paramount_skydance_paramount_global'],
                                  'other_eight_same_heading_text': True},
    'old_exact_result_ids_withdrawn': {
        'marriott_international': 'sha256:6077181e489edc0859d6420a2fea7d1d6384daab5f391fdfc4ee7597008b7762',
        'paramount_skydance_paramount_global': 'sha256:a7a52ae7df0eb150b4cc6cf66c08b508056febcfbd013ea7a9ec85026c144cca',
    },
    'new_final_private_result_ids': {
        'marriott_international': marriott['result_id'],
        'paramount_skydance_paramount_global': paramount['result_id'],
    },
    'native_status': 'BOTH_CANDIDATE_READY_AND_REPEAT_NO_SOURCE_CONTENT_CHANGE_AND_INDEPENDENT_PROCESS_COLD_READ',
    'tests': {'new_directed': 4, 'fast_selectors': 145},
    'limited_independent_review': 'PENDING_EXACT_PATCH_SHA',
    'trusted_summary': {'excluded_coordinates': 12, 'excluded_exact_result_ids': 18},
    'new_real_calls': [0, 0, 0],
    'current_390_credit': False, 'production_authorized': False,
    'evidence': 'docs/evidence/issue28_continuous/collab-d01-source-successor-20261002/',
}
state['ci_36908673854'] = {
    'head': 'af9e170958aa8907a70e33795c2b6896d9c84ecc',
    'run_id': 36908673854, 'conclusion': 'SUCCESS', 'jobs_successful': 16,
    'jobs_total': 16, 'updated_at_utc': '2026-10-01T21:15:29Z',
    'scope': 'Previous af9 head only; does not cover D01 successor edits.'}
relative = 'docs/evidence/issue28_continuous/execution-state.json'
base = subprocess.check_output(['git', 'show',
    'af9e170958aa8907a70e33795c2b6896d9c84ecc:' + relative], cwd=ROOT).decode()
start = base.rfind('"collab_28_47_v1": {')
assert start >= 0 and base.endswith('\n}\n')
before, collaboration = base[:start], base[start:-3]
collaboration = collaboration.replace(
    '"peer_read_commit": "48b46a2d742eb3e3b8bd5a6404908745046b5d2f"',
    '"peer_read_commit": "2b4f571ef18274299145c63b4c355aa97c45d030"', 1)
collaboration = collaboration.replace(
    '"peer_register_git_blob": "670cb629b1b557057132fe4aa7423f51a01bff84"',
    '"peer_register_git_blob": "7bf9d63d03a198409c668205135d50655dad1725"', 1)
assert collaboration != base[start:-3]
def entry(key):
    return '  ' + json.dumps(key, ensure_ascii=False) + ': ' + json.dumps(
        state[key], ensure_ascii=False, indent=2).replace('\n', '\n  ')
updated = (before + collaboration + ',\n' + entry('d01_emphasis_successor_20261002')
           + ',\n' + entry('ci_36908673854') + '\n}\n')
assert json.loads(updated) == state
state_path.write_text(updated)
marker = '2026-10-02 D01原文标题后继：'
body = (marker + '固定读#47 2b4f571e的D01来源补丁，#28十家公司当前保存原件比较只改变Marriott（34→38，四条下划线类别标题）与Paramount（一条U.S.标题截断恢复）。旧两个精确Result及Run保留，当前可信统计新增撤回Marriott，合计12坐标/18身份；其它八家仅证明此项标题提取文本无变化。显式D01后继来源与Evidence/Review/Result/Run禁网接通，两家最终V13绑定下各有私有CANDIDATE_READY、重复触发NO_SOURCE_CONTENT_CHANGE、独立进程冷读；不新增正式390或生产信用。定向4项、fast145/145、V13/V14执行绑定和三份接线收据通过；限定独审仍待精确SHA。原账本195槽/143/143/52，无新真实调用。证据`collab-d01-source-successor-20261002/`。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + body)
print(json.dumps({'status': 'RECORDED_D01_PRIVATE_SUCCESSOR',
                  'excluded_coordinates': 12, 'excluded_result_ids': 18}))
