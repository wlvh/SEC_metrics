项目接收方 Claude：**项目进度快照 v1**（2026-10-14 09:44 UTC 冻结，main `681b35d8`）

范围：登记的 10 家公司 × 39 指标 × 各公司最近五个已披露完整财年，共 1,950 格。沿用现有业务目标、验收标准与权限，三份 Issue 正文未改。完整逐格表与生成材料：[scope_table.csv](https://github.com/wlvh/SEC_metrics/blob/b389b3903a30598ce0662a756b4503c0d425cfd7/docs/receiver/progress_snapshot_v1/output/scope_table.csv) ，[生成说明与命令](https://github.com/wlvh/SEC_metrics/blob/b389b3903a30598ce0662a756b4503c0d425cfd7/docs/receiver/progress_snapshot_v1/README.md) 。

### 1. 范围与参考分类

| 公司 | 财年标签 | 实际期间 | 报告主体 |
|---|---|---|---|
| Marriott International | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 1048286×5 |
| Southwest Airlines | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 92380×5 |
| Ford Motor Company | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 37996×5 |
| Pfizer | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 78003×5 |
| JPMorgan Chase | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 19617×5 |
| Salesforce | FY2022–FY2026 | 2021-02-01 至 2026-01-31 | PRIMARY 1108524×5 |
| Lumen Technologies | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 18926×5 |
| Macy's | FY2021–FY2025 | 2021-01-31 至 2026-01-31（非 365/366 天：FY2021=364天、FY2022=364天、FY2023=371天、FY2024=364天、FY2025=364天） | PRIMARY 794367×5 |
| Paramount Skydance / Paramount Global | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PREDECESSOR 813828×4；PRIMARY 2041610×1 |
| Enphase Energy | FY2021–FY2025 | 2021-01-01 至 2025-12-31 | PRIMARY 1463101×5 |

参考表 `catalog/reference/generated/sic_metric_map.json` 按原始字段 `business_applicability` 重新计数（每格只属一类）：

| 参考分类 | 公司×指标组合 | 格数（×5 年） |
|---|---:|---:|
| 适用 APPLICABLE | 227 | 1,135 |
| 有条件 CONDITIONAL | 3 | 15 |
| 待确认 PENDING_CONFIRMATION | 7 | 35 |
| 不适用 NOT_APPLICABLE | 153 | 765 |
| **参考适用子集（适用+有条件）** | 230 | **1,150** |
| 合计 | 390 | 1,950 |

当期视图：每家公司最近一年的 39 格（共 390 格）就是当期成果的对应位置，不另计数。

### 2. 当前状态（本次在 main 上离线观察，每格计一次）

| 状态类别 | 适用 | 有条件 | 待确认 | 不适用 | 合计 |
|---|---:|---:|---:|---:|---:|
| 本次未取得观察（运行未完成） `NO_OBSERVATION` | 622 | 5 | 0 | 441 | 1,068 |
| 有值 `VALUE` | 291 | 0 | 0 | 0 | 291 |
| 合理非数值终态（结构性不适用/无经济意义） `TERMINAL_NON_NUMERIC` | 3 | 0 | 0 | 283 | 286 |
| 开发缺口：历史入口未接入 `DEV_GAP_NOT_CONNECTED` | 100 | 10 | 35 | 5 | 150 |
| 需新模型回答（用户决定额度） `ANSWER_GAP_MODEL_RESPONSE` | 52 | 0 | 0 | 0 | 52 |
| 开发缺口：不适用却以报错结束 `DEV_GAP_NA_REPORTED_AS_ERROR` | 0 | 0 | 0 | 36 | 36 |
| 无保存的 D04 回答（用户决定额度） `ANSWER_GAP_NO_SAVED_D04_CALL` | 18 | 0 | 0 | 0 | 18 |
| 开发缺口：来源关系/输入未解决 `DEV_GAP_SOURCE_RELATION` | 17 | 0 | 0 | 0 | 17 |
| 开发缺口：原件定位/解析 `DEV_GAP_NAVIGATION_OR_PARSE` | 8 | 0 | 0 | 0 | 8 |
| 按现行规则扣留（合理终态） `WITHHELD_BY_CURRENT_RULE` | 7 | 0 | 0 | 0 | 7 |
| 缺保存原件 `INPUT_GAP_SOURCE` | 6 | 0 | 0 | 0 | 6 |
| 按规则扣留：冲突/歧义 `WITHHELD_CONFLICT_OR_AMBIGUOUS` | 5 | 0 | 0 | 0 | 5 |
| 开发缺口：修订年报/继任主体 `DEV_GAP_AMENDMENT_OR_SUCCESSOR` | 3 | 0 | 0 | 0 | 3 |
| 扣留（原因待归类） `WITHHELD_OTHER` | 2 | 0 | 0 | 0 | 2 |
| 有匹配的保存回答（未运行） `VALUE_PENDING_SAVED_ANSWER` | 1 | 0 | 0 | 0 | 1 |
| 合计 | 1,135 | 15 | 35 | 765 | 1,950 |

观察覆盖（每家公司 39 指标 × 5 年 = 195 格；B13/C02/D02/D03 在历史入口没有处理接口，单列为“未接入”；其余 175 格按“运行结束后完整导出 / 运行中的逐格检查 / 未取得”计）：

| 公司 | 取得观察 | 完整导出 | 运行中逐格检查 | 未接入（代码事实） | 未取得 |
|---|---:|---:|---:|---:|---:|
| Enphase Energy | 195 | 175 | 0 | 20 | 0 |
| Ford Motor Company | 27 | 0 | 7 | 20 | 168 |
| JPMorgan Chase | 35 | 0 | 15 | 20 | 160 |
| Lumen Technologies | 195 | 175 | 0 | 20 | 0 |
| Macy's | 110 | 0 | 90 | 20 | 85 |
| Marriott International | 20 | 0 | 0 | 20 | 175 |
| Paramount Skydance / Paramount Global | 20 | 0 | 0 | 20 | 175 |
| Pfizer | 195 | 175 | 0 | 20 | 0 |
| Salesforce | 65 | 0 | 45 | 20 | 130 |
| Southwest Airlines | 20 | 0 | 0 | 20 | 175 |

- 冻结时：Enphase、Lumen、Pfizer 跑完并经入口只读导出；JPMorgan（已中止，15 格）、Macy's、Salesforce、Ford（刚开始）为部分运行；Marriott、Paramount、Southwest 未开始。后台继续按公司补跑，补齐后出 v1.1。`NO_OBSERVATION` 只表示本版还没跑到，不按旧结果或发布包填补。
- D02：历史入口只在提供已保存法律审阅时处理 D02，本次未提供，所以 D02 状态取 main 上的准备对照：49 个可准备请求中，Ford FY2025 有能对上的保存回答，其余 38 个需要新回答；11 个准备失败（8 个原件定位/解析，3 个修订年报/继任主体）。

### 3. 已确认成果

定义：本次观察有值（或合理非数值终态），且已有原件核对记录与本次观察的值一致（按公司、指标、期间对齐，申报编号不同另标）。不按结果编号继承。

- 有值，且已有原件核对记录与本次观察一致：**272 格**（B04 19、B05 19、B08 18、B09 18、C01 18、D01 18、E02 18、E03 18、E04 18、E05 18、B07 17、C03 13、C04 13、B03 11）。
- 合理非数值终态且与参考分类一致（参考表不适用、本次为结构性不适用等）：**283 格**。参考表不是“不适用”、本次却是非数值终态的 3 格：Lumen Technologies B06 FY2025（参考 APPLICABLE，本次 NOT_MEANINGFUL DENOMINATOR_NONPOSITIVE Recognized borro）；Lumen Technologies B07 FY2023（参考 APPLICABLE，本次 NOT_MEANINGFUL RATIO_NUMERATOR_NOT_POSITIVE Source-rebu）；Lumen Technologies B07 FY2025（参考 APPLICABLE，本次 NOT_MEANINGFUL RATIO_NUMERATOR_NOT_POSITIVE Source-rebu）。
- 按现行规则合理扣留：7 格（Enphase Energy C04 FY2021、Lumen Technologies C04 FY2021、Macy's C04 FY2021、Pfizer B02 FY2021、Pfizer B02 FY2024、Pfizer C04 FY2021、Salesforce C04 FY2022）。
- **旧核对与本次观察不一致：19 格**（同格有登记错值 8 格；由同年/上年 B01 错值派生的 B02/B03 11 格）。其中 19 格能由登记错值解释：旧核对当时读到并判为一致的是收入小计或组成项（后已登记为错值），本次观察是总收入，例如 Lumen FY2021 B01 本次 19,687,000,000，旧读数 17,795,000,000。这些旧依据不沿用，需要对当前值重新核对原件。
  涉及：Lumen Technologies B01 FY2021（同格有登记错值）；Lumen Technologies B01 FY2022（同格有登记错值）；Lumen Technologies B01 FY2023（同格有登记错值）；Lumen Technologies B01 FY2024（同格有登记错值）；Lumen Technologies B01 FY2025（同格有登记错值）；Lumen Technologies B02 FY2021（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B02 FY2022（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B02 FY2023（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B02 FY2024（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B02 FY2025（同格有登记错值）；Lumen Technologies B03 FY2021（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B03 FY2022（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B03 FY2023（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B03 FY2024（由同年/上年 B01 错值派生的 B02/B03）；Lumen Technologies B03 FY2025（同格有登记错值）；Macy's B03 FY2023（由同年/上年 B01 错值派生的 B02/B03）；Pfizer B01 FY2023（同格有登记错值）；Pfizer B02 FY2023（由同年/上年 B01 错值派生的 B02/B03）；Pfizer B03 FY2023（由同年/上年 B01 错值派生的 B02/B03）。
- 有核对记录、本次没有值：600 格（多为运行未完成）；只有计数级记录（无逐格数值）：26 格。
- 本次有值但没有任何原件核对记录：0 格。
- 用户正式采纳（与上面的原件核对分开记录）：现行发布中逐项正式采纳 2 格（Marriott International B01 FY2025、Marriott International B10 FY2025）；随现行发布整体继承、没有逐项采纳记录 321 格；其余 1,627 格未采纳。依据：用户 2026-09-10 委托批准的 [发布决定](https://github.com/wlvh/SEC_metrics/pull/40#issuecomment-5611711644) 与 [执行记录](https://github.com/wlvh/SEC_metrics/blob/48b233f875d07145464e078afe686249e38e963b/docs/evidence/annual_formal_adoption/production-execution/README.md) （2 项采纳 + 其余继承；包内“待生产授权”字段按设计不改写，所以不能只看包内字段）

### 4. 未确认/未完成（原因、负责人、下一步）

| 类别 | 格数 | 其中参考适用子集 | 负责人 | 下一步 |
|---|---:|---:|---|---|
| 本次未取得观察（运行未完成） | 1,068 | 627 | 接收方 | 本次快照未取得观察（运行未完成或未覆盖） |
| 开发缺口：历史入口未接入 | 150 | 110 | #28/#47 | 历史入口未接入该指标或该族 |
| 需新模型回答（用户决定额度） | 52 | 52 | 用户 | 需新的模型回答；调用额度由用户决定（#153 第 6 节） |
| 开发缺口：不适用却以报错结束 | 36 | 0 | #28/#47 | 行业不适用却以报错结束，应输出结构性不适用 |
| 无保存的 D04 回答（用户决定额度） | 18 | 18 | #47/用户 | 该年没有已保存的 D04 回答；新增调用由用户决定，#47 确认含义 |
| 开发缺口：来源关系/输入未解决 | 17 | 17 | #28/#47 | 来源关系或输入未解决（B06 负债组成、银行输入等），按对应指标族处理 |
| 开发缺口：原件定位/解析 | 8 | 8 | #28/#47 | 原件定位/解析缺口，按对应 PR 处理 |
| 缺保存原件 | 6 | 6 | #47 | 缺保存原件：先查已有恢复来源，确需新 SEC 获取由用户决定 |
| 按规则扣留：冲突/歧义 | 5 | 5 | #47 | 按规则扣留（冲突/歧义）；开发者说明是否为合理终态 |
| 开发缺口：修订年报/继任主体 | 3 | 3 | #28/#47 | 修订年报/继任主体处理未接入 |
| 扣留（原因待归类） | 2 | 2 | #47 | 扣留原因待开发者归类 |
| 有匹配的保存回答（未运行） | 1 | 1 | #47 | 已有匹配的保存回答，按 D02 保存回答入口运行并读取 |

- **Macy's B01/B02**：FY2019 年报正文不在保存原件中，区间规则要求窗口内每份年报都读到财年标签，所以五年全部被阻断（已观察 6 格），已向 #47 补件。
- **B10/B11**：历史入口把非酒店公司也交给酒店模块并以报错结束（已观察 36 格，跑完为 90 格）；参考表这些格都是不适用，正确终态应为结构性不适用，已交 #47。
- **D04**：原因码末尾 `:0` 指账本中该年匹配的保存回答数为 0；#47 账本只有 Marriott FY2023/2024、Paramount FY2024。已问 #28 是否有当期 D04 保存包可复用。
- **E01**：14 格有需要内容确认的 8-K 候选但没有保存回答；已问 #47 是否别处有，否则由用户决定额度。
- `WITHHELD_OTHER` 2 格（Salesforce FY2022 B03、Macy's FY2022 C03）待 #47 说明是合理终态还是开发缺口；其中 Salesforce 那格 #47 旧记录从原件读到了 0.0463。

### 5. 当期视图与本次观察的对齐

当期视图取现行发布包 `publication_24bf8f1654f3…`（327 行）；按公司、指标、期间对齐后再比较，期间不同的行不跨期比较。323 行落在范围表的同期格上（其中 4 行落在非最近一年：Paramount Skydance / Paramount Global D01 FY2024、Paramount Skydance / Paramount Global D02 FY2024、Paramount Skydance / Paramount Global D03 FY2024、Paramount Skydance / Paramount Global D04 FY2024），4 行的期间对不上任何格。

| 当期格（390） | 格数 |
|---|---:|
| 发布包有值／当前 main 本次未取得观察 | 112 |
| 发布包合理非数值终态／当前 main 本次未取得观察 | 72 |
| 发布包没有该行 | 63 |
| 两边都有值且相同 | 43 |
| 发布包有文字结论／当前 main 未出结果 | 32 |
| 两边都是合理非数值终态，状态相同 | 26 |
| 发布包有文字结论／当前 main 本次未取得观察 | 11 |
| 发布包该行属于其他期间（不跨期比较） | 8 |
| 发布包未出结果／当前 main 本次未取得观察 | 7 |
| 发布包合理非数值终态／当前 main 未出结果 | 7 |
| 发布包有值／当前 main 未出结果 | 3 |
| 两边都有文字结论（发布包文字在证据表，本版未逐字比较） | 3 |
| 两边都有值但不同 | 3 |

- 两边都有值但不同：Lumen Technologies B01 FY2025 本次 12402000000 / 发布包 11331000000；Lumen Technologies B02 FY2025 本次 -0.05386023802 / 发布包 -0.06579272817；Lumen Technologies B03 FY2025 本次 0.156184486373 / 发布包 0.170946959668。
- 发布包有值、当前 main 未出结果：E01 2、B06 1。原因见各格 `terminal_class`（历史入口未接入、扣留或缺回答），不按发布包补值。
- 发布包行的期间与该公司最近财年不一致：Macy's B10（发布包 2025-12-31，本格 2026-01-31）；Macy's B11（发布包 2025-12-31，本格 2026-01-31）；Paramount Skydance / Paramount Global D01（发布包 2024-12-31，本格 2025-12-31）；Paramount Skydance / Paramount Global D02（发布包 2024-12-31，本格 2025-12-31）；Paramount Skydance / Paramount Global D03（发布包 2024-12-31，本格 2025-12-31）；Paramount Skydance / Paramount Global D04（发布包 2024-12-31，本格 2025-12-31）；Salesforce B10（发布包 2025-12-31，本格 2026-01-31）；Salesforce B11（发布包 2025-12-31，本格 2026-01-31）。
- **发布包在已登记错值（已撤回）的格子上仍有值：10 格**。其中 4 格发布值与登记的错值完全相同（Lumen Technologies B01 FY2025；Lumen Technologies B02 FY2025；Lumen Technologies B03 FY2025；Macy's B02 FY2025）；其余 6 格登记里没有记下错值本身，无法从材料判断发布值是否就是被撤回的那一个（Ford Motor Company E01 FY2025；Lumen Technologies E01 FY2025；Macy's E01 FY2025；Pfizer E01 FY2025；Salesforce B03 FY2026；Southwest Airlines E01 FY2025）。
- **Macy's 可能还有未登记的同类错值**：FY2024、FY2025 年报同时标了总收入 `Revenues`（23,006,000,000 / 22,621,000,000）和净销售额，而现行发布 FY2025 B01 = 21,764,000,000（净销售额）、#47 旧读数 FY2024 B01 = 22,293,000,000（净销售额）；FY2023 同类读数已登记为错值。已请 #28 确认登记。FY2021/2022 年报只标了净销售额，当前 main 对这两年取净销售额、FY2023 起取总收入，增长率前后口径不一致，是否统一由用户决定。

### 6. 材料缺口与补件请求

- #47（历史侧）：[补件请求](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-6165601387) —— Macy's FY2019 年报正文、B10/B11 不适用报错、19 格旧核对需对当前值重读原件、2 格扣留归类、14 格 E01 保存回答、JPMorgan 运行速度。
- #28（当期/发布侧）：[补件请求](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6165605691) —— 发布包 10 格已撤回值的处理、Macy's FY2024/2025 收入口径是否登记、发布包 8 行期间不一致、当期 D04 保存包、公司入口当期导出（可选）。
- 需要用户决定（不变，汇总于此）：D02 新回答 38 个（#262 合入后 Pfizer 再加 5 个）、D04/E01 新回答（视补件结果）、Macy's FY2019 年报是否新增 1 次 SEC 获取（视 #47 回复）、现行发布中已撤回值是否替换发布（视 #28 方案）。

### 7. 生成方法

- 生成命令、输入范围与列定义见 [README](https://github.com/wlvh/SEC_metrics/blob/b389b3903a30598ce0662a756b4503c0d425cfd7/docs/receiver/progress_snapshot_v1/README.md) ；`output/history_rows.csv` 保存本次全部观察，后续只需补跑未完成公司再重建表。
- 当前 main 观察：main `681b35d8` 上公司入口离线运行（网络禁用），每家公司新目录，不写旧状态；冻结后对 689 个逐格记录核对处理文件摘要，与 main 全部一致，新增调用全为 0（`output/run_identity.json`）。
- 核对依据按公司、指标、截止日对齐后比较数值（文字按摘要），不按结果编号继承；有登记错值的旧依据单列，不沿用。参考分类直接取参考表原始字段，四类互斥，待确认不并入适用或不适用。

新增 SEC/模型/付费调用 0/0/0；旧状态未改写；未改业务目标、验收标准与权限。

---
_Generated by [Claude Code](https://claude.ai/code)_
