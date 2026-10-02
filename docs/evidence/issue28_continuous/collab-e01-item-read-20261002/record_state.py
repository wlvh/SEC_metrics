"""Record source-reader ability without promoting an E01 business result."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
raw = path.read_text()
state = json.loads(raw)
assert 'e01_item_source_repair_20261002' not in state
source = json.loads((HERE / 'pfizer-section.json').read_text())
assert source['status'] == 'PASS_AUTHENTICATED_PRIMARY_SECTION_AND_REPLAY'
assert source['metric_result_created'] is False
entry = {'status': 'EXPLICIT_SAVED_PFIZER_8_01_BODY_READABLE_NOT_NATIVE_E01_RESULT',
         'fixed_peer_read': 'bc0a2ac7ed1c89ac5d3c309d52f4519898ba6ee7',
         'own_function': 'scripts/vnext/e01_item_source.py:bound_801_primary_section',
         'saved_positive_source_id': source['section_id'],
         'directed_final_tree_tests': 6,
         'exploratory_fast_run': 'STARTED_BEFORE_FINAL_LINKED_HEADING_GUARD_NO_FINAL_TREE_CREDIT',
         'v13_v14_runtime_binding_changed': False,
         'old_frozen_route_result_changed': False,
         'e01_business_content_confirmation_complete': False,
         'new_result_or_run': False, 'new_real_calls': [0, 0, 0],
         'trusted_summary': '13_COORDINATES_19_EXACT_RESULT_IDENTITIES_WITHDRAWN',
         'independent_review': 'PENDING_EXACT_SHA',
         'evidence': 'docs/evidence/issue28_continuous/collab-e01-item-read-20261002/'}
key = 'e01_item_source_repair_20261002'
pretty = '  ' + json.dumps(key) + ': ' + json.dumps(
    entry, ensure_ascii=False, indent=2).replace('\n', '\n  ')
assert raw.endswith('\n}\n')
updated = raw[:-3] + ',\n' + pretty + '\n}\n'
assert json.loads(updated)[key] == entry
path.write_text(updated)
marker = '2026-10-02 E01 8.01来源读取后继：'
note = (marker + '原E01旧零值扣留后，修现有显式来源组件：允许普通可见颜色/相对定位、用8.01条目码而非固定标题、拒带链接目录标题；透明/零字号/低不透明度及改坏原件仍拒。Pfizer保存8-K主正文通过SourceReference与资产哈希重建为一条来源节段，原文确认完成Metsera收购；最终树定向6项及原件重读通过。组件尚未进入普通E01原生Run，未提供新数值或390信用，V13/V14绑定未改，真实调用0/0/0。探索性fast在最终代码微调前启动，不当作最终树通过；后续以精确提交审阅/CI为准。证据`collab-e01-item-read-20261002/`。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + note)
print(json.dumps({'status': entry['status'], 'source_id': source['section_id']}))
