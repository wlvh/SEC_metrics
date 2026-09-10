# SEC_metrics AI-First FSD v3.3.1

## 不对称验证版：冻结的三切片 PoC Implementation Baseline

| 属性 | 值 |
|---|---|
| 文档版本 | 3.3.1 |
| 日期 | 2026-07-28 |
| 状态 | **FROZEN IMPLEMENTATION BASELINE** |
| 适用项目 | `wlvh/SEC_metrics` |
| 本期切片 | B01 Revenue；B10/B11/ADR 酒店披露组；B03 EBITDA margin |
| 本期目标 | 证明 AI 可以替代频繁变化的酒店表格语义解析，同时不让程序重新长出第二套 Resolver，并维持现有 CSV、Golden、Validation 和报告 |
| 后续修改原则 | 不再进行架构重写；只有真实实现、mutation 或回归暴露问题时，才以小型 patch 修改本文 |

---

# 1. 最终决策

SEC_metrics vNext 的首期主链固定为：

```text
现有 request ledger、filing inventory 与不可变 SEC 原始材料
        ↓
结构化字段直接读取；复杂表格由一个 AI Reader 阅读
        ↓
AI 输出候选、精确 locator、原始值及 period/unit/scope 主张
        ↓
Evidence Checker 做不对称机械核验
  - 文件、表格、行列和单元格真实存在
  - 原始数字可从 locator 重取
  - AI 引用的表头和标签确实位于局部上下文
  - 数字、百分比、负号和单位可规范化
  - 程序不重新理解酒店业务语义
        ↓
Semantic Review
  - period/scope 等复杂财务主张由人审核
  - ReviewDecision 与候选、Spec 和证据绑定
        ↓
Verified Observation
        ↓
确定性 Calculator 计算 B03 等派生指标
        ↓
Metric Result + Execution Trace + Run Manifest
        ↓
Legacy Projector 合并现有完整结果并投影旧格式
        ↓
现有 Golden / Validation
        ↓
原子替换旧 CSV 与 evidence；报告只读
```

一句话概括：

> **AI 负责语义解题；程序负责证据验真、数值重取和公式计算；人负责批准无法低成本机械证明的经济口径。**

程序不得为了“验证 AI”而重新搜索文件、重新选择行列或重新实现酒店、银行等行业语义。

---

# 2. 本期范围与非目标

## 2.1 本期必须实现

1. 冻结当前完整基线，并复用现有 request ledger、raw evidence、hash 和 provenance；
2. 新产物隔离写入 `artifacts/vnext/`，不得在 shadow 阶段覆盖现有输出；
3. B01 使用现有确定性结构化选择路径，不为了架构统一而强制经过 AI；
4. B10/B11/ADR 由一次 AI 表格读取产生候选；
5. Evidence Checker 仅实现 locator、raw value、显式标签、数字规范化和酒店恒等式；
6. PoC 酒店指标必须经过人工 ReviewDecision；
7. B03 的 direct/fallback、guard、cross-check 和质量传播全部由 MetricSpec 表达；
8. Legacy Projector 生成完整 `metrics_matrix.csv` 和 `metric_evidence.csv` staging；
9. 对 staging 运行现有 Golden、Validation 和报告；
10. 切换后旧路径不得再写入 B01/B03/B10/B11，酒店旧 resolver/repair 必须删除或永久不可达。

## 2.2 本期明确不实现

- 通用 deterministic scope parser；
- 通用 Scope Terms Registry 或 CompanyRule engine；
- Source Recipe、layout fingerprint 和 Recipe cache；
- 默认双 Reader、Critic 或 Adjudicator；
- A02、B06、E02 和定性指标；
- 完整 `NOT_DISCLOSED_CONFIRMED` / Coverage 平台；
- 自动发布毕业机制；PoC 的 AI 表格事实始终要求人工 ReviewDecision；
- Databricks `current/as-of/NO_CHANGE`；
- 双解析器、taxonomy package service、通用 API；
- 为每种逻辑对象建设独立服务、数据库或 repository layer；
- 通用 cross-source reconciliation 引擎；B01 复用现有选择与 cross-check 行为。

---

# 3. 不可违反的不变量

| ID | 不变量 |
|---|---|
| INV-01 | AI claimed value 永不得直接进入正式结果；AI value 与 locator 重读值不一致时，Candidate 必须拒绝并重新提取。 |
| INV-02 | AI 对 period、unit、scope 的主张必须绑定局部证据；复杂 scope 必须有 ReviewDecision。 |
| INV-03 | Evidence Checker 不得重新搜索整份 filing、独立选择候选或实现行业语义解析。 |
| INV-04 | 为验证一个新指标而新增指标、公司或行业专用语义 Python，默认视为架构失败。 |
| INV-05 | 已结构化且可唯一选择的 SEC 字段不得为了统一而重新经过 AI。 |
| INV-06 | 派生指标只能引用 Verified Observation；未声明的 fallback 不得执行。 |
| INV-07 | 报告不得联网、修补、upsert、刷新 Golden 或改写任何权威数据。 |
| INV-08 | 历史 Run 重放不得重新调用 AI；必须读取冻结资产、Candidate、ReviewDecision、Observation 和 Trace。 |
| INV-09 | Candidate、EvidenceCheck、ReviewDecision、VerifiedObservation 和 MetricResult 必须逻辑隔离。 |
| INV-10 | 同一业务内容不得因模型元数据、日志、时间戳或无语义代码重构而改变内容身份。 |
| INV-11 | 已迁移指标必须先经 Legacy Projector 维持现有功能，再禁用旧写路径。 |
| INV-12 | filing 内容全部按不可信数据处理，不得改变系统提示、工具权限或写权限。 |
| INV-13 | Phase 1 Cutover 默认要求严格字段 parity；任何旧结果修正必须另开方法论 PR，不得以“approved correction”口头放行。 |
| INV-14 | AI 指定的目标表必须以完整表格或明确有界的行列上下文展示给审核者，审核视图不得只展示 AI 自己筛选出的候选。 |

---

# 4. 首期物理结构

```text
catalog/
  company_traits.yaml
  metrics/
    B01_revenue.md
    B03_ebitda_margin.md
    B10_occupancy.md
    B11_revpar.md
  disclosures/
    lodging_kpi_table.md

artifacts/vnext/runs/<run_id>/
  records.jsonl
  review_decisions.jsonl
  manifest.json
  validation.json

artifacts/vnext/reports/<run_id>/
  review.md
  report_manifest.json

artifacts/vnext/staging/<run_id>/
  metrics_matrix.csv
  metric_evidence.csv
  projection_manifest.json
```

`records.jsonl` 使用 `record_type` 区分：

```text
SOURCE_REFERENCE
DERIVED_ASSET
STRUCTURED_OBSERVATION_CANDIDATE
AI_EXTRACTION_RUN
OBSERVATION_CANDIDATE
EVIDENCE_CHECK
VERIFIED_OBSERVATION
METRIC_RESULT
EXECUTION_TRACE
```

Run 在 `status=FROZEN` 前可以写入 ReviewDecision；冻结后目录内文件不得修改。`review.md` 是可重复生成的只读视图，不属于冻结输入。

首期只需要以下模块或等价边界：

```text
compile_spec
build_table_grid
read_structured_fact
run_ai_reader
check_evidence
apply_review_decision
calculate_result
project_legacy
render_review
```

---

# 5. Evidence 与来源身份

## 5.1 复用现有抓取与 provenance

vNext 不重建 SEC 获取系统。必须复用现有：

- request ledger；
- filing/accession inventory；
- raw response body；
- content SHA-256；
- portable locator；
- request attempt provenance；
- material inventory。

## 5.2 RawBlob 与 SourceReference

RawBlob 只表达 exact bytes：

```yaml
record_type: RAW_BLOB
raw_asset_id: sha256:<exact bytes>
byte_length: 123456
media_type: text/html
storage_uri: ...
```

SourceReference 表达该内容在 SEC filing 中的身份：

```yaml
record_type: SOURCE_REFERENCE
source_reference_id: sha256:<canonical source reference>
raw_asset_id: sha256:...
source_url: ...
accession: ...
document_name: ...
source_role: target_10k_primary
request_attempt_id: ...
```

相同 bytes 可以对应多个 SourceReference，不得覆盖 provenance。

正式 Observation 必须绑定：

```text
raw_asset_id
source_reference_id
accession
document_name
source_role
```

以下字段只属于审计，不进入事实内容身份：

```text
retrieved_at_utc
request_attempt_id
本地绝对路径
```

## 5.3 最小 Source Manifest

每个 Run 的 `manifest.json` 至少包含：

```yaml
run_id: ...
status: OPEN | FROZEN | FAILED
company_id: ...
target_period: ...
source_references:
  - source_reference_id: ...
    source_role: target_10k_primary
    accession: ...
    document_name: ...
    raw_asset_id: ...
missing_required_source_roles: []
spec_file_hashes: {...}
records_file_hash: ...
review_decisions_file_hash: ...
validation_file_hash: ...
content_manifest_hash: ...
audit_manifest_hash: ...
```

本期不从 Manifest 推导完整“未披露”结论；它只证明实际使用了哪些文件、来源角色和期间。

## 5.4 DerivedAsset

首期只支持 table-grid：

```yaml
record_type: DERIVED_ASSET
derived_asset_id: sha256:<canonical grid bytes>
parent_raw_asset_ids: [sha256:...]
transform_id: html_to_table_grid
transform_semantic_version: "1"
content_type: application/vnd.secmetrics.table-grid+json
storage_uri: ...
```

规则：

- AI 可以读取 table-grid；
- locator 可以指向 table-grid；
- derived bytes 必须 content-addressed 保存；
- 当前在役 transform 必须能从 RawBlob 重建同一 grid；
- 历史重放可以直接读取永久保存的 derived bytes，不要求永久保留所有旧 transform 运行环境。

---

# 6. MetricSpec

## 6.1 文档与哈希

MetricSpec 使用 Markdown + YAML front matter。

YAML 是正式机器语义；正文承载财务定义、AI 任务、审核问题和示例。

必须分别生成：

```text
spec_semantic_hash
prompt_bundle_hash
```

`spec_semantic_hash` 包含：

```text
metric_id
kind
canonical_unit
applicability
required_claims
forbidden_confusions
inputs
formula
guards
quality rules
legacy_projection
review_policy
```

`prompt_bundle_hash` 包含：

```text
spec semantic bundle
AI instructions
正例/反例
prompt template version
disclosure group context
```

纯背景文字和作者备注不得进入任何 hash。

## 6.2 最小 Applicability

首期只支持基于公司 trait 的：

```yaml
applicability:
  all: [lodging]
  none: []
```

`company_traits.yaml` 可以由现有 SIC/profile/registry 投影生成，不建设新规则引擎。

行为：

- 条件满足：`APPLICABLE`；
- 条件不满足：`N_A_STRUCTURAL`，不调用 AI、不运行计算；
- Legacy Projector 仍必须按基线要求生成结构性不适用行；
- 不得写 `if company == ...`。

## 6.3 B10 示例

```markdown
---
metric_id: B10
name: Occupancy
kind: direct_numeric
canonical_unit: ratio
reported_unit: percent
source_mode: ai_table
applicability:
  all: [lodging]
required_claims:
  period_role: current_fiscal_year
  property_population: comparable
  operating_scope: systemwide
  geography: worldwide
forbidden_confusions:
  - prior_year
  - percentage_change
  - company_operated
  - regional_only
review_policy: human_required_during_poc
legacy_projection:
  unit: percent
  value_multiplier: "100"
  status_exact: MDA_OK
  source_class: MDA
---
```

AI 返回 `73.1%`；Canonical Observation 保存：

```text
value = 0.731
unit = ratio
```

Legacy Projector 输出：

```text
value = 73.1
unit = percent
```

程序不负责证明“Comparable Systemwide Worldwide 在酒店方法论上就是 B10”；它只验证相关标签真实位于目标表格上下文。该语义由 ReviewDecision 批准。

## 6.4 B03 完整 Contract

B03 不得引用未定义角色，也不得把 fallback 隐藏进 Python。

```yaml
metric_id: B03
kind: derived_numeric
canonical_unit: ratio
applicability:
  all: [non_financial]

inputs:
  revenue:
    reuse_metric_observation: B01

  operating_income:
    choose_first:
      - extraction_role:
          approved_concepts:
            - us-gaap:OperatingIncomeLoss
          quality: EXACT

      - derived_role:
          op: subtract
          inputs:
            pretax:
              approved_concepts:
                - us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest
                - us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments
            nonoperating:
              approved_concepts:
                - us-gaap:NonoperatingIncomeExpense
                - us-gaap:OtherNonoperatingIncomeExpense
          quality: APPROX
          guards:
            - same_accession
            - same_period
            - same_entity
            - compatible_units
          cross_check:
            when_available: true
            inputs:
              costs_and_expenses:
                optional: true
                choose_first_concepts:
                  - us-gaap:CostsAndExpenses
                guards:
                  - same_accession
                  - same_period
                  - same_entity
                  - compatible_units
            expression:
              op: subtract
              args: [revenue, costs_and_expenses]
            relative_tolerance: "0.01"

  depreciation_and_amortization:
    choose_first:
      - extraction_role:
          approved_concepts:
            - us-gaap:DepreciationDepletionAndAmortization
            - us-gaap:DepreciationAmortizationAndAccretionNet
            - us-gaap:DepreciationAndAmortization
          quality: EXACT

      - derived_role:
          op: add
          inputs:
            depreciation:
              approved_concepts: [us-gaap:Depreciation]
            amortization:
              approved_concepts: [us-gaap:AmortizationOfIntangibleAssets]
          quality: EXACT
          quality_reason: COMPOSED_FROM_EXACT_COMPONENTS
          guards:
            - same_accession
            - same_period
            - same_entity
            - compatible_units

top_level_guards:
  - same_accession
  - same_period
  - same_entity
  - compatible_units
  - annual_duration: [300, 400]
  - denominator_nonzero

formula:
  op: divide
  args:
    - op: add
      args: [operating_income, depreciation_and_amortization]
    - revenue

quality_rule:
  operating_income_direct: EXACT
  operating_income_reconstructed: APPROX
  dna_direct: EXACT
  dna_composed: EXACT
```

硬规则：

1. direct combined D&A 被选中时，不得再额外加回独立 amortization；
2. `CostsAndExpenses` 不存在时，允许 OI 重建继续，但 Trace 必须记录 `CROSS_CHECK_UNAVAILABLE`；
3. `CostsAndExpenses` 存在但 context 不兼容时不得用于 cross-check；
4. cross-check 可执行且误差超过 1% 时，该 OI reconstruction 路径失败；
5. 任意顶层输入跨 accession、period、entity 或 unit 时，B03 必须 WITHHELD；
6. annual duration 不在 300–400 天，或 denominator 为 0 时，结果为 `NOT_MEANINGFUL`，不得伪装为来源缺失；
7. `reuse_metric_observation: B01` 必须在相同 company、period 和 canonical scope 下唯一命中；0 条或多条均失败，不得静默选择第一条；
8. B03 的 `spec_closure_hash` 必须包含 B01 的 closure hash。

---

# 7. AI Reader 与 Candidate

## 7.1 Lodging Disclosure Group

一次 AI Extraction Run 必须同时返回：

```text
occupancy
revpar
adr
```

不得按三个指标分别读取同一张表。

## 7.2 Candidate Schema

```yaml
record_type: AI_EXTRACTION_RUN
run_id: ...
raw_or_derived_asset_ids: [...]
prompt_bundle_hash: sha256:...
model_fingerprint: ...
reader_output:
  disclosure_group: lodging_kpi_table
  table_locator:
    derived_asset_id: sha256:...
    table_id: table_17
  candidates:
    - role: occupancy
      claimed_raw_value: "73.1%"
      claimed_period: FY2025
      claimed_reported_unit: percent
      claimed_scope:
        property_population: comparable
        operating_scope: systemwide
        geography: worldwide
      locator:
        derived_asset_id: sha256:...
        table_id: table_17
        row_path: [Worldwide]
        column_path: [2025, Occupancy]
      scope_evidence_locators:
        - {location: table_caption, text: "Comparable Systemwide Properties"}
        - {location: row_path, text: "Worldwide"}
      competing_candidates:
        - claimed_raw_value: "75.4%"
          locator:
            derived_asset_id: sha256:...
            table_id: table_17
            row_path: [Worldwide]
            column_path: [2025, Company-operated Occupancy]
          rejection_reason_claim: company_operated
```

每个正式 competing candidate 必须有可重放 locator。无法定位的主张只能进入：

```yaml
unresolved_competing_claims:
  - description: ...
```

存在 unresolved claim 时，Candidate 必须 `REVIEW_REQUIRED`。

## 7.3 Candidate 内容身份

`target_candidate_hash` 必须按以下业务内容生成：

```text
metric/disclosure role
raw/derived asset IDs
source_reference IDs
selected locator
claimed period/unit/scope
claimed raw value
competing candidate locators and claims
```

不得包含：

```text
run_id
model fingerprint
时间戳
自由解释文字
日志
```

同一候选在同一文件上重新运行，只要 substantive claims 和 locator 不变，ReviewDecision 可以继续命中。

## 7.4 Prompt Injection 边界

- filing 内容必须位于明确的数据区；
- filing 中的指令性文字不得改变系统要求；
- AI Reader 无 shell、文件写入、网络扩权和数据库写权限；
- AI 输出必须通过 schema 校验。

---

# 8. Evidence Checker：不对称机械核验

## 8.1 必须做的检查

Evidence Checker 只能做以下通用检查：

1. asset 与 SourceReference 存在且 hash/关系匹配；
2. table/row/column/span/fact locator 可解析；
3. locator 指向的 raw cell/text 真实存在；
4. AI claimed raw value 与 locator 重读 raw value 必须一致；不一致时 Candidate 直接 `REJECTED`，不得用重读值替换后继续；
5. 百分比、负号、括号、million/billion 等按统一数值政策规范化；
6. AI 引用的 header、caption、row、label 文本真实位于同一局部表格路径；
7. AI 声称的 period/unit 若有明确 header/caption，所引标签必须真实存在；
8. selected 和 competing candidate 的 locator/raw value 均真实存在；
9. 生成目标表的完整 review context：至少包含 AI 指定的完整表格，或该表全部行 × Occupancy/RevPAR/ADR 角色列与全部年度列；不得只展示 AI 选择的子集；
10. 酒店三项满足恒等式容差；
11. ReviewDecision 的 approved claims 必须满足 MetricSpec required claims；这是 canonical 字典/谓词比对，不是程序自行解释语义；
12. B03 Trace 必须可由 Verified Observations 重算。

## 8.2 明确禁止

Evidence Checker 不得：

- 独立搜索整份 filing 寻找目标表；
- 独立选择正确 row/column；
- 判断 Comparable/Systemwide/Worldwide 的行业经济含义；
- 重新给 selected/competing candidate 做语义排序；
- 判断 standardized/advanced 哪个是目标方法学；
- 为新指标增加专用 scope parser；
- 在 Python 中维护公司或行业专用 label 词库；
- 依据“看起来合理”替换 AI locator；
- 把“机械展示同一目标表的全部行列”扩张成全文语义召回器。

如果语义判断不能通过局部机械证据和 canonical claims 比对完成，必须进入 Review，而不是扩张 Checker。

## 8.3 数值政策

```yaml
numeric_policy:
  decimal_precision: 28
  rounding: ROUND_HALF_EVEN
  serialization: fixed_point
  normalize_trailing_zeros: true
  allow_nan: false
  allow_infinity: false
  percent_to_ratio: divide_by_100
```

规则：

- `73.1%` 的 canonical value 是 `0.731`；
- Legacy percent 投影时乘以 `100`；
- 所有中间计算使用 Decimal；
- hash 使用 fixed-point canonical string；`0.7310` 与 `0.731` 规范化为同一值；
- null、空集合和字段缺失不得混同。

Canonical JSON：UTF-8、object key 排序、集合字段稳定排序、LF 换行。

## 8.4 酒店 Identity

```yaml
identity:
  expected: adr * occupancy
  actual: revpar
  tolerance:
    kind: relative
    value: "0.01"
```

`occupancy` 使用 canonical ratio。三个披露值允许因独立四舍五入产生 1% 以内相对误差。

---

# 9. Semantic Review

## 9.1 PoC Review 策略

| 来源 | Review 要求 |
|---|---|
| B01 唯一结构化事实 | 无人工 Review，沿用现有确定性规则 |
| B10/B11/ADR AI 表格 | 必须有 HUMAN ReviewDecision |
| B03 | 输入和计算通过即可；APPROX 路径必须在 review.md 显示 |

PoC 不实现自动发布毕业机制。任何 AI 表格新 filing 均需要人工 ReviewDecision；是否引入自动批准必须在 PoC 后另立需求。

## 9.2 ReviewDecision

```yaml
review_decision_id: sha256:<full audit decision>
target_candidate_hash: sha256:<content-based candidate>
decision: APPROVE | REJECT
approved_claims:
  period_role: current_fiscal_year
  reported_unit: percent
  scope:
    property_population: comparable
    operating_scope: systemwide
    geography: worldwide
reviewed_spec_semantic_hash: sha256:...
reviewed_source_bindings:
  - source_reference_id: ...
    raw_asset_id: ...
    accession: ...
    document_name: ...
reviewer_type: HUMAN
reviewer_id: ...
decided_at_utc: ...
reason: ...
```

生成独立：

```text
approval_effect_hash = hash(
  target_candidate_hash
  + decision
  + approved_claims
  + reviewed_spec_semantic_hash
  + reviewed_source_bindings
)
```

`approval_effect_hash` 进入业务内容；reviewer、时间和理由只进入审计。

规则：

- ReviewDecision 不得修改 Candidate；
- Candidate substantive content、Spec、source binding、locator 或 approved claims 变化后，旧决定失效；
- ReviewDecision 不得直接赋值 Publication；
- `approved_claims` 必须满足 MetricSpec `required_claims`，否则决定无效；
- PoC 酒店只接受 HUMAN，第二 AI Reviewer 延期。

---

# 10. Verified Observation、Result 与 Publication

## 10.1 Verified Observation 生成

结构化路径：

```text
唯一结构化事实
+ 现有结构 guard 通过
→ Verified Observation
```

AI 路径：

```text
Candidate
+ Evidence Check PASS
+ 有效 HUMAN ReviewDecision
+ approved claims 满足 required claims
→ Verified Observation
```

## 10.2 Observation 身份与来源绑定

```yaml
source_binding:
  raw_asset_id: ...
  source_reference_id: ...
  accession: ...
  document_name: ...
  source_role: target_10k_primary
  derived_asset_id: ...
  locator: ...
```

```text
observation_id = hash(
  semantic_role
  + company_id
  + period
  + approved scope claims
  + canonical value/unit
  + source_binding
)
```

不得包含代码、模型、时间戳、日志或 reviewer 身份。

## 10.3 Result Grain

```text
company_id
metric_id
period_start
period_end
scope_key
spec_closure_hash
```

权威 scope 是 canonical JSON object；

```text
scope_key = sha256(canonical_scope_json)
```

避免字符串拼接和转义歧义。

`spec_closure_hash` 是指标自身及所有传递复用指标的 semantic hash 闭包。B03 必须包含 B01。

## 10.4 最小结果语义

```yaml
applicability: APPLICABLE | N_A_STRUCTURAL
quality: EXACT | APPROX | NOT_MEANINGFUL | NONE
publication: PUBLISHED | WITHHELD
reason_code: ...
value: decimal | null
unit: canonical unit | null
```

Publication 固定规则：

| 条件 | 结果 |
|---|---|
| Applicability 不满足 | `N_A_STRUCTURAL + NONE + PUBLISHED + value=null` |
| APPLICABLE，Verified Observation/Trace 通过，quality=EXACT/APPROX | PUBLISHED |
| APPLICABLE，annual duration/denominator 等规则明确判定无经济意义 | `NOT_MEANINGFUL + PUBLISHED + value=null` |
| Evidence/Review/guard/计算失败 | WITHHELD |
| 未定义组合 | WITHHELD + `INVALID_STATE_COMBINATION` |

Publication 不接受人工直接赋值。

---

# 11. Calculator 与 Execution Trace

首期 Calculator 只实现：

```text
add
subtract
multiply
divide
```

`choose_first` 属于 Spec 输入解析，不属于 Calculator。B01 direct value 无需 `identity` 运算。

Calculator 不得读取 HTML、调用 AI、找表、判断 scope、按公司名分支或执行未声明 fallback。

Execution Trace 必须记录：

```text
input observation IDs
选择的 direct/fallback 路径
被拒绝输入及机械原因
每一步 Decimal
cross-check 是否可用及结果
quality EXACT/APPROX/NOT_MEANINGFUL
最终结果
```

B03 必须从 Trace 完全重算。

---

# 12. Run 内容身份与审计身份

首期不建设 Dataset Version；使用不可变 Run Manifest。

## 12.1 content_manifest_hash

包含：

```text
spec semantic/closure hashes
source bindings actually used
Verified Observations
Metric Results
selected evidence
semantic Execution Trace
approval_effect_hashes
```

不包含：模型、实现代码 fingerprint、run_id、时间戳、reviewer、日志。

## 12.2 audit_manifest_hash

包含：

```text
run_id/timestamps
AI model/prompt/inference metadata
code fingerprints
全部 Candidate/competing/unresolved claims
Evidence Check 明细
完整 ReviewDecision
validation diagnostics
日志
```

代码重构或模型重跑但业务内容不变：

```text
content_manifest_hash 不变
audit_manifest_hash 可以变化
```

---

# 13. Legacy Projector：完整迁移桥

## 13.1 输入

Projector 必须同时读取：

```text
A. 本轮旧系统生成的完整 legacy metrics/evidence（完成所有旧 repair 后）
B. 本轮冻结的 vNext Result/Observation/Trace
C. migrated_metric_ids = [B01, B03, B10, B11]
D. 每个 MetricSpec 的 legacy_projection
E. legacy baseline manifest
```

Phase 1 严格 parity；Projector 不接受未定义的 “approved correction”。发现旧结果疑似错误时，先停止 cutover，另开方法论 PR。

## 13.2 合并规则

### metrics_matrix

1. 对非 migrated metric IDs，完整保留旧行；
2. 对 migrated IDs，删除旧行并使用 vNext 投影行；
3. 兼容键沿用当前 `(company, metric_id)`；
4. replacement 在旧行原位置写入；旧文件中不存在的新行按 `(company, metric_id)` 排序追加；
5. 输出必须包含完整矩阵，不能只输出四个指标。

### metric_evidence

1. 对非 migrated IDs，完整保留旧 evidence；
2. 删除 migrated IDs 的旧 evidence；
3. 将每个 vNext source binding/Observation 按稳定 `evidence_order` 投影为一行；
4. 不再用分号把多个 accession、document 或 value 拼成一个单元格；若旧 schema 只能表示一条 evidence，则为同一指标输出多行；
5. 输出按旧基线顺序优先，再按 `(company, metric_id, evidence_order)` 稳定排序。

## 13.3 字段投影契约

每个 migrated MetricSpec 必须明确 `legacy_projection`，覆盖：

```text
value
unit
status
source_class
formula
period_start
period_end
accession
concept_or_section
context_or_dimension
confidence
notes
extraction_method
evidence rows
```

最低映射：

| vNext 语义 | Legacy 投影 |
|---|---|
| quality=EXACT，B01/B03 | `status=OK`（source_class 由 Spec/selected source 定义） |
| quality=APPROX，B03 | `status=OK_APPROX` |
| B10/B11 AI 表格 exact | `status=MDA_OK`, `source_class=MDA` |
| quality=NOT_MEANINGFUL | `status=NOT_MEANINGFUL`, value 为空，notes 保留原因 |
| applicability=N_A_STRUCTURAL | `status=N_A_STRUCTURAL`, value 为空 |
| B10 canonical ratio | legacy value ×100，unit=`percent` |
| B03 formula | 从 Spec AST 渲染，不允许手写另一份公式 |

`confidence`、`notes` 和其他文本字段必须使用 MetricSpec 中的版本化模板，并在 Phase 1 与当前基线逐字段 parity。

## 13.4 执行顺序与原子性

```text
1. 旧 pipeline 完成所有非迁移及旧基线计算
2. vNext Run 完成并 FROZEN
3. Projector 生成完整 staging metrics/evidence + projection_manifest
4. 对 staging 运行现有 Golden 和 Validation
5. 任一失败：正式旧文件保持不变
6. 全部通过：metrics、evidence、manifest 作为一组原子替换
7. 报告仅读取已发布文件，不得再调用 repair
```

`projection_manifest.json` 至少包含：

```text
legacy input hashes
vNext run/content hash
migrated metric IDs
staging metrics/evidence hashes
Golden/Validation result hashes
published_at_utc
```

## 13.5 双生产者禁用

Projector 切换后：

```text
apply_p0_repairs
apply_lodging_kpi_metrics
旧 upsert 路径
```

不得写入 migrated IDs。CI 失败码：

```text
LEGACY_PATH_STILL_ACTIVE
```

---

# 14. 三个垂直切片

## Slice A：B01 Revenue

目标：证明结构化事实不需要 AI。

要求：

- 复用当前 Company Facts / filing XBRL 选择和现有 cross-check；
- 不在 PoC 新建通用 amendment-aware reconciliation 引擎；
- period/entity/unit/accession 来自结构化字段；
- 按现有 applicability 与 continuity 行为严格 parity；
- 无新增业务语义 Python 分支。

## Slice B：B10/B11/ADR

目标：证明 AI 能替代酒店专用语义 parser。

要求：

- 一次 AI call 返回三项；
- AI 找表、行、列、年份和 scope；
- Checker 只验证 locator/cell/局部标签与完整表格上下文；
- 人工 ReviewDecision 批准 period/scope；
- canonical Occupancy 存 ratio，Legacy 投影为 percent；
- 程序验证 RevPAR 恒等式；
- 不新增酒店专用 scope parser；
- 通过 Bridge 后旧酒店 resolver/repair 必须退出正式路径。

## Slice C：B03 EBITDA margin

目标：证明 Contract 能替代复杂业务 Python。

要求：

- Revenue 复用唯一 B01 Observation；
- OI direct/reconstruction、optional cross-check 全部在 Spec；
- D&A direct/composed 均为 EXACT；
- OI reconstruction 为 APPROX；
- 顶层 same accession/period/entity/unit/annual duration/denominator guard 生效；
- Calculator 只执行通用算术；
- Trace 可重放；
- 不存在未声明 fallback。

---

# 15. 验收场景

## AC-01｜AI value 与 locator 不一致

Given AI claimed `73.1%`，locator cell 实际为 `71.3%`；When Evidence Check；Then Candidate `REJECTED`，不得采用 `71.3%` 继续发布，必须重新提取。

## AC-02｜Locator 不存在

Given AI 返回不存在的 table/row/column；When Evidence Check；Then Candidate REJECTED，Result WITHHELD。

## AC-03｜局部标签真实但语义待审

Given “Comparable Systemwide Properties” 和 “Worldwide” 均真实位于目标表格路径；When Evidence Check；Then Candidate 只能 EVIDENCE_CHECKED；无 ReviewDecision 时不得发布。

## AC-04｜Claims 不匹配

Given MetricSpec 要求 current fiscal year，ReviewDecision 批准 prior year；When生成 Verified Observation；Then决定无效，Result WITHHELD。

## AC-05｜完整表格上下文

Given AI 选择一条 Worldwide Occupancy；When生成 review.md；Then必须展示 AI 指定表的完整表格或全部相关角色/年度行列，不得只展示 selected/competing 的 AI 筛选子集。

## AC-06｜程序不得重新解题

Given Evidence Checker 新增按酒店关键词搜索全文并自行选择表/行；When architecture lint；Then失败 `SEMANTIC_PARSER_REINTRODUCED`。

## AC-07｜新布局不改 Python

Given下一年度酒店表格换列；When AI 返回新 locator 且 Evidence/Review/identity 通过；Then生产 Python 修改文件数必须为 0。

## AC-08｜B03 防双计

Given combined D&A=100 且 amortization=20；When B03；Then D&A=100，不得为120，quality=EXACT。

## AC-09｜B03 跨 accession

Given Revenue 与 OI/D&A 来自不兼容 accession；When顶层 guard；Then B03 WITHHELD，不得计算。

## AC-10｜B03 Cross-check

Given OI reconstruction、Revenue 与 compatible CostsAndExpenses 可得，且 `Revenue-Costs` 与重建 OI 相对误差 >1%；Then该 reconstruction path 失败。

## AC-11｜NOT_MEANINGFUL

Given annual duration 为 successor stub 且不在300–400天；When B01/B03 按当前方法论处理；Then生成可见 `NOT_MEANINGFUL` 行，不得消失或伪装为来源缺失。

## AC-12｜Review 绑定

Given Candidate locator 或 source_reference_id 改变；When复用旧 ReviewDecision；Then旧决定失效。

## AC-13｜Applicability

Given非 lodging 公司；When执行 B10/B11；Then不调用 AI，并由 Projector 输出 `N_A_STRUCTURAL` 兼容行。

## AC-14｜Legacy 完整合并

Given旧系统有全部指标、vNext 只有四个 migrated IDs；When Projector；Then非迁移行全部保留，四个迁移行被替换，完整矩阵行数与基线规则一致。

## AC-15｜双文件原子发布

Given staging metrics 通过但 evidence 或 Validation 失败；When publish；Then两个正式文件都不改变。

## AC-16｜现有功能保持

Given vNext cutover；When运行现有 Golden、Validation 和报告；Then字段级 parity，旧酒店 repair 不再写入。

## AC-17｜历史 replay 无 AI

Given已冻结 Run；When无模型凭据重放；Then可从 assets、Candidate、Review、Observation 和 Trace 产生相同 Result。

---

# 16. 复杂度硬门

PoC 成功必须同时满足：

1. B10/B11 迁移后，至少一条旧酒店语义 resolver/repair 被真实删除，且其入口不可达；
2. 新酒店 filing 换行列时，生产 Python 修改文件数为 0；
3. 新增另一个表格指标不得新增专用 parser；
4. Evidence Checker 中不得出现 metric_id、company_id、行业名条件分支；
5. 新架构新增的业务专用分支数必须少于删除的旧业务专用分支数；
6. 所有 PUBLISHED 数值均可从 locator 机械重取；
7. 所有复杂 scope/period 主张均有有效 ReviewDecision；
8. 当前 CSV、Golden、Validation 和报告逐字段不退化；
9. AI 关闭后历史 replay 成功；
10. 报告网络调用和权威数据写入均为 0；
11. Phase 1 不允许用未定义 “approved correction” 绕过 parity；
12. B03 Contract 不得包含未定义角色，业务 fallback 不得出现在 Python 控制流中。

核心观测：

| 指标 | 当前 | v3.3.1 目标 |
|---|---:|---:|
| 新布局需修改生产 Python 文件数 | 多个 | 0 |
| 酒店指标专用语义正则 | 多个 | 0 |
| 酒店专用 resolver/repair | 多条 | 删除或永久不可达 |
| 每个新表格指标的新 parser | 通常需要 | 0 |
| Evidence Checker 理解的酒店业务语义 | 多 | 0 |

---

# 17. 实施顺序

## PR 0：基线、隔离与只读边界

- 冻结现有结果/evidence/Golden/Validation/request provenance；
- 新输出写 `artifacts/vnext/`；
- 新 renderer 只读；
- 禁止新增 report repair；
- 建立公司 trait 最小投影视图。

## PR 1：Evidence 基础

- RawBlob/SourceReference 适配视图；
- 最小 Source Manifest；
- table-grid DerivedAsset；
- locator round-trip。

## PR 2：Specs 与 AI Reader

- B01/B03/B10/B11 Specs；
- dual hashes；
- lodging disclosure group；
- 单 AI Reader；
- Candidate schema 和完整目标表 review context。

## PR 3：Evidence Checker 与 ReviewDecision

- locator/value/label 机械检查；
- percent→ratio 和数值政策；
- claims matching；
- content-based Candidate hash；
- ReviewDecision / approval effect；
- `SEMANTIC_PARSER_REINTRODUCED` lint。

## PR 4：Slice A 与 Slice B Shadow

- B01；
- B10/B11/ADR；
- strict parity；
- identity；
- 人工 review。

## PR 5：Slice C

- B03 完整 Contract；
- Calculator；
- Trace；
- cross-accession、cross-check、D&A quality tests。

## PR 6：Legacy Projector 与 Cutover

- 完整 merge 和字段映射；
- staging Golden/Validation；
- 双文件原子替换；
- 旧 migrated IDs 写路径禁用；
- 全量回归；
- 删除旧酒店 resolver/repair/semantic regex。

---

# 18. 后续能力触发条件

只有真实实现证明需要时才增加：

| 能力 | 触发条件 |
|---|---|
| 第二 AI Reviewer | 人工审核成为明确瓶颈；一致性只作为辅助，不能替代证据和方法论 |
| 通用 Scope Binding | 同一标签跨多公司/年度反复获批，且人工审核成为主要成本 |
| CompanyRule | A02/B06 等稳定公司 scope 差异出现 |
| Source Recipe | 同一布局反复出现且模型读取成为瓶颈 |
| 完整 absence/coverage | E02/B12 迁移 |
| qualitative_signal | C/D 类文本指标迁移 |
| Databricks current/as-of | 三切片 Cutover 稳定 |
| 双解析器/taxonomy service | 规模扩大或出现真实解析事故 |
| 自动发布 | 另立需求；不得从本 PoC 文档中隐式推导 |

---

# 19. Definition of Done

v3.3.1 首期完成必须满足：

- B01、B10、B11、B03 在 vNext 正确产出；
- ADR 作为支撑 Observation 完整留痕；
- AI value 未直接进入任何正式结果；
- AI value 与 locator 不一致时 Candidate 被拒绝；
- 酒店语义由 AI 主张和 HUMAN ReviewDecision 批准，不由程序重建；
- 审核者可以看到完整目标表格上下文，而非 AI 筛选视图；
- B03 全部 direct/fallback、cross-check 和 guard 在 Spec 中可见；
- D&A composed 保持 EXACT，只有 OI reconstruction 传播 APPROX；
- B03 跨 accession/period/entity/unit 被拒绝；
- 非 lodging 公司产生 N_A_STRUCTURAL 兼容行；
- stub period 等现有 NOT_MEANINGFUL 行保持可见；
- Legacy Projector 生成完整矩阵和 evidence，并保持所有现有字段 parity；
- 当前 Golden、Validation 和报告通过；
- migrated IDs 的旧写路径失效，旧酒店语义路径删除或永久不可达；
- 下一年度酒店表格换列不修改生产 Python；
- 历史 replay 无需 AI；
- 报告严格只读。

最终判定：

> **只有当 AI 吸收了文件定义、布局和公司措辞的变化，Evidence Checker 没有重新长成行业 Resolver，且旧专用路径真实退出，AI-first 才算成功。**
