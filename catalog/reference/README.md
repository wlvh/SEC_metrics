# Metrics reference tables（SIC × Metrics 映射表与指标定义表）

状态：参考数据，不是运行配置。本目录不被任何生产加载器扫描（现有加载器只
glob `catalog/metrics/*.md`、`catalog/disclosures/*.md`、`catalog/r4_v2/*.md`），
不改变 pipeline 如何选择、提取、计算或发布指标；`source_selection.json` 不是生
产激活指针。来源：[Issue #44](https://github.com/wlvh/SEC_metrics/issues/44)。

## 两张表回答什么

| 表 | 文件 | 回答的问题 |
|---|---|---|
| SIC × Metrics 映射表 | `generated/sic_metric_map.json`（权威）/ `.csv`（派生阅读视图） | 这个行业配置应该看哪些指标？业务适用性、优先级、条件与依据是什么？ |
| Metrics 定义表 | `generated/metric_definitions.json`（权威）/ `.csv`（派生阅读视图） | 指标是什么意思，从哪张 filing / 哪个字段或定位规则取数，怎么算，单位、期间、统计范围、限制是什么？定义来自哪个版本，实现/验证到什么程度？ |

映射表是长格式：一行 = 一个基线 SIC 范围 × 一个 metric ID，共 10 个范围 × 39 个
指标 = 390 行。定义表每个 metric ID 一条记录，其中 `applicable_sic_ranges` 只能由
映射表反向生成。

## 文件与维护位置

```text
catalog/reference/
  README.md                 本文件
  source_selection.json     显式来源清单：每个指标按哪个明确绑定选取哪个已提交定义；
                            inputs 的 sha256 是漂移检测依据；development_references
                            只记录 PR #43 固定提交的路径与摘要，生成时不读取
  metric_metadata.json      唯一的人工补充：中英文名称/说明、legacy 方法说明及代码引用、
                            预期状态、限制、验证范围说明
  sic_metric_rules.json     唯一手工维护的行业↔指标业务关系（按 traits / profile 的有序 clause）
  generated/                生成结果，不得手改
tools/generate_metrics_reference.py   生成器（生成 / --check / --refresh-source-digests）
tests/test_metrics_reference.py       专项测试（独立预期 + 反例）
.github/workflows/metrics-reference.yml  短 CI：--check 与专项测试
```

单一维护原则：

- SIC 范围只在 `config/metric_applicability.yaml#profile_rules` 维护；本目录只给范围加中英文标签，生成器校验标签与基线范围精确一致。
- 行业 → traits 只在 `catalog/company_traits.yaml` 维护。
- 公式、依赖、来源优先级、guard、单位、applicability 从所选机器来源（MetricSpec 前置 JSON、`catalog/deterministic_metrics.json`、`catalog/event_routes.json`、`config/source_strategy_registry.json` 等）读取，不在元数据中重复维护。
- 元数据里的 `citations`（path / symbol / literals）由生成器逐条核对存在，说明与代码漂移时生成失败。

## 命令

```bash
python3 tools/generate_metrics_reference.py --check
```

只读校验：核对 40 个声明输入的摘要（数据/文档文件为整文件 sha256；`scripts/sec_pipeline.py`、`scripts/vnext/calculator.py`、`scripts/vnext/zero_ai_r2.py` 三个代码引用目标为 `digest_scope=cited_symbols`，只对被引用的顶层符号块取摘要，文件其他位置的无关改动不算漂移），再在内存中生成并与 `generated/` 逐字节比较；不写盘。

```bash
python3 tools/generate_metrics_reference.py
```

生成并写入 `generated/` 四个文件。相同已提交输入得到相同字节（sorted keys、无时间戳、无绝对路径）。

```bash
python3 tools/generate_metrics_reference.py --refresh-source-digests
```

声明输入内容变化后显式更新 `source_selection.json` 的 sha256（只改这些字段），随后重新生成并审阅差异。这是唯一会修改 `source_selection.json` 的命令。

```bash
python3 -m unittest tests.test_metrics_reference -v
```

## 版本选择原则（EXPLICIT_BINDING_FIRST）

按明确用途对应的 Requirement / 发布计划 / 运行配置绑定选取冻结版本，不按最大 vN、
最近修改时间或最早冻结版本自动选取：

| 绑定 | 指标 | 选取的定义 | 状态标签 |
|---|---|---|---|
| active R3 发布计划 `config/release_plans/issue_15_lodging_r3.json` | A01 A02 A05 A06 A07 A08 A10 B02 B04 B05 B07 B08 B09 B12（确定性目录）、B01 B03 B10 B11（MetricSpec）、C01 E01–E05（事件路由） | 目录成员 / `catalog/metrics/*.md` / 路由成员 | `ACTIVE_VNEXT_RELEASE_R3` |
| R4 离线计划 `config/release_plans/issue_28_r4_scoped_engine_v3.json` | A03 A04 A09 A11 A12 A13 | `catalog/r4_v2/*.md`；Issue #15 的 `catalog/metrics/*.md` 作为历史变体 | `R4_OFFLINE_PLAN_NOT_ACTIVE` |
| R5 政策 `config/r5_b06_structured_v1.json` | B06 | `catalog/r5/B06_structured.md`；`catalog/metrics/B06_debt_to_equity.md` 为回退表格合同，`r5/history` 为被取代版本 | `R5_STRUCTURED_DRAFT_NOT_AUTHORIZED` |
| Issue #15 表格合同 `catalog/table_task_contracts.json` | B13 | `catalog/metrics/B13_capacity_utilization.md` | `NOT_IN_VNEXT_RELEASE_PLAN` |
| 文字定义 `02_指标定义_SEC_10公司单年指标.md` + legacy 代码引用 | C02 C03 C04 D01 D02 D03 D04 | 定义文档章节；方法来自 `scripts/sec_pipeline.py` 的符号/字面量引用 | `NOT_IN_VNEXT_RELEASE_PLAN` |

PR #43（固定提交 `8346c326f04be5a863dc8bf2f010087a6f2025a3`）上的后继 Spec 只以
`development_references`（path + sha256 + 一句说明）记录，`verified_by_generator=false`；
它们不是定义来源，也不代表上线状态。D03 在 main 与该提交上都没有 Spec。

## 三个独立维度

- **业务适用性**（映射表 `business_applicability`）：APPLICABLE / CONDITIONAL / NOT_APPLICABLE / PENDING_CONFIRMATION，来自 `sic_metric_rules.json` 的有序 clause；`business_priority` 是本目录的编制默认值（`priority_basis`），不是 pipeline 规则。
- **结构性适用性**（映射表 `structural_applicability`）：由所选定义的 `applicability.all/none` 对行业 traits 求值（语义同 `scripts/vnext/calculator.py::metric_is_applicable`）。生成器拒绝“结构性不适用但业务标为适用”的规则。
- **实现/验证情况**（定义表 `implementation_status`）：vNext 状态来自发布计划/政策文件的显式绑定；legacy 状态来自代码引用；`verification_scope_note` 说明基线证据只覆盖 10 家样本公司。有 Spec 不等于已上线，无 Spec 不等于只有未来规划。

未命中任何基线范围的 SIC：映射表 `unmatched_sic_policy` = PENDING_CONFIRMATION，并记录
legacy pipeline 的运行默认（`profile_from_sic_rules` 返回 `default_non_fi`）。范围重叠会
使生成失败。SIC 以四位字符串保存并保留前导零，范围含端点。

## 边界

- 不修改任何 MetricSpec、`config/metric_applicability.yaml`、抽取/计算/路由/发布实现、历史 Requirement 或证据。
- 生成、校验与 CI 只使用本分支已提交的数据：不 import / 执行 PR #43 代码，不调用 git，不联网。
- 本目录不证明任何 SIC 或行业能成功提取；扩展新行业属于后续任务。
