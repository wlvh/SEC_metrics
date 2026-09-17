# Issue #44 业务验收记录（基线 main `fa56b59`，2026-09-17）

只读验收：直接读取合入 main 的 `catalog/reference/generated/sic_metric_map.json` 与
`metric_definitions.json`，未运行 pipeline、未做真实调用。验收者：Claude Code 代用户执行；
场景与预期由 GPT 6 Pro 审阅意见提出。

## 五个 SIC 场景

| SIC | 命中配置 | 结果 | 判断 |
|---|---|---|---|
| 7011 | 酒店住宿 | 24 项适用（含 B10、B11，条件写明当年 / Comparable Systemwide / Worldwide 绝对值）；B13 待确认 | 通过 |
| 6021 | 商业银行 | A01–A13 适用；B08 结构性排除；**B06 记为 NOT_APPLICABLE，依据只引用定义文档 B 组标题** | 不通过 |
| 3711 | 制造业 | 22 项适用；B13 条件适用（需可计算的产量与产能披露） | 通过 |
| 7372 | 订阅/合同收入 | 23 项适用，含 B12 且写明 RPO/cRPO 替代观测 ≠ ARR ≠ churn；B13 待确认 | 通过 |
| 9999 | 未命中 | PENDING_CONFIRMATION，并说明 legacy `default_non_fi` 只是运行默认 | 通过 |

## 三个定义抽查

- B03：`((operating_income + depreciation_and_amortization) / revenue)`，收入复用 B01，四项 guard + 年度时长 300–400 天 + 分母非零，单位 ratio；示例 100/20/5 → 0.25 = 25%。通过。
- B10：reported percent → canonical ratio（乘数 100），范围固定 comparable / systemwide / worldwide，禁止混淆项明确。通过。
- D04：参考实现 legacy 关键词规则；目标路线 auditor_fact_v1 结构化优先 + text 回退，main 未绑定 concept。通过；补充措辞：关键词未命中只是有界未命中，不是有充分证据的无疑虑结论。

## 不通过项的根因与修复

所选 B06 定义为 R5（`config/r5_b06_structured_v1.json`），其 `debt_scope_definition.bank_scope` 为
"Separate bank funding scope and comparability limitation; no netting assets"，`excluded` 含
`customer_deposits`；`docs/evidence/r5_b06_scope/debt_scope_relationships.json` 有 JPM
`bank_funding` 范围记录（`complete=false`，`BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED`），
`docs/r5_b06_structured.md` 说明新集合明确适用于十公司并新增 JPM B06 明确阻断行。映射表却按更早的
定义文档分组把银行 B06 写成 NOT_APPLICABLE，把"资料不完整、未获生产授权"错编码为"业务不适用"。

修复（本目录所在提交）：银行 B06 改为 CONDITIONAL / SUPPLEMENTARY，条件与依据引用 R5 政策与证据；
生成器新增规则：NOT_APPLICABLE 子句的 basis 只能引用定义层来源，不得引用证据目录、发布计划或
`production_authorized` 等实现/授权状态；新增正反测试；B13 对银行的 NOT_APPLICABLE 保留并补强定义层依据；
D04 描述补充"有界未命中"。定义表 B06 的 `applicable_sic_ranges` 随映射表反向生成，现包含 6020–6029 CONDITIONAL。
