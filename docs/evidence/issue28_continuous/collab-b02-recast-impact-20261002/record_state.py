"""Record the measured current-route impact of the peer B02 guard expansion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
raw = path.read_text()
state = json.loads(raw)
impact = json.loads((HERE / 'impact.json').read_text())
assert impact['positive_current_b02_count'] == 8
assert impact['newly_withheld_by_peer_guard'] == []
assert len(impact['rows']) == 10 and impact['ledger_and_source_log_unchanged']
assert 'b02_same_concept_recast_20261002' not in state
key = 'b02_same_concept_recast_20261002'
entry = {'status': 'CURRENT_TEN_SAVED_SOURCE_IMPACT_MEASURED_NO_NEW_RESULT_WITHDRAWAL',
         'peer_fixed_read': impact['peer_fixed_commit'],
         'peer_original_rule_commit': '336ab3ae15b6c0af0c0c06982f87f54bff67209a',
         'peer_guard_git_blob': impact['peer_guard_git_blob'],
         'own_bound_guard': impact['own_guard_path'],
         'current_positive_b02_count': 8,
         'non_numeric': {'jpmorgan_chase': 'TRAIT_NOT_APPLICABLE',
                         'paramount_skydance_paramount_global': 'ENTITY_CONTINUITY_NOT_COMPARABLE'},
         'newly_withheld_by_peer_guard': [],
         'integration_decision': 'DEFER_THIS_BATCH_NO_CURRENT_RESULT_CHANGED; FUTURE_B02_RULE_BATCH_USE_OWN_EXPLICIT_VERSIONED_SUCCESSOR_AND_TEST_SAME_CONCEPT_RECAST',
         'old_run_or_result_rewritten': False,
         'new_real_calls': [0, 0, 0],
         'evidence': 'docs/evidence/issue28_continuous/collab-b02-recast-impact-20261002/'}
pretty = '  ' + json.dumps(key) + ': ' + json.dumps(
    entry, ensure_ascii=False, indent=2).replace('\n', '\n  ')
assert raw.endswith('\n}\n')
updated = raw[:-3] + ',\n' + pretty + '\n}\n'
assert json.loads(updated)[key] == entry
path.write_text(updated)
marker = '2026-10-02 B02同概念重述通知处置：'
note = (marker + '固定读#47 49b41271与336ab3ae后继守卫，#28直接从十家公司当前保存来源重建B02候选，并离线比较旧/新函数：八家当期B02有值，新增护栏均不扣留；JPMorgan规则不适用、Paramount主体不可比。故本批不改已经绑定的普通V1、不重签旧Run；未来新报表仍需本方专用版本化后继纳入同概念重述正例和当期八值回归。此为当期增量影响核对，不证明未来不会重述或八值全部内容正确。证据`collab-b02-recast-impact-20261002/`，真实调用0/0/0。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + note)
print(json.dumps({'status': entry['status'], 'current_values': 8}))
