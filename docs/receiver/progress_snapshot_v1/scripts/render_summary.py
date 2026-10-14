#!/usr/bin/env python3
"""Render the #153 snapshot comment (Chinese Markdown) from build_snapshot.py outputs.

usage: render_summary.py <snapshot_dir> <links.json> <out.md>
links.json gives the fixed-commit URLs of the committed table and inputs.
Only counts and short lists are rendered; the complete table stays in the CSV.
"""
import collections, csv, json, sys
from pathlib import Path

snap, links, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
s = json.loads((snap / 'summary.json').read_text())
rows = list(csv.DictReader(open(snap / 'scope_table.csv', encoding='utf-8')))
C = collections.Counter

CLASS_ZH = {
    'VALUE': '有值',
    'VALUE_PENDING_SAVED_ANSWER': '有匹配的保存回答（未运行）',
    'TERMINAL_NON_NUMERIC': '合理非数值终态（结构性不适用/无经济意义）',
    'TERMINAL_NOT_DISCLOSED': '合理终态：SEC 未披露',
    'KNOWN_DEFECT_WITHHELD': '已登记错值，扣留',
    'ANSWER_GAP_MODEL_RESPONSE': '需新模型回答（用户决定额度）',
    'INPUT_GAP_SOURCE': '缺保存原件',
    'DEV_GAP_AMENDMENT_OR_SUCCESSOR': '开发缺口：修订年报/继任主体',
    'DEV_GAP_NOT_CONNECTED': '开发缺口：历史入口未接入',
    'DEV_GAP_NAVIGATION_OR_PARSE': '开发缺口：原件定位/解析',
    'DEV_GAP_EXECUTION_ERROR': '开发缺口：执行报错',
    'WITHHELD_CONFLICT_OR_AMBIGUOUS': '按规则扣留：冲突/歧义',
    'WITHHELD_OTHER': '扣留（原因待归类）',
    'VALUE_STATUS_WITHOUT_VALUE': '状态有值但值为空',
    'UNCLASSIFIED': '未归类',
    'NO_OBSERVATION': '本次未取得观察（运行未完成）',
    'WITHHELD_BY_CURRENT_RULE': '按现行规则扣留（合理终态）',
    'DEV_GAP_SOURCE_RELATION': '开发缺口：来源关系/输入未解决',
    'DEV_GAP_NA_REPORTED_AS_ERROR': '开发缺口：不适用却以报错结束',
    'ANSWER_GAP_NO_SAVED_D04_CALL': '无保存的 D04 回答（用户决定额度）',
}
REF_ZH = {'APPLICABLE': '适用', 'CONDITIONAL': '有条件', 'PENDING_CONFIRMATION': '待确认', 'NOT_APPLICABLE': '不适用'}
REF_ORDER = ['APPLICABLE', 'CONDITIONAL', 'PENDING_CONFIRMATION', 'NOT_APPLICABLE']


def fmt(n):
    return '{:,}'.format(n)


lines = []
add = lines.append
add('项目接收方 Claude：**项目进度快照 v1**（%s，main `%s`）' % (links['date_utc'], links['main'][:8]))
add('')
add('范围：登记的 10 家公司 × 39 指标 × 各公司最近五个已披露完整财年，共 %s 格。沿用现有业务目标、验收标准与权限，三份 Issue 正文未改。完整逐格表与生成材料：[scope_table.csv](%s)，[生成说明与命令](%s)。' % (fmt(s['cells']), links['table'], links['readme']))
add('')
add('### 1. 范围与参考分类')
add('')
add('| 公司 | 财年标签 | 实际期间 | 报告主体 |')
add('|---|---|---|---|')
by_company = collections.defaultdict(list)
for r in rows:
    if r['metric_id'] == 'A01':
        by_company[r['company_id']].append(r)
for cid, rs in by_company.items():
    rs.sort(key=lambda r: int(r['fiscal_year_label']))
    labels = 'FY%s–FY%s' % (rs[0]['fiscal_year_label'], rs[-1]['fiscal_year_label'])
    span = '%s 至 %s' % (rs[0]['period_start'] or '?', rs[-1]['period_end'] or '?')
    odd = [r['fiscal_year_label'] for r in rs if r['period_days'] and int(r['period_days']) not in (365, 366)]
    if odd:
        span += '（非 365/366 天：%s）' % '、'.join('FY%s=%s天' % (r['fiscal_year_label'], r['period_days']) for r in rs if r['fiscal_year_label'] in odd)
    roles = C((r['registrant_role'], r['reporting_cik']) for r in rs)
    role = '；'.join('%s %s×%d' % (k[0], k[1], n) for k, n in roles.items())
    add('| %s | %s | %s | %s |' % (rs[0]['company_name'], labels, span, role))
add('')
pairs = s['reference_pairs']
cells = s['reference_cells']
add('参考表 `catalog/reference/generated/sic_metric_map.json` 按原始字段 `business_applicability` 重新计数（每格只属一类）：')
add('')
add('| 参考分类 | 公司×指标组合 | 格数（×5 年） |')
add('|---|---:|---:|')
for k in REF_ORDER:
    add('| %s %s | %s | %s |' % (REF_ZH[k], k, fmt(pairs.get(k, 0)), fmt(cells.get(k, 0))))
add('| **参考适用子集（适用+有条件）** | %s | **%s** |' % (fmt(pairs.get('APPLICABLE', 0) + pairs.get('CONDITIONAL', 0)), fmt(s['reference_subset_1150_cells'])))
add('| 合计 | %s | %s |' % (fmt(sum(pairs.values())), fmt(s['cells'])))
add('')
add('当期视图：每家公司最近一年的 39 格（共 %s 格）就是当期成果的对应位置，不另计数。' % fmt(s['current_view_cells']))
add('')
add('### 2. 当前状态（本次在 main 上离线观察，每格计一次）')
add('')
classes = [k for k, _ in C(r['terminal_class'] for r in rows).most_common()]
add('| 状态类别 | ' + ' | '.join(REF_ZH[k] for k in REF_ORDER) + ' | 合计 |')
add('|---|' + '---:|' * (len(REF_ORDER) + 1))
for cl in classes:
    vals = [sum(1 for r in rows if r['terminal_class'] == cl and r['reference_class'] == k) for k in REF_ORDER]
    add('| %s `%s` | %s | %s |' % (CLASS_ZH.get(cl, cl), cl, ' | '.join(fmt(v) for v in vals), fmt(sum(vals))))
add('| 合计 | ' + ' | '.join(fmt(cells.get(k, 0)) for k in REF_ORDER) + ' | %s |' % fmt(s['cells']))
add('')
add('观察覆盖（每家公司 195 格；`HISTORY_RUN` 为入口完整导出，`HISTORY_RUN_PARTIAL` 为运行未结束时的逐格检查，`HISTORY_ENTRY_NOT_CONNECTED` 为入口未接入的 B13/C02/D02/D03）：')
add('')
add('| 公司 | 取得观察 | 其中完整导出 | 部分运行 | 未接入（代码事实） | 未取得 |')
add('|---|---:|---:|---:|---:|---:|')
for cid in sorted(by_company):
    rs = [r for r in rows if r['company_id'] == cid]
    src = C(r['obs_source'] for r in rs)
    add('| %s | %s | %s | %s | %s | %s |' % (rs[0]['company_name'], fmt(len(rs) - src.get('NONE', 0)), fmt(src.get('HISTORY_RUN', 0)),
        fmt(src.get('HISTORY_RUN_PARTIAL', 0)), fmt(src.get('HISTORY_ENTRY_NOT_CONNECTED', 0)), fmt(src.get('NONE', 0))))
add('')
for line in links.get('state_notes', []):
    add('- ' + line)
add('')
add('### 3. 已确认成果')
add('')
confirmed = [r for r in rows if r['terminal_class'] in ('VALUE', 'TERMINAL_NON_NUMERIC', 'TERMINAL_NOT_DISCLOSED', 'WITHHELD_BY_CURRENT_RULE')
             and r.get('check_vs_current', '').startswith('SAME_VALUE')]
add('定义：本次观察有值（或合理非数值终态），且已有原件核对记录与本次观察的值一致（按公司、指标、期间对齐，申报编号不同另标）。不按结果编号继承。')
add('')
add('- 有值，且已有原件核对记录与本次观察一致：**%s 格**（%s）。' % (fmt(len(confirmed)), '、'.join('%s %d' % (k, n) for k, n in C(r['metric_id'] for r in confirmed).most_common(14))))
term = [r for r in rows if r['terminal_class'] == 'TERMINAL_NON_NUMERIC' and r['reference_class'] == 'NOT_APPLICABLE']
odd_term = [r for r in rows if r['terminal_class'] == 'TERMINAL_NON_NUMERIC' and r['reference_class'] != 'NOT_APPLICABLE']
add('- 合理非数值终态且与参考分类一致（参考表不适用、本次为结构性不适用等）：**%s 格**。参考表不是“不适用”、本次却是非数值终态的 %s 格：%s。' % (
    fmt(len(term)), fmt(len(odd_term)), '；'.join('%s %s FY%s（参考 %s，本次 %s %s）' % (r['company_name'], r['metric_id'], r['fiscal_year_label'], r['reference_class'], r['obs_metric_status'], (r['obs_reason'] or '')[:40]) for r in odd_term[:20]) or '无'))
rule = [r for r in rows if r['terminal_class'] == 'WITHHELD_BY_CURRENT_RULE']
add('- 按现行规则合理扣留：%s 格（%s）。' % (fmt(len(rule)), '、'.join(sorted({'%s %s FY%s' % (r['company_name'], r['metric_id'], r['fiscal_year_label']) for r in rule}))))
diff = [r for r in rows if r.get('check_vs_current', '').startswith('DIFFERENT_VALUE')]
kinds = C(r['check_vs_current'] for r in diff)
KIND_ZH = {'DIFFERENT_VALUE_OLD_READING_HAS_REGISTERED_DEFECT': '同格有登记错值', 'DIFFERENT_VALUE_DERIVED_FROM_B01_DEFECT': '由同年/上年 B01 错值派生的 B02/B03',
           'DIFFERENT_VALUE': '没有登记错值可解释'}
explained = sum(n for k, n in kinds.items() if k != 'DIFFERENT_VALUE')
add('- **旧核对与本次观察不一致：%s 格**（%s）。其中 %s 格能由登记错值解释：旧核对当时读到并判为一致的是收入小计或组成项（后已登记为错值），本次观察是总收入，例如 Lumen FY2021 B01 本次 19,687,000,000，旧读数 17,795,000,000。这些旧依据不沿用，需要对当前值重新核对原件。' % (
    fmt(len(diff)), '；'.join('%s %d 格' % (KIND_ZH.get(k, k), n) for k, n in kinds.items()), fmt(explained)))
add('  涉及：%s。' % '；'.join(sorted({'%s %s FY%s（%s）' % (r['company_name'], r['metric_id'], r['fiscal_year_label'], KIND_ZH.get(r['check_vs_current'], '')) for r in diff})))
for r in [r for r in diff if r['check_vs_current'] == 'DIFFERENT_VALUE']:
    add('  - 无登记错值可解释：%s %s FY%s 本次 %s，旧记录 %s（%s）。' % (r['company_name'], r['metric_id'], r['fiscal_year_label'], r['obs_value'][:40], r['check_recorded_values'][:60], r['check_sources'][:80]))
noval = [r for r in rows if r.get('check_vs_current') == 'NO_CURRENT_VALUE']
add('- 有核对记录、本次没有值：%s 格（多为运行未完成）；只有计数级记录（无逐格数值）：%s 格。' % (fmt(len(noval)), fmt(sum(1 for r in rows if r.get('check_vs_current') == 'NO_RECORDED_VALUE'))))
vals = [r for r in rows if r['terminal_class'] == 'VALUE']
add('- 本次有值但没有任何原件核对记录：%s 格。' % fmt(sum(1 for r in vals if not r.get('original_check_basis'))))
ad = C(r['adoption_status'] for r in rows)
add('- 用户正式采纳（与上面的原件核对分开记录）：现行发布中逐项正式采纳 %s 格（%s）；随现行发布整体继承、没有逐项采纳记录 %s 格；其余 %s 格未采纳。%s' % (
    fmt(sum(n for k, n in ad.items() if k.startswith('FORMAL_ADOPTION'))),
    '、'.join(sorted('%s %s FY%s' % (r['company_name'], r['metric_id'], r['fiscal_year_label']) for r in rows if r['adoption_status'].startswith('FORMAL_ADOPTION'))),
    fmt(ad.get('ACTIVE_PUBLICATION_CARRIED_OVER', 0)), fmt(ad.get('NOT_ADOPTED', 0)), links.get('adoption_note', '')))
add('')
add('### 4. 未确认/未完成（原因、负责人、下一步）')
add('')
add('| 类别 | 格数 | 其中参考适用子集 | 负责人 | 下一步 |')
add('|---|---:|---:|---|---|')
for cl in classes:
    if cl in ('VALUE', 'TERMINAL_NON_NUMERIC', 'TERMINAL_NOT_DISCLOSED', 'WITHHELD_BY_CURRENT_RULE'):
        continue
    rs = [r for r in rows if r['terminal_class'] == cl]
    owner = '/'.join(sorted({o for r in rs for o in r['owner'].split('/') if o}))
    nxt = C(r['next_step'] for r in rs).most_common(1)[0][0]
    add('| %s | %s | %s | %s | %s |' % (CLASS_ZH.get(cl, cl), fmt(len(rs)), fmt(sum(1 for r in rs if r['in_reference_subset_1150'] == 'Y')), owner, nxt))
add('')
for line in links.get('open_notes', []):
    add('- ' + line)
add('')
add('### 5. 当期视图与本次观察的对齐')
add('')
cv = [r for r in rows if r['current_view'] == 'Y']
al = C((r.get('pub_row') or '').split(':')[0] + '|' + (r.get('align_status') or '') for r in cv)
pub_total = (s.get('publication') or {}).get('rows', 0)
pub_on = sum(1 for r in rows if r.get('pub_row') == 'Y')
pub_hist = [r for r in rows if r.get('pub_row') == 'Y' and r['current_view'] != 'Y']
add('当期视图取现行发布包 `%s`（%s 行）；按公司、指标、期间对齐后再比较，期间不同的行不跨期比较。%s 行落在范围表的同期格上（其中 %s 行落在非最近一年：%s），%s 行的期间对不上任何格。' % (
    links.get('publication_id', '')[:24] + '…', fmt(pub_total), fmt(pub_on), fmt(len(pub_hist)),
    '、'.join(sorted({'%s %s FY%s' % (r['company_name'], r['metric_id'], r['fiscal_year_label']) for r in pub_hist})) or '无', fmt(pub_total - pub_on)))
add('')
STATE_ZH = {'VALUE': '有值', 'TEXT': '有文字结论', 'TERMINAL': '合理非数值终态', 'OPEN': '未出结果', 'NONE': '本次未取得观察'}


def align_label(key):
    row, status = key.split('|', 1)
    if row == 'NO_ROW':
        return '发布包没有该行'
    if row == 'ROW_FOR_OTHER_PERIOD':
        return '发布包该行属于其他期间（不跨期比较）'
    fixed = {'BOTH_VALUE_SAME': '两边都有值且相同', 'BOTH_VALUE_DIFFERENT': '两边都有值但不同',
             'BOTH_TERMINAL_SAME_STATUS': '两边都是合理非数值终态，状态相同',
             'BOTH_TERMINAL_DIFFERENT_STATUS': '两边都是合理非数值终态，状态不同',
             'BOTH_TEXT_RESULT_NOT_COMPARED': '两边都有文字结论（发布包文字在证据表，本版未逐字比较）'}
    if status in fixed:
        return fixed[status]
    if status.startswith('PUB_'):
        pub, cur = status[4:].split('__CUR_')
        return '发布包%s／当前 main %s' % (STATE_ZH.get(pub, pub), STATE_ZH.get(cur, cur))
    return key


add('| 当期格（%s） | 格数 |' % fmt(len(cv)))
add('|---|---:|')
for k, n in sorted(al.items(), key=lambda x: -x[1]):
    add('| %s | %s |' % (align_label(k), fmt(n)))
add('')
bd = [r for r in rows if r.get('align_status') == 'BOTH_VALUE_DIFFERENT']
if bd:
    add('- 两边都有值但不同：' + '；'.join('%s %s FY%s 本次 %s / 发布包 %s' % (r['company_name'], r['metric_id'], r['fiscal_year_label'], r['obs_value'][:14], r['pub_value'][:14]) for r in bd) + '。')
po = [r for r in rows if r.get('align_status') == 'PUB_VALUE__CUR_OPEN']
if po:
    add('- 发布包有值、当前 main 未出结果：%s。原因见各格 `terminal_class`（历史入口未接入、扣留或缺回答），不按发布包补值。' % '、'.join('%s %d' % (k, n) for k, n in C(r['metric_id'] for r in po).most_common()))
for code, text in (('PUB_TERMINAL__CUR_VALUE', '发布包为非数值终态、当前 main 有值'), ('PUB_VALUE__CUR_TERMINAL', '发布包有值、当前 main 为非数值终态'),
                   ('BOTH_TERMINAL_DIFFERENT_STATUS', '两边都是非数值终态但状态不同'), ('PUB_OPEN__CUR_VALUE', '发布包未出结果、当前 main 有值')):
    rs = [r for r in rows if r.get('align_status') == code]
    if rs:
        add('- %s：%s。' % (text, '；'.join('%s %s FY%s（发布包 %s / 当前 %s）' % (r['company_name'], r['metric_id'], r['fiscal_year_label'], r['pub_status'], r['obs_metric_status'] or r['terminal_class']) for r in rs)))
op = [r for r in cv if (r.get('pub_row') or '').startswith('ROW_FOR_OTHER_PERIOD')]
if op:
    add('- 发布包行的期间与该公司最近财年不一致：%s。' % '；'.join(sorted({'%s %s（发布包 %s，本格 %s）' % (r['company_name'], r['metric_id'], r['pub_row'].split(':', 1)[1], r['period_end']) for r in op})))
pdf = [r for r in rows if r.get('pub_defect_flag')]
if pdf:
    eq = [r for r in pdf if r['pub_defect_flag'] == 'PUBLICATION_VALUE_EQUALS_REGISTERED_DEFECT_VALUE']
    add('- **发布包在已登记错值（已撤回）的格子上仍有值：%s 格**。其中 %s 格发布值与登记的错值完全相同（%s）；其余 %s 格登记里没有记下错值本身，无法从材料判断发布值是否就是被撤回的那一个（%s）。' % (
        fmt(len(pdf)), fmt(len(eq)), '；'.join(sorted('%s %s FY%s' % (r['company_name'], r['metric_id'], r['fiscal_year_label']) for r in eq)),
        fmt(len(pdf) - len(eq)), '；'.join(sorted('%s %s FY%s' % (r['company_name'], r['metric_id'], r['fiscal_year_label']) for r in pdf if r not in eq))))
for line in links.get('alignment_notes', []):
    add('- ' + line)
add('')
add('### 6. 材料缺口与补件请求')
add('')
for line in links.get('requests', []):
    add('- ' + line)
add('')
add('### 7. 生成方法')
add('')
for line in links.get('method', []):
    add('- ' + line)
add('')
add('新增 SEC/模型/付费调用 0/0/0；旧状态未改写；未改业务目标、验收标准与权限。')
add('')
add('---')
add('_Generated by [Claude Code](https://claude.ai/code)_')
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(len('\n'.join(lines)), 'chars')
