"""Render the #153 v1.1 update from output_v1_1 (numbers are computed, wording is fixed).

usage: render_v1_1.py OUTPUT_DIR V1_OUTPUT_DIR FROZEN_AT_UTC MAIN_SHA > comment.md
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

out, v1, frozen, main_sha = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
rows = list(csv.DictReader(open(out / 'scope_table.csv', encoding='utf-8')))
old = {(r['company_id'], r['metric_id'], r['fiscal_year_label']): r for r in csv.DictReader(open(v1 / 'scope_table.csv', encoding='utf-8'))}
errors = list(csv.DictReader(open(out / 'published_errors.csv', encoding='utf-8')))
names = {r['company_id']: r['company_name'] for r in rows}
cls = collections.Counter(r['terminal_class'] for r in rows)
src = collections.Counter(r['obs_source'] for r in rows)
observed = len(rows) - src['NONE']
newly = [r for r in rows if old[(r['company_id'], r['metric_id'], r['fiscal_year_label'])]['obs_source'] == 'NONE'
         and r['obs_source'] != 'NONE']
not_connected = collections.Counter(r['metric_id'] for r in rows if r['terminal_class'] == 'DEV_GAP_NOT_CONNECTED')
newly_cls = collections.Counter(r['terminal_class'] for r in newly)
check = collections.Counter(r['check_vs_current'] for r in rows)
confirmed = check['SAME_VALUE'] + check['SAME_VALUE_AS_CORRECTING_READING']
v1_confirmed = sum(1 for r in old.values() if r['check_vs_current'] == 'SAME_VALUE')
conflicts = collections.Counter(r['metric_id'] for r in rows if r['check_vs_current'] == 'CONFLICTING_CHECKS')
gaps = collections.Counter(r['metric_id'] for r in rows if r['terminal_class'] == 'ANSWER_GAP_MODEL_RESPONSE')
adoption = collections.Counter(r['adoption_status'] for r in rows)
jpm_missing = sum(1 for r in rows if r['terminal_class'] == 'NO_OBSERVATION')


def fmt(v):
    if not v:
        return '—'
    n = float(v)
    return f'{n:,.0f}' if abs(n) >= 1000 or n.is_integer() else f'{n:.4f}'


ACTION = {'REPLACE_WITH_VERIFIED_VALUE': '换成已核对值', 'WITHHOLD': '扣留'}
WHY = {'B01': '收入小计/净销售额当作总收入', 'B02': '用小计算的增长率', 'B03': '用小计作分母'}
WHY_BY_CREDIT = {'WITHDRAWN_CONFIRMED_FIXED_ASSET_SUBTOTAL_USED_AS_TOTAL': 'D&A 只取了固定资产部分',
                 'WITHDRAWN_SELECTED_1_01_FINANCING_IS_NOT_M_AND_A_ANNOUNCEMENT': '把融资协议 8-K 计为并购公告',
                 'WITHDRAWN_CONFIRMED_FALSE_ZERO_FOR_CONTENT_CONFIRMED_M_AND_A': '漏读 8.01 正文，实际有一宗已完成的收购'}


def why(e):
    for credit in e['current_credit'].split(';'):
        if credit in WHY_BY_CREDIT:
            return WHY_BY_CREDIT[credit]
    return WHY.get(e['metric_id'], '')
lines = []
add = lines.append
add(f'项目接收方 Claude：**项目进度快照 v1.1**（{frozen} 冻结；观察仍用 main `681b35d8` 的代码，'
    f'缺陷登记与发布出口读取 main `{main_sha[:8]}`）')
add('')
add('按反馈收口，不重做范围和流程。下面把“新查清”“真正修好”“仍需外部材料或授权”分开写。'
    '完整逐格表、生成命令与输入：[output_v1_1](https://github.com/wlvh/SEC_metrics/tree/claude/sec-metrics-integration-gat2v8/docs/receiver/progress_snapshot_v1/output_v1_1) 。')
add('')
add('### 0. 口径更正（相对 v1）')
add(f'- v1 的 882 是**状态观察覆盖**，不是 882 格都在本次重算：完整导出 525、运行中逐格 157、入口能力判断 200。'
    f'剩余 1,068 格是当时没有观察，不等于未开发。')
add(f'- v1 的 272 改称“**与既有原件读数相符**”，不叫完整验收。比较规则已收紧，并加了边界测试：'
    f'值、期间、单位、主体、申报必须在同一条核对记录上同时相符；'
    f'旧记录之间互相冲突的不自动确认；读数本身等于已登记错值的不作为依据。'
    f'按新规则重算，v1 的 272 格全部仍然成立。')
add(f'- “随现行发布继承” {adoption["ACTIVE_PUBLICATION_CARRIED_OVER"]} 格只是发布记录，不与“相符”相加，也不说明现在仍正确。'
    f'逐项正式采纳仍是 {adoption["FORMAL_ADOPTION_2026_09_10"]} 格。')
add('')
add('### 1. 三类结果分开')
add('**A. 这次新查清（没有改变任何结果）**')
add(f'- 观察覆盖 {observed:,} / 1,950：完整导出 {src["HISTORY_RUN"]:,}、运行中逐格 {src["HISTORY_RUN_PARTIAL"]}、'
    f'入口能力判断 {src["HISTORY_ENTRY_NOT_CONNECTED"]}。未取得 {src["NONE"]} 格，全部是 JPMorgan，补跑还在进行'
    f'（其中 D04 FY2025 一格由 #28 报告已有当期结果）。'
    f'比 v1 新增观察 {len(newly)} 格，其中有值 {newly_cls["VALUE"]}、合理非数值终态 {newly_cls["TERMINAL_NON_NUMERIC"]}。'
    f'这些是补跑 Ford、Southwest、Paramount、Marriott 得到的观察，**不是新增交付**。')
add(f'- 与既有原件读数相符：{confirmed} 格（v1 为 {v1_confirmed}，新增部分来自补跑的公司）。')
add(f'- 旧核对记录互相冲突、不予确认：{sum(conflicts.values())} 格（'
    + '、'.join(f'{m} {n} 格' for m, n in sorted(conflicts.items())) + '），这些格本次都没有当前值。')
add('- 发布出口错值、D04/E01/D02 缺口和 Macy\'s 的两个问题，见第 2–4 节。')
add('')
add('**B. 真正修好（已进入 main；进入用户默认读取出口的：0）**')
add('- #286、#289：Macy\'s FY2025 B01/B03、FY2024 B01/B02 四个旧错结果，公司读取入口现在扣留。修正后的值还是分支候选，未采纳。')
add('- #282：JPMorgan 当期 D04 恢复复用 27 组保存回答，零调用。#284：D03 解释规则一致。')
add('')
add('**C. 仍需外部材料或授权**：发布出口处理（第 2 节）、新模型调用（第 4 节）、Macy\'s FY2019 年报（第 3 节）。')
add(f'开发项（不需要授权）：历史入口未接入 {cls["DEV_GAP_NOT_CONNECTED"]} 格'
    f'（B13、C02、D03 各 {not_connected["B13"]}，另 {cls["DEV_GAP_NOT_CONNECTED"] - not_connected["B13"] - not_connected["C02"] - not_connected["D03"]} 格为 B06/D01/C04 的个别年份）；'
    f'B10/B11 对非酒店公司以报错结束 {cls["DEV_GAP_NA_REPORTED_AS_ERROR"]} 格。后者修好只改状态语义，**不增加任何数值**，单独列出。'
    f'还有 {cls["WITHHELD_OTHER"]} 格扣留原因待 #47 归类。')
add('')
add('### 2. 发布出口里已确认的错值（最优先，需要你批准处理方式）')
add('- **用户实际读取的出口**：根目录 `REPORT_十公司财务指标.md`、`outputs/metrics_matrix.csv`、`outputs/metric_evidence.csv`。'
    '它们与现行发布包 `publication_24bf8f…` 逐字节相同，业务指南第 3–4 步指向这里。'
    '公司读取入口（`vnext_company.py results`）已扣留登记错值，不受影响。')
add('- 已确认的 12 格（发布值等于已登记错值；6 格的替代值由接收方用各公司原 10-K 的 XBRL 重算）：')
add('')
add('| 公司 | 指标 | 期末 | 发布值 | 错在哪里 | 处理 | 已核对替代值 |')
add('|---|---|---|---:|---|---|---:|')
for e in sorted([e for e in errors if e['proposed_action'] != 'REVIEW_BY_OWNER'],
                key=lambda e: (e['proposed_action'] != 'REPLACE_WITH_VERIFIED_VALUE', e['company_id'], e['metric_id'])):
    add(f"| {names.get(e['company_id'], e['company_id'])} | {e['metric_id']} | {e['period_end']} | {fmt(e['published_value'])} | "
        f"{why(e)} | {ACTION[e['proposed_action']]} | {fmt(e['verified_replacement'])} |")
add('')
review = [e for e in errors if e['proposed_action'] == 'REVIEW_BY_OWNER']
add(f'- 另有 {len(review)} 行文字或非数值结论，落在已登记缺陷的坐标上。发布 CSV 不带结果编号，不能凭坐标认定为同一个错误，请 #28 逐条判定。')
add('- **最小处理方案**（属生产变更，等你批准；旧包原字节保留为历史）：')
add('  - **B（推荐）**：用现有发布工具出一个后继包，只改这 12 行——6 行换成上表的已核对值，6 行改为扣留并写明原因；'
    '其余行逐字节不变。active 切到新包，旧包作为上一版，可回退。由 #28 实施，接收方按上表逐格核对后再切换。')

add('  - **A（可先止血）**：不动发布包，在 main 增加一份勘误清单，并在业务指南读取步骤前加提示。缺点是直接读 CSV 的人仍会看到旧值。')
add('  - 两者都不包括：上面待判定的文字结论，以及整批采纳新快照。')
add('')
add('### 3. 调查结论（按现行规则即可处理，不需要你拍板）')
add('- **D04**：#28 的 93 组旧回答全部属于最新一年，10 家公司每家 4–27 组，当期路线已经消费。'
    '最新一年不需要为历史入口补兼容或新调用，本表把这 10 格记为“当期路线已有结果（#28 报告，接收方未复现）”。'
    '真实缺口是 FY2021–2024 共 37 个公司年度：Marriott FY2023/2024、Paramount FY2024 已有 #47 保存回答，不在其中。')
add('- **Macy\'s FY2021/22**：两年原年报利润表都没有“总收入”行，只列 Net sales 和 Credit card revenues, net（净额 832/863）。'
    'FY2023 年报重述时改称 Other revenue，金额 939/1,007，含重分类项目，与原报不同。'
    '按现行规则（各年取首次报告值，不用后来的比较数），这两年取净销售额是规则的结果，不是实现错误。'
    '由此 FY2023 增长率前后口径不同，按现行规则应扣留。请 #47 在 FY2019 解锁后确认代码确实如此。'
    '只有要改用重述后的比较数时，才需要你决定（即 #153 第 5.2 节的“B02 上年取值”）。')
add('- **Macy\'s FY2019 为什么会阻断五年**：财年标签检查以起始年 1 月 1 日为目标，载入一段申报元数据窗口。'
    'Macy\'s FY2019 年报的期末是 2020-02-01，落在窗口内；代码规定窗口内任何一份没读到的原件都会阻断所有年份。'
    '各年数值本身不需要 FY2019，它只影响 FY2020 的标签是否唯一，也就是 FY2021 增长率的上年取值。'
    'FY2022–2025 被一起阻断，属于检查范围过宽，已请 #47 收窄。')
add('')
add('### 4. 新模型调用：去重后的真实缺口（一次决定，不逐格）')
add('')
add('| 指标 | 缺口 | 去重后的请求数 | 规模 |')
add('|---|---|---:|---|')
add(f'| D02 | {gaps["D02"]} 个公司年度 | {gaps["D02"]} | 当前 main 上 44 个可准备样本各 1 个请求，互不重复，其中 Ford FY2025 已有保存回答。'
    '已测过的 10 个约 2.7 万–6.3 万 token/个；代码上限 20 万 token/个 |')
add(f'| E01 | {gaps["E01"]} 个公司年度（JPMorgan FY2022–2025 尚未观察） | {gaps["E01"]} | 每格 1 个请求，合计约 71 万字符（约 18 万 token） |')
add('| D04 历史 | 37 个公司年度 | 约 350（按 #28 当期每家 4–27 组推算） | — |')
add('')
add('- 按 #28 最近报告的总账，额度剩余 provider/paid/SEC = 97/97/28。D02 加 E01 共 81 次，在剩余额度内；D04 历史约 350 次，超出剩余额度。')
add('- 建议：一次授权 D02 + E01 不超过 81 次（每次请求不超过 20 万 token，输入总量不超过约 900 万 token）。D04 历史单独决定：提高额度，或暂缓。')
add('')
add('### 5. 需要你决定的只剩三项')
add('1. 发布出口：批准方案 B，或先做 A。')
add('2. 新调用：是否批准 D02 + E01 共不超过 81 次；D04 历史是否提高额度。')
add('3. Macy\'s FY2019：是否批准 1 次 SEC 获取（在剩余 28 次以内）。与 #47 收窄检查范围可以同时做。')
add('')
add('新增 SEC/模型/付费调用 0/0/0；旧状态未改写；未改业务目标、验收标准与权限。')
print('\n'.join(lines))
