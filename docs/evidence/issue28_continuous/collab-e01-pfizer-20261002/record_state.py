"""Record exact Pfizer E01 withdrawal and the fixed #47 defect read."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
state_path = ROOT / 'docs/evidence/issue28_continuous/execution-state.json'
continuation = ROOT / 'docs/evidence/issue28_continuous/continuation.md'
raw = state_path.read_text()
state = json.loads(raw)
audit = json.loads((HERE / 'audit.json').read_text())
register = json.loads((ROOT / 'docs/evidence/issue28_continuous/'
                       'known_result_defects.json').read_text())
assert audit['status'] == 'CONFIRMED_OLD_ZERO_EXCLUDES_RELEVANT_8_01_BODY'
assert register['current_trusted_summary']['newly_excluded_coordinate_count'] == 13
assert register['current_trusted_summary']['newly_excluded_result_id_count'] == 19
assert 'e01_pfizer_8_01_20261002' not in state
collab_start = raw.index('"collab_28_47_v1": {')
collab_end = raw.index('\n  },', collab_start)
collab = raw[collab_start:collab_end]
assert '"peer_read_commit": "2b4f571ef18274299145c63b4c355aa97c45d030"' in collab
assert '"peer_register_git_blob": "7bf9d63d03a198409c668205135d50655dad1725"' in collab
new_collab = collab.replace('"peer_read_commit": "2b4f571ef18274299145c63b4c355aa97c45d030"',
    '"peer_read_commit": "bc0a2ac7ed1c89ac5d3c309d52f4519898ba6ee7"', 1).replace(
    '"peer_register_git_blob": "7bf9d63d03a198409c668205135d50655dad1725"',
    '"peer_register_git_blob": "4740055ffe552d1beb688634e8886f68385706bc"', 1)
raw = raw[:collab_start] + new_collab + raw[collab_end:]
key = 'e01_pfizer_8_01_20261002'
entry = {'status': 'OLD_ZERO_WITHDRAWN_EXACT_RESULT_NO_REPLACEMENT',
         'peer_fixed_read': audit['peer_fixed_read'],
         'peer_defect_id': audit['peer_defect_id'],
         'own_old_result_id': audit['old_result_id'],
         'old_run_id': audit['old_run_id'],
         'accession': audit['accession'],
         'old_matcher_returns_empty_for_this_8_01': True,
         'current_trusted_summary': {'excluded_coordinates': 13,
                                     'excluded_exact_result_ids': 19},
         'new_result_or_run': False,
         'new_real_calls': [0, 0, 0],
         'evidence': 'docs/evidence/issue28_continuous/collab-e01-pfizer-20261002/',
         'next_engineering_boundary': 'EXPLICIT_ORDINARY_8_01_BODY_SOURCE_AND_CONTENT_CONFIRMED_M_AND_A_WITH_DEDUP_NOT_YET_COMPLETE'}
pretty = '  ' + json.dumps(key) + ': ' + json.dumps(
    entry, ensure_ascii=False, indent=2).replace('\n', '\n  ')
assert raw.endswith('\n}\n')
updated = raw[:-3] + ',\n' + pretty + '\n}\n'
assert json.loads(updated)[key] == entry
state_path.write_text(updated)
marker = '2026-10-02 Pfizer E01旧零值纠错：'
note = (marker + '固定读#47 bc0a2ac7登记后，本方直接核对FY2025保存8-K头文件、8.01主正文、旧Candidate/Result与390同ID：2025-11-13 Pfizer正文明确报道完成Metsera收购及合并协议；原HDR生成brief不含关键词，冻结matcher没有读正文，旧Result 27708650…为错误零。仅扣留该旧精确Result/坐标，当前总计13坐标/19身份；原件、旧Run/Result/390分母保留，不复制#47修复结果，不生成新E01数值。证据`collab-e01-pfizer-20261002/`，真实调用0/0/0。E01完整普通后继还需内容确认、1.01融资排除、8.01范围和去重；不把本次错误扣留算作能力完成。\n')
text = continuation.read_text()
if marker not in text:
    continuation.write_text(text.rstrip() + '\n\n' + note)
print(json.dumps({'status': entry['status'], 'excluded_coordinates': 13}))
