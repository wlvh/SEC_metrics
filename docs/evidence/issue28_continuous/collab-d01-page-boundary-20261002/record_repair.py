"""Keep the first review failure while recording this narrow D01 correction."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
state_path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
raw = state_path.read_text()
state = json.loads(raw)
assert state['d01_emphasis_successor_20261002']['limited_independent_review'] == 'PENDING_EXACT_PATCH_SHA'
old = '"limited_independent_review": "PENDING_EXACT_PATCH_SHA"'
assert raw.count(old) == 1
raw = raw.replace(old, '"limited_independent_review": "NEEDS_FIX_PAGE_JOIN_FALSE_POSITIVE_1457E99A"', 1)
fast = json.loads((HERE / 'fast-suite.json').read_text())
assert fast['status'] == 'PASSED' and len(fast['tests']) == 145
current = json.loads((HERE / 'current-ten.json').read_text())
assert current['status'] == 'PASS_TEN_SAVED_CURRENT_CANDIDATES_BYTE_IDENTICAL'
assert (HERE / 'native.exit').read_text().strip() == '0'
native = json.loads((HERE / 'private-update.json').read_text())
cold = json.loads((HERE / 'cold-read.json').read_text())
assert native['result_id'] == cold['result_id']
binding = json.loads((HERE / 'binding-after-d01-successor.json').read_text())
assert native['requirement_closure_hash'] == binding['parent_requirement_closure_hash']
entry = {'status': 'PAGE_JOIN_FALSE_ACCEPTANCE_REMOVED_KNOWN_MULTISPAN_WITHHELD',
         'first_review': 'docs/evidence/issue28_continuous/collab-d01-source-successor-20261002/independent-review-1457e99/conclusion.md',
         'first_review_verdict': 'NEEDS_FIX_RETAINED',
         'new_review': 'PENDING_EXACT_REPAIR_SHA',
         'changed_code': 'scripts/vnext/d01_emphasis_source.py',
         'current_saved_source_candidates': 'TEN_OF_TEN_EXACT_PRIOR_CANDIDATE_HASHES',
         'new_page_boundary_tests': ['ONLY_DIGIT_DOES_NOT_JOIN', 'KNOWN_MULTISPAN_WITHHELD'],
         'native': {'paramount_result_id': native['result_id'],
                    'first_status': native['first_status'],
                    'repeat_status': native['repeat_status'],
                    'cold_read_result_id': cold['result_id']},
         'fast_selectors': 145,
         'bindings': binding,
         'new_real_calls': [0, 0, 0],
         'trusted_summary_unchanged': '12_COORDINATES_18_EXACT_RESULT_IDENTITIES_WITHDRAWN',
         'current_390_credit': False, 'production_authorized': False,
         'evidence': 'docs/evidence/issue28_continuous/collab-d01-page-boundary-20261002/'}
assert 'd01_page_boundary_repair_20261002' not in state
key = 'd01_page_boundary_repair_20261002'
pretty = '  ' + json.dumps(key) + ': ' + json.dumps(
    entry, ensure_ascii=False, indent=2).replace('\n', '\n  ')
assert raw.endswith('\n}\n')
updated = raw[:-3] + ',\n' + pretty + '\n}\n'
assert json.loads(updated)[key] == entry
state_path.write_text(updated)
marker = '2026-10-02 D01跨页误合回修：'
note = (marker + '首轮1457e99a限定独审NEEDS_FIX保留：只有一个数字块也被合并，且单原文跨度不能表示两段标题。新后继不再合并；已知页码＋目录链接＋小写续句的跨页形式保留未支持状态，数字单块反例不合并。十家当前保存来源候选哈希10/10与先前一致，Paramount在新绑定下禁网私有正常更新、重复无变化与异进程冷读通过，fast145/145通过；当前旧错误结果12坐标/18身份仍扣留，尚无390或生产信用。新差异限定独审和远端CI待实际终态。证据`collab-d01-page-boundary-20261002/`，真实调用0/0/0。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + note)
print(json.dumps({'status': entry['status'], 'fast': len(fast['tests'])}))
