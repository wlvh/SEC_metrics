"""Preserve the E01 first-review failure and record narrow source repair."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
raw = path.read_text()
state = json.loads(raw)
assert state['e01_item_source_repair_20261002']['independent_review'] == \
    'NEEDS_FIX_BC37A277_LINKED_BOUNDARY_AND_OFFSCREEN_TEXT'
assert 'e01_item_boundary_repair_20261002' not in state
prior = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                    'collab-e01-item-read-20261002/pfizer-section.json').read_text())
current = json.loads((HERE / 'pfizer-section.json').read_text())
assert prior['section_id'] == current['section_id']
assert prior['section_text_sha256'] == current['section_text_sha256']
fast = json.loads((HERE / 'fast-suite.json').read_text())
assert fast['status'] == 'PASSED' and len(fast['tests']) == 145
key = 'e01_item_boundary_repair_20261002'
entry = {'status': 'FIRST_REVIEW_P1_SOURCE_BOUNDARIES_REPAIRED_OFFLINE',
         'first_review': 'docs/evidence/issue28_continuous/collab-e01-item-read-20261002/independent-review-bc37a27/conclusion.md',
         'first_review_verdict': 'NEEDS_FIX_RETAINED',
         'repair_review': 'PENDING_EXACT_SHA',
         'changed_code': 'scripts/vnext/e01_item_source.py',
         'linked_801_toc_not_body': True,
         'linked_following_901_refused': True,
         'large_position_offsets_refused': True,
         'saved_pfizer_source_id_unchanged': current['section_id'],
         'directed_final_tree_tests': 6, 'fast_final_tree_selectors': 145,
         'v13_v14_runtime_binding_changed': False,
         'new_result_or_run': False, 'new_real_calls': [0, 0, 0],
         'current_390_credit': False, 'production_authorized': False,
         'evidence': 'docs/evidence/issue28_continuous/collab-e01-item-boundary-20261002/'}
pretty = '  ' + json.dumps(key) + ': ' + json.dumps(
    entry, ensure_ascii=False, indent=2).replace('\n', '\n  ')
assert raw.endswith('\n}\n')
updated = raw[:-3] + ',\n' + pretty + '\n}\n'
assert json.loads(updated)[key] == entry
path.write_text(updated)
marker = '2026-10-02 E01显式来源P1回修：'
note = (marker + '首轮bc37a277独审NEEDS_FIX保留：链接目录/后续9.01与视窗外正文可误接纳。新增链接祖先传递与后续带链接Item边界拒绝，左右上下大偏移/正负方向均拒；Pfizer原原件节段ID与哈希不变。最终树定向6项、fast145/145通过；显式来源能力尚未接正常E01 Run，无新数值/390或生产信用，Pfizer旧零继续扣留；新差异精确独审和远端CI待实际结果。证据`collab-e01-item-boundary-20261002/`，真实调用0/0/0。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + note)
print(json.dumps({'status': entry['status'], 'section_id': current['section_id']}))
