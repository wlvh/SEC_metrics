# SEC_metrics 项目全景与专家指南（vNext）

> **适用条件**：本指南在《SEC Metrics vNext：可审计财务指标契约与抗格式演化系统》FSD v1.1 的 Definition of Done 全部满足、Gate G0–G5 通过并完成主系统切换后启用。AI 章节只有在 Gate G6 通过后才描述已启用能力；否则按 `DISABLED` 或 `SHADOW` 阅读。
>
> **文档角色**：本指南解释系统为什么这样设计、专家如何阅读和操作系统、出现异常时怎样判断；它不复制或替代 FSD、Catalog Release、Dataset Version 和自动生成审核产物中的规范性定义。

| 文档属性 | 值 |
|---|---|
| 指南版本 | 2.0 |
| 基线 FSD | `SEC_metrics_vNext_FSD_v1.1.md` |
| 目标读者 | 项目负责人、财务方法论审核者、数据审核者、工程师、QA、发布负责人、审计者、AI 工程代理 |
| 当前状态数据来源 | Catalog/Dataset/Validation/Parser/Taxonomy manifest 自动生成 |
| 手工维护边界 | 领域叙事、设计理由、审计方法、操作心智模型、事故复盘 |

---

## 目录

0. [如何使用本指南：权威层级与可信度标记](#0-如何使用本指南权威层级与可信度标记)
1. [系统是什么：使命、边界与可信结果的定义](#1-系统是什么使命边界与可信结果的定义)
2. [vNext 心智模型：从 RawAsset 到 Dataset Version](#2-vnext-心智模型从-rawasset-到-dataset-version)
3. [SEC 数据平面、XBRL 与 taxonomy 基础](#3-sec-数据平面xbrl-与-taxonomy-基础)
4. [Source Shell：RawAsset、Adapter、格式漂移与隔离](#4-source-shellrawassetadapter格式漂移与隔离)
5. [SEC 官方测试套件与 Arelle：如何成为可替换的外部质量资产](#5-sec-官方测试套件与-arelle如何成为可替换的外部质量资产)
6. [Catalog Release：指标定义、结构化公式、traits 与审批](#6-catalog-release指标定义结构化公式traits-与审批)
7. [Candidate Resolution：候选生成、排序、拒绝账本](#7-candidate-resolution候选生成排序拒绝账本)
8. [ComputationIR、单位代数、Lineage 与 Evidence](#8-computationir单位代数lineage-与-evidence)
9. [四维状态、Coverage Receipt 与 Publication Policy](#9-四维状态coverage-receipt-与-publication-policy)
10. [Dataset Version、原子发布、公开视图与只读报告](#10-dataset-version原子发布公开视图与只读报告)
11. [Strategy 目录与领域案例](#11-strategy-目录与领域案例)
12. [验证拓扑：Golden、Mutation、Backtest、SEC Suite 与 G0–G6](#12-验证拓扑goldenmutationbacktestsec-suite-与-g0g6)
13. [专家审计手册](#13-专家审计手册)
14. [扩展手册：新公司、新行业、新指标、新格式、新 parser](#14-扩展手册新公司新行业新指标新格式新-parser)
15. [运行监控、质量北极星与事故响应](#15-运行监控质量北极星与事故响应)
16. [AI Proposal：允许做什么、如何审核、何时关闭](#16-ai-proposal允许做什么如何审核何时关闭)
17. [常见错误模式与反模式](#17-常见错误模式与反模式)
18. [当前实现地图、交付物与命令索引](#18-当前实现地图交付物与命令索引)
19. [Legacy Round 3、规则考古与制度记忆](#19-legacy-round-3规则考古与制度记忆)
20. [专家训练清单与术语表](#20-专家训练清单与术语表)
21. [外部规范与参考资料](#21-外部规范与参考资料)

---

## 0. 如何使用本指南：权威层级与可信度标记

### 0.1 文档权威层级

发生冲突时，按以下顺序裁决：

1. **FSD**：外部可观察行为、状态机、错误行为、数据语义和发布门禁的规范性来源。
2. **APPROVED Catalog Release**：某一时点全部指标方法论、适用性、resolver、strategy、FormulaIR shape、publication options 与审批的权威来源。
3. **PUBLISHED Dataset Version**：已发布公司 × 指标 × 期间 × scope × 定义版本 × result role 的权威事实快照。
4. **自动生成审核产物**：Applicability Matrix、Metric Card、Semantic Diff、Backtest、Candidate Review、Parser Agreement、Taxonomy Impact、Gate Summary。
5. **本专家指南**：解释设计理由、操作方法、审计路径和事故经验；不得反向修改以上权威对象。
6. **Legacy 文档与 CSV**：用于迁移、兼容和历史研究，不定义当前系统行为。

因此，本指南不会手工复述每个指标的完整候选链、公式版本和适用矩阵。专家需要查看某一指标的当前定义时，必须打开该 Catalog Release 自动生成的 Metric Card，而不是从本文复制一段旧说明。

### 0.2 四级可信度标记

```text
[生成]  直接从 Catalog/Dataset/Validation/Parser/Taxonomy 权威对象渲染，带来源 hash；禁止手改。
[实测]  通过独立执行、重放、对抗测试或人工复核得到，并记录 run/audit ID。
[考证]  已阅读源代码、规范或原始材料并确认，但不是本次运行的自动产物。
[声明]  历史文档、报告或人员陈述；尚未在当前版本独立复核。
```

`[生成]` 表示**抗文档漂移能力最高**，不代表数据天然不会错；数据正确性仍由 validation、审计和 Published-Wrong Rate 共同约束。`[实测]` 可以独立发现生成系统自身的错误，因此两者不是简单的真值等级排序。

### 0.3 当前版本绑定区块

真实仓库中的以下区块必须由 CI 生成。本文稿保留占位符，不声称当前 legacy 仓库已经拥有这些 vNext 版本 ID。

<!-- GENERATED:CURRENT_RELEASE:START -->

| [生成] 当前绑定 | 值 |
|---|---|
| `implementation_commit` | `{{IMPLEMENTATION_COMMIT}}` |
| `fsd_version` | `1.1` |
| `catalog_release_id` | `{{CATALOG_RELEASE_ID}}` |
| `catalog_semantic_hash` | `{{CATALOG_SEMANTIC_HASH}}` |
| `dataset_version_id` | `{{DATASET_VERSION_ID}}` |
| `publication_policy_version` | `{{PUBLICATION_POLICY_VERSION}}` |
| `taxonomy_registry_hash` | `{{TAXONOMY_REGISTRY_HASH}}` |
| `adapter_manifest_hash` | `{{ADAPTER_MANIFEST_HASH}}` |
| `parser_manifest_hash` | `{{PARSER_MANIFEST_HASH}}` |
| `sec_efm_version` | `{{SEC_EFM_VERSION}}` |
| `sec_public_test_suite_version` | `{{SEC_TEST_SUITE_VERSION}}` |
| `gate_summary` | `{{G0_G6_SUMMARY}}` |
| `generated_at_utc` | `{{GENERATED_AT_UTC}}` |

<!-- GENERATED:CURRENT_RELEASE:END -->

### 0.4 指南自身的漂移防线

- 所有统计数字、状态分布、文件清单、parser 版本、taxonomy 版本、命令入口和门禁结果必须位于 `[生成]` 区块。
- 生成区块必须绑定来源对象 hash；手工修改后 CI 必须失败。
- 手工章节不得把示例值写成无版本的“当前值”。任何实例都必须标注 `dataset_version_id`，或明确写为“Legacy Round 3 历史案例”。
- 指南中的规范性语句如果与 FSD 不一致，必须修改指南，不得以指南解释覆盖 FSD。

---

## 1. 系统是什么：使命、边界与可信结果的定义

### 1.1 一句话

SEC_metrics 是一个**版本化、可审计、可回放、能够抵抗 SEC 来源格式与 taxonomy 演化的财务指标契约和发布系统**：它从 SEC 官方来源取得不可变原始资产，经可替换 adapter 生成标准化观察事实，再由已批准的指标契约确定性地产生、验证并发布财务、治理、风险和事件结果。

### 1.2 系统追求什么

系统追求的不是“所有格子都有数字”，而是：

```text
正确的事实能够发布；
不能证明正确的事实被明确暂缓；
不适用、无经济意义、未披露、没找到、解析失败和格式不支持彼此可区分；
任何 Published 结果都可以从固定版本原始材料独立重放。
```

最危险的失败不是空值，而是：

> **一个错误值携带正常状态、正常证据外观和正常报告位置，被下游当成事实消费。**

因此系统遵循失败等级：

```text
正确发布 > 明确弃权/暂缓 > 显式失败 > 静默错值
```

### 1.3 系统不做什么

- 不用第三方财务数据库补齐 SEC 未披露值。
- 不让 AI 直接决定或发布指标事实。
- 不把任意公式字符串、SQL 或 Python `eval` 当指标语言。
- 不把某个 parser、某个 taxonomy 年份、某种 HTML 布局或某家公司名称写成指标内核不可替换的假设。
- 不允许 reviewer 直接覆盖 `publication_status` 或原地改写已发布 Dataset Version。
- 不把 `metrics_matrix.csv`、报告 Markdown 或 Metric Card 当运行输入。

### 1.4 可信结果公式

```text
一个 Published 结果可信 =
  原始资产可重放
  + 来源格式被支持或已审计
  + filing/taxonomy 解释正确
  + 指标契约已批准
  + 候选裁决可解释
  + FormulaIR 可重算
  + long-form lineage 完整
  + Coverage Receipt 足以支撑观察结论
  + Validation/Mutation/Backtest 通过
  + Publication Policy 允许
  + Dataset Version 原子且不可变
```

少任何一项，它最多是“一个看起来像结果的候选”。

---

## 2. vNext 心智模型：从 RawAsset 到 Dataset Version

### 2.1 核心对象链

```text
SEC Source
  ↓ fetch
SourceObservation ──→ RawAsset（不可变字节 + SHA-256）
                         ↓ adapter/parser
                 CanonicalObservation
                         ↓ resolver
                    MetricCandidate
                  ↙ selected   ↘ rejected/suppressed
             ComputationGraph   Rejection Ledger
                         ↓
                    MetricResult
                         ↓ validation + coverage + policy
          PUBLISHED / WITHHELD / NEEDS_REVIEW
                         ↓ atomic publish
                   DatasetVersion
                         ↓
              Public View / Review View / Report
```

### 2.2 三个逻辑边界

#### Source Shell：易变外壳

负责 SEC API、accession package、XBRL/iXBRL、HTML 表格、文本、taxonomy package 和 parser。它知道文件格式，但不知道 B03、B06 或 A02 的经济定义。

#### Metric Kernel：稳定内核

负责 Catalog Release、适用性、候选裁决、ComputationIR、单位代数、validation 和 publication policy。它只读取 Canonical Observations，不读取 SEC 文件。

#### Proposal Plane：不可信提案层

AI 可以在这里寻找 concept、定位表格、草拟契约和测试，但不能写入 APPROVED Catalog、Metric Result、Golden expected 或 Published Dataset。

### 2.3 为什么这条边界能抵抗 SEC 格式变化

当 SEC 文件外观发生变化时，系统应当修改或新增 adapter，而不是修改指标公式。例如：

```text
旧 iXBRL transform 失效
→ Adapter 报 NEW_TRANSFORMATION / FORMAT_UNSUPPORTED
→ 只有依赖该 capability 的结果被 WITHHELD
→ 修 Adapter
→ 从原 RawAsset 离线重放
→ 与旧/影子 parser、Golden 和历史结果比较
→ 发布新 Dataset Version
```

B03 的公式和 B06 的经济定义在此过程中不应发生变化。

---

## 3. SEC 数据平面、XBRL 与 taxonomy 基础

### 3.1 SEC 来源平面

#### Submissions：申报索引

回答“公司提交过什么”：form、accession、filing date、report date、primary document、CIK、名称、SIC、fiscal year end 等。它用于 filing discovery 和实体登记，不直接证明某个财务值。

#### Company Facts：公司级标准事实聚合

适合标准、公司整体层面的 XBRL 事实。它便于跨期间选择，但不能完整表达所有自定义概念、维度事实和表格/文本披露。

#### Accession Materials：原始申报包

包含 filing 目录、主文档、XBRL/iXBRL、FilingSummary、header、附件等，是维度、自定义事实、8-K item、DEF 14A 和表格/文本证据的主要来源。

#### Taxonomy Packages：解释层依赖

不是公司的 filing 内容，却决定 concept、type、periodType、balance、labels、references 和 relationships 如何被解释。历史 filing 必须使用其实际引用的 taxonomy package，不得用“当前最新 taxonomy”追溯改写。

### 3.2 “Company Facts 优先”不再是全局规则

vNext 不采用全系统统一的“Company Facts 优先、accession 补足”。每个 APPROVED Metric Contract 声明自己的 source priority 和 required capabilities：

- B01 可以以标准公司级事实为优先。
- A01/A02 必须依赖带 Basel methodology dimensions 的 accession facts。
- B10/B11 可能依赖 HTML table structure。
- C03 优先消费 ECD XBRL。
- E02 依赖完整 8-K 搜索窗口和 coverage receipt。

来源优先级属于指标语义的一部分，必须经过 Catalog 审批。

### 3.3 XBRL 核心词汇

- **concept**：事实的语义标签，分标准 taxonomy 概念和公司扩展概念。
- **context**：实体、期间和维度组合。
- **dimension**：axis + member，为事实增加口径限定。
- **unit**：USD、shares、pure 等。
- **scale/sign**：iXBRL 对展示值的缩放和符号解释。
- **schemaRef**：filing 指向的 taxonomy 入口。
- **taxonomy release/package hash**：解释 filing 时实际使用的版本和不可变包指纹。
- **locator**：回到原始事实、表格单元或文本 span 的结构化位置。

### 3.4 HTTP 与来源纪律

- 生产来源初始仅允许 SEC 与已登记 taxonomy package 来源。
- 请求必须遵守 SEC User-Agent 和速率政策。
- 网络调用只允许在 discovery/ingest 或显式 taxonomy acquisition 流程。
- Resolver、validator、publication、report 和离线 replay 不得临时联网补数据。
- 每次请求必须产生 SourceObservation；成功内容按 bytes hash 进入 RawAsset vault。
- 相同内容重复取得不得产生第二个逻辑 RawAsset。

---

## 4. Source Shell：RawAsset、Adapter、格式漂移与隔离

### 4.1 RawAsset 与 SourceObservation 的区别

`SourceObservation` 表达“某次 run 请求了什么、何时请求、HTTP 结果和重试是什么”。`RawAsset` 表达“成功获得的不可变字节是什么”。

这种分离解决三个问题：

1. 同一内容可以被多次观察，但只存一个资产。
2. 网络故障不被误认为 filing 不存在。
3. parser 升级可以对历史资产离线重放，不依赖 SEC 当时仍返回完全相同的网络响应。

### 4.2 Source Adapter 的职责

Adapter 必须完成：

```text
detect capability
parse supported source
preserve raw semantics
emit CanonicalObservations
emit parser diagnostics
emit CoverageReceipt inputs
emit source dialect fingerprint
```

Adapter 不得：

- 决定某观察是不是 B03 或 A02 主值；
- 为了凑数改变期间、单位或 scope；
- 在未知 transform 时改用附近文本猜值；
- 直接产生 `PUBLISHED` 状态。

### 4.3 Canonical Observation

每个观察独立一行/对象。Numeric XBRL 观察至少保留：

```text
raw_asset_id
accession / form / filed date
entity identifier
schemaRef / taxonomy release / package hash
namespace URI + local concept name
period start/end
canonical unit
dimensions（稳定排序）
raw lexical value
scale / sign / decimals / precision
normalized decimal
source locator
adapter/parser version
validation messages
```

HTML 表格观察应保留 table/header/row/column locator；文本观察应保留 section、character/byte range 和 quote hash。`evidence_quote` 是人类视图，不是唯一证据锚点。

### 4.4 Source Dialect Fingerprint

每个 filing/source package 都要记录：

```text
media/document types
package structure
schemaRef URLs
taxonomy namespaces
Inline XBRL namespace/version
ix element set
transform registry
unit registry
dimension axes
extension domains
HTML/table structure
parser warning/error signature
```

它用于区分：

```text
KNOWN_DIALECT
NEW_TAXONOMY_RELEASE
NEW_NAMESPACE
NEW_IX_FEATURE
NEW_TRANSFORMATION
NEW_DOCUMENT_PACKAGING
HTML_STRUCTURE_DRIFT
UNKNOWN_SOURCE_DIALECT
```

### 4.5 局部隔离，而不是整家公司全停或全放

格式风险按 capability/metric dependency 隔离：

| 情形 | 正确行为 |
|---|---|
| Company Facts 正常，酒店表格布局未知 | B01 可发布；B10/B11 `FORMAT_UNSUPPORTED + WITHHELD` |
| iXBRL dimensional parser 分歧 | 依赖该维度事实的 A01/A02 暂缓；不依赖它的 8-K 事件可以继续 |
| 8-K inventory 完整、未发现 Item 1.03 | E02 作为明确零值发布 |
| taxonomy package 无法取得 | 依赖该 taxonomy 的 XBRL 结果暂缓；不得改用“最接近版本” |

### 4.6 Format Quarantine

新 dialect、未知 transform 或 material parser disagreement 必须进入隔离：

```text
DETECTED
→ QUARANTINED
→ ROOT_CAUSE_IDENTIFIED
→ ADAPTER/PARSER_FIXED
→ OFFLINE_REPLAYED
→ VALIDATED
→ NEW_DATASET_PUBLISHED
→ CLOSED
```

旧 Published Dataset 仍可查询，但不得伪装成新 filing 的当前结果。

---

## 5. SEC 官方测试套件与 Arelle：如何成为可替换的外部质量资产

### 5.1 两项已经进入 FSD 的位置

FSD v1.1 已明确要求（主要见 `FMT-004/005/006/009`、`VAL-007`、`AC-VAL-06`、`WP-C2`、Gate G4 与外部规范基线）：

- parser/taxonomy 升级必须运行 SEC Interactive Data Public Test Suite 的受支持部分，并记录 EFM/test-suite 版本、通过/失败数量和跳过理由；
- 关键 XBRL/iXBRL 路径必须支持独立 primary/shadow parser；Arelle 或其他 standards-compliant processor 可以作为实现候选，但具体产品不是权威来源；
- 新 parser major、新 taxonomy、新 dialect 必须对受影响 corpus 100% shadow；material disagreement 不得发布。

因此不需要再给 FSD 增补规范条款。指南的任务是说明这些要求如何运营。

### 5.2 SEC Interactive Data Public Test Suite 的定位

[考证] SEC 的公开测试套件由许多小型 Interactive Data instances、schemas 和 linkbases 组成，并标明案例是否违反某项 validation、属于 warning 还是会造成 EDGAR rejection。它主要帮助开发者验证 Interactive Data 软件对 EDGAR 规则的处理。

对 SEC_metrics 而言，它是**外部标准符合性语料库**，不是业务指标真值库。

它能证明的主要是：

- parser 对 XBRL/iXBRL、schema/linkbase、部分 EFM validation 边界的行为是否符合预期；
- 某个 parser/plugin 升级有没有破坏标准案例；
- 新 EFM/test suite 到来时，支持面和失败面发生了什么变化。

它不能单独证明：

- B03 的 EBITDA proxy 方法论正确；
- A02 选中的是 actual ratio 而不是 regulatory threshold；
- B10 选择了正确的酒店 scope；
- E02 的搜索窗口完整；
- 公司扩展 concept 与指标语义等价。

这些仍由 Catalog、项目 fixtures、Golden、mutation、backtest 和人工方法论审核负责。

### 5.3 测试套件如何进入 CI

#### Suite Registry

每个被使用的 SEC suite 版本必须登记：

```text
efm_version
test_suite_release_date
summary_asset_sha256
testcase_archive_sha256
downloaded_at_utc
supported_case_manifest_hash
runner_version
expected_outcome_mapping_version
```

不得在 CI 中永远下载“latest”并覆盖旧版本。新版本先登记为 candidate，旧 release 仍可重放。

#### 三层执行策略

| 层 | 触发 | 执行范围 | 作用 |
|---|---|---|---|
| PR 快速层 | 修改 adapter/parser canonicalization | 与项目实际 capability 相关的 curated subset | 快速发现基本标准回归 |
| Parser Release 层 | parser/plugin major/minor、taxonomy/EFM 变化 | 全部“受支持”官方案例 + 项目 fixtures | 决定 parser candidate 能否晋级 |
| Upstream Watch 层 | SEC 发布新 suite/EFM | 新旧 suite 并行、差异报告 | 识别新规则，不自动升级生产 |

“受支持”不等于可以随意跳过。每个 skipped case 必须有：

```text
reason_code
unsupported_capability
owner
首次记录版本
复查条件或到期时间
```

跳过数量突然增加必须视为 regression。

#### 结果产物

CI 必须输出版本化 Conformance Report：

```text
suite/EFM version
parser + plugin manifest
supported/pass/fail/skipped counts
每个失败案例的官方 expected outcome 与实际 outcome
新增失败、已修复失败、范围变化
release gate verdict
```

### 5.4 Arelle 的正确角色

[考证] Arelle 是开源 XBRL processor，支持 XBRL 2.1、Dimensions、Taxonomy Packages、Inline XBRL 1.1，并提供 SEC EFM validation 能力。Arelle 项目同时说明 SEC 维护其 EDGAR validation plugins。

项目可以让 Arelle 担任：

- `primary parser`：主要生成 Canonical Observations；或
- `shadow parser`：与现有/另一独立实现比较；或
- `conformance runner`：执行官方套件和 EFM diagnostics。

但 Arelle **不是系统权威来源**。权威来源仍是 RawAsset、固定 taxonomy package、APPROVED Catalog 和 Dataset Version。Arelle 是软件依赖而不是财务数据源；引入它不改变项目的 SEC-only 数据边界。

### 5.5 Arelle Adapter 的隔离边界

```text
RawAsset + locked taxonomy packages
        ↓
ArelleAdapter（固定版本、固定插件、固定参数）
        ↓
Canonical Observations + diagnostics
```

不得让以下对象泄漏进 Metric Kernel：

- Arelle 内部 model object；
- Arelle context/object ID；
- namespace prefix 作为事实身份；
- Arelle 专属错误字符串作为 publication policy；
- 隐式在线下载的未锁定 taxonomy。

Metric Kernel 只能看到来源无关的 Canonical Observation。

### 5.6 Parser Manifest 与供应链要求

每次 Arelle 运行至少记录：

```text
Arelle release/commit 或 container digest
Python/runtime/OS/architecture
启用插件列表与 hash
SEC EDGAR/EFM plugin 版本与 hash
command/config hash
taxonomy package cache manifest
network policy
SBOM/dependency lock
parser diagnostics signature
```

历史 replay 应优先使用本地、hash 锁定 taxonomy packages，并关闭不受控网络获取。否则“相同 parser 版本”仍可能因为远端 taxonomy 内容变化而得到不同结果。

### 5.7 Primary/Shadow 比较不是全量噪声比赛

强制比较域为：

```text
该 filing 上 APPROVED resolver 的 observation 消费闭包
+ Golden fixtures 明确引用的 observations
+ versioned parser-canary 集合
```

域内比较 canonical fact key、normalized value、scale/sign、period、unit、entity、dimensions 和 required fact 存在性。域外 footnote、内部 ID、排序和未消费 hidden facts 的差异只记 `PARSER_NON_MATERIAL_DIFF`。

以下为 material：

- 同一 canonical fact key 值不同；
- scale/sign 解释不同；
- period/unit/entity/dimensions 不同；
- 一方缺失 contract-required fact；
- 一方 fatal、另一方产生了被消费候选；
- 表格 header/row mapping 产生不同主值。

Material disagreement 的结果必须 `WITHHELD` 或 `NEEDS_REVIEW`，不得“挑看起来合理的一边”。

### 5.8 Arelle 升级工作流

```text
1. 登记 candidate parser manifest。
2. 固定官方 SEC suite/EFM 版本和 taxonomy registry。
3. 运行官方受支持 suite。
4. 运行项目 Golden、fixtures、mutations。
5. 对历史 RawAssets 离线重放。
6. 在强制比较域与当前 parser 100% shadow。
7. 生成 Parser Agreement 与影响报告。
8. 所有 material diff 归因并审批。
9. Gate G4 通过后提升 primary/shadow role。
10. 发布新 Dataset Version；不得改写旧版本。
```

### 5.9 三种质量资产必须同时存在

| 质量资产 | 主要发现什么 | 不能替代什么 |
|---|---|---|
| SEC 官方测试套件 | 标准与 EFM conformance 回归 | 指标经济语义和真实公司披露变体 |
| 独立 primary/shadow parser | 实现级解释分歧和 silent parser bug | 两个 parser 共同犯错、方法论错误 |
| 项目 Golden/fixtures/mutation/backtest | B03/B06/Basel/RevPAR/RPO/E02 等业务语义 | 全部 XBRL 标准边界 |

最强的系统不是“相信最权威的一个 parser”，而是让这三类证据彼此正交，缺陷难以同时穿透。

---

## 6. Catalog Release：指标定义、结构化公式、traits 与审批

### 6.1 Catalog Release 是原子权威对象

Catalog Release 同时锁定：

```text
metric definitions and versions
metric kinds and result grain
applicability/typed traits
entity exceptions
resolver/strategy versions
source priorities and hard constraints
ComputationIR shape
quality/publication options
required capabilities and coverage scopes
taxonomy compatibility decisions
finance/data approvals
code/build/schema versions
canonical semantic hash
```

一份 YAML 或 Markdown 不是完整权威对象。人类编辑格式必须经 compiler 规范化并产生 lock。

### 6.2 Metric Contract 的阅读顺序

专家审核一个指标时先回答：

1. 它代表什么经济事实，明确不代表什么？
2. `metric_kind` 是 numeric、dimensional、event 还是 qualitative？
3. 结果粒度是什么：实体、期间、scope、role？
4. 对哪些 traits REQUIRED/OPTIONAL/N_A/PROHIBITED？
5. 输入 components 如何解析，source priority 是什么？
6. 哪些 hard constraints 必须满足？
7. normal/fallback/rejection path 是什么？
8. 什么情况下是 EXACT、APPROX、UNVERIFIED 或 NOT_MEANINGFUL？
9. Publication Policy 是否允许该质量发布？
10. 要求哪些 evidence、coverage、正例、反例和正确弃权例？

### 6.3 FormulaIR：人读公式与机器计算同源

自由文本公式只能作为生成展示，不能作为计算真相。示例：

```yaml
nodes:
  revenue:
    op: OBS_REF
    observation_id: obs_revenue
  operating_income:
    op: OBS_REF
    observation_id: obs_operating_income
  depreciation:
    op: OBS_REF
    observation_id: obs_depreciation
  amortization:
    op: OBS_REF
    observation_id: obs_amortization
  da:
    op: ADD
    args: [depreciation, amortization]
  numerator:
    op: ADD
    args: [operating_income, da]
  result:
    op: DIVIDE
    args: [numerator, revenue]
root: result
```

非 `OBS_REF` 节点只能引用 graph node ID。系统从同一图：

- 计算 Decimal 值；
- 渲染公式；
- 生成 lineage；
- 执行单位代数；
- 做 Golden graph recomputation。

### 6.4 Typed Traits

公司能力和适用性用正交 traits 表达：

```text
archetype: non_financial / financial_institution
industry: lodging / airline / manufacturing / pharma / software / ...
business traits: captive_finance / subscription_revenue / franchise_heavy / ...
entity traits: continuous / successor_predecessor / stub_period / major_reorg
```

SIC 可以提供默认建议，但最终 assignment 必须有有效期、来源和理由。Trait 冲突必须在 Catalog compile 时失败，不能靠运行时隐式优先级。

### 6.5 Entity Exception

公司真实特殊性可以存在，但必须显式：

```text
company_id / metric_id / scope
reason and SEC evidence
approved_by / reviewed_hash
valid_from / valid_to
review or expiry condition
```

禁的是藏在生产控制流里的 `if company == ...`，不是现实中确有的 successor/predecessor、captive finance 或特殊报告主体。

### 6.6 SemVer 与审批

- **Major**：经济定义、公式、结果粒度、适用范围或可比性改变。
- **Minor**：增加不改变既有 Published 结果的 exact-equivalent 来源、安全 fallback 或新支持范围。
- **Patch**：纯文案、元数据或展示修复；backtest 必须证明零语义变化。

方法论变化必须 Finance Review；来源/resolver/adapter 变化必须 Data Review；两者都有则双审。审批绑定 semantic hash，hash 变化后旧审批失效。

---

## 7. Candidate Resolution：候选生成、排序、拒绝账本

### 7.1 为什么必须保留被拒绝候选

最后命中了什么，只能解释“系统选了谁”；被拒绝候选解释“为什么不是另一个看似合理的事实”。对 Basel threshold、RevPAR percentage change、混合期间 D&A、captive finance consolidated debt，这往往是审计的核心。

### 7.2 Candidate 状态

```text
SELECTED
REJECTED
SUPPRESSED
```

`SUPPRESSED` 是因 applicability、scope 或 policy 明确不参与竞争，不等于 publication 的 `WITHHELD`。

### 7.3 常见拒绝原因

```text
WRONG_PERIOD
WRONG_UNIT
WRONG_ACCESSION
ENTITY_SCOPE_MISMATCH
DIMENSION_SCOPE_MISMATCH
FORBIDDEN_CONCEPT
THRESHOLD_NOT_ACTUAL_RATIO
SEMANTIC_NEIGHBOR_UNAPPROVED
FAILED_INVARIANT
FAILED_CROSS_CHECK
LOWER_PRIORITY
DUPLICATE_EQUIVALENT
AMBIGUOUS_SAME_RANK
UNSUPPORTED_SOURCE_CAPABILITY
```

### 7.4 确定性要求

- 候选顺序变化不得改变 selected candidate。
- 插入重复事实不得改变结果。
- 加入低优先级候选不得改变已选结果。
- 同 rank 且无法确定性区分时必须 `AMBIGUOUS`，不得按文件顺序选第一个。
- Candidate selection 不能读取公司名、ticker 或 CIK 比较业务分支。
- 每次裁决必须记录 resolver version、rank components、selected/rejected reasons 和 candidate snapshot hash。

### 7.5 Source Priority 与语义近邻

概念名称相似不等于经济事实相同。Taxonomy compatibility 只有 `EXACT_EQUIVALENT` 或明确批准的 replacement 才能自动进入候选链；`NARROWER/BROADER/RELATED_BUT_DIFFERENT/UNKNOWN` 默认进入方法论审核。

---

## 8. ComputationIR、单位代数、Lineage 与 Evidence

### 8.1 ComputationIR 的职责

Resolver 选择正确输入；ComputationIR 负责可重算的算术。允许的封闭操作包括：

```text
OBS_REF / IDENTITY / ADD / SUBTRACT / MULTIPLY / DIVIDE
AVERAGE / PERCENT_CHANGE / COUNT / NEGATE / ABS
```

不得嵌入任意 Python、SQL 或表达式解释器。

### 8.2 单位代数

- ADD/SUBTRACT/AVERAGE：输入单位必须兼容，输出保持该单位。
- DIVIDE：相同金额单位相除得到 ratio；其他组合必须由契约声明。
- PERCENT_CHANGE：分子分母同单位，输出 ratio。
- COUNT：输出 count。
- OBS_REF/IDENTITY/NEGATE/ABS：保持输入单位。
- 单位冲突必须阻止计算，不得只写 warning。

### 8.3 Long-form Lineage

每条关系一行/edge：

```text
result → computation graph
computation node → observation
candidate → observation
observation → raw asset
coverage receipt → source operation/asset
validation → result/catalog/dataset target
```

Canonical 层不得用分号拼接 accession、context、path 或 value。Legacy projection 可以为了兼容使用旧表示，但不得反向作为运行输入。

### 8.4 Evidence Locator 类型

#### XBRL Fact

```text
raw_asset_id + accession + concept QName + canonical context key + unit + tuple path（如适用）
```

#### HTML Table Cell

```text
raw_asset_id + table locator + header path + row path + column path + raw cell text hash
```

#### Text Span

```text
raw_asset_id + section + start/end offset + quote hash
```

#### Filing Item/Search Window

```text
CIK/role + form set + date/period window + accession list + item code/section coverage
```

### 8.5 Published 可重放性

每个 Published numeric result 必须可以：

```text
读取固定 Dataset Version
→ 找到 Catalog Release 和 graph
→ 取得全部 OBS_REF observations
→ 回到 RawAssets/locators
→ 用固定 Decimal policy 重算
→ 与 Published value 精确或按 contract tolerance 一致
```

不能完成这一流程的结果属于 `Published-Unverifiable`，目标必须为 0。

---

## 9. 四维状态、Coverage Receipt 与 Publication Policy

### 9.1 Applicability

```text
REQUIRED
OPTIONAL
N_A_STRUCTURAL
PROHIBITED
```

### 9.2 Observation

```text
OBSERVED
PARTIAL
NOT_FOUND
NOT_DISCLOSED_CONFIRMED
SOURCE_UNAVAILABLE
PARSE_FAILED
FORMAT_UNSUPPORTED
AMBIGUOUS
NOT_RUN
```

### 9.3 Result Quality

```text
EXACT
APPROX
QUALITATIVE
NOT_MEANINGFUL
UNVERIFIED
NO_RESULT
```

### 9.4 Publication

```text
PUBLISHED
WITHHELD
NEEDS_REVIEW
```

Publication 是计算字段，不是 reviewer 按钮：

```text
publication_status = policy(
  metric_kind,
  applicability_status,
  observation_status,
  result_quality,
  coverage_completeness,
  validation_results,
  approval_state,
  contract_publication_options,
  publication_policy_version
)
```

决策表外的任何组合必须 fail closed：`WITHHELD + STS_UNMAPPED_STATE_COMBINATION`。

### 9.5 Coverage Receipt：怎样证明“没有”

“没找到”只是搜索结果；“确认未披露”是一条需要证明覆盖范围的结论。Coverage Receipt 至少回答：

```text
要求搜索哪些 filings/forms/accessions？
要求解析哪些 documents/sections/capabilities？
这些对象是否成功取得和解析？
搜索窗口和 entity roles 是否完整？
是否存在 parser/format/taxonomy 缺口？
结果是 COMPLETE / PARTIAL / FAILED / NOT_APPLICABLE？
```

只有 COMPLETE coverage 才能支持 `NOT_DISCLOSED_CONFIRMED`。

### 9.6 三个关键语义示例

#### E02：全年 8-K 扫描后没有破产事件

```text
value = 0
observation_status = OBSERVED
result_quality = EXACT
publication_status = PUBLISHED
```

它不是“SEC 没有数据”，而是“搜索完成，事件计数为零”。

#### B06：负权益

```text
value = null
observation_status = OBSERVED
result_quality = NOT_MEANINGFUL
publication_status = PUBLISHED
```

债务和权益都有证据，只是比率不具有经济意义。

#### 新 iXBRL transform 无法解析

```text
value = null
observation_status = FORMAT_UNSUPPORTED
result_quality = NO_RESULT 或 UNVERIFIED
publication_status = WITHHELD
```

不得映射为 `NOT_DISCLOSED_CONFIRMED`。

### 9.7 Reviewer 可以做什么

Reviewer 可以批准或拒绝：

- Metric Contract；
- Candidate selection；
- Entity Exception；
- Taxonomy compatibility mapping；
- Publication Policy 版本变更；
- Expected Change Manifest。

Reviewer 不得直接把某行从 UNVERIFIED 改成 PUBLISHED。人工决定形成新的版本化输入，系统重新 resolve/validate/publish。

---

## 10. Dataset Version、原子发布、公开视图与只读报告

### 10.1 Run 生命周期

```text
CREATED
→ DISCOVERING
→ INGESTING
→ NORMALIZING
→ RESOLVING
→ VALIDATING
→ READY_TO_PUBLISH
→ PUBLISHED
```

终止/旁路状态包括：

```text
NO_CHANGE
WITHHELD
FAILED
```

报告渲染不属于写状态机。

### 10.2 Candidate Snapshot

Resolve 结束产生不可变候选快照；Validate 只判断，不修改候选；Publish 只发布已通过的完整 snapshot。任何“validation 期间顺手修值”的逻辑都是架构违规。

### 10.3 原子发布

- Dataset Version 必须包含完整 snapshot 和版本 metadata。
- 任一 DATASET P0 失败，current pointer 不变。
- 同 snapshot hash 重复发布返回 NO_CHANGE。
- 并发相同 snapshot 最多产生一个版本。
- 已发布版本不可原地修改；修正必须产生新版本。

### 10.4 固定版本读取

页面或下游先取得 `current dataset version`，随后所有 metrics、evidence、history 请求固定该版本。页面加载期间 current 改变，不得混入新版本数据。

### 10.5 Public View 与 Review View

#### Public View

仅返回：

- Published PRIMARY；
- 已批准且政策允许的 ALTERNATE；
- 明确 N_A/absence/NOT_MEANINGFUL 状态；
- 不返回 candidate 或 withheld 数值。

#### Review View

授权用户可查看：

- selected/rejected/suppressed candidates；
- withheld reasons；
- parser/taxonomy diagnostics；
- Coverage Receipts；
- ComputationGraph 与 lineage；
- backtest 和审批。

二者必须引用同一 result IDs，不能建立互相对不上的第二套审核数据。

### 10.6 报告只读

Report/HTML/Markdown/Legacy CSV：

- 网络调用为 0；
- 不修改 canonical 数据；
- 不刷新 Golden expected；
- 不执行 repair；
- 只从指定 Dataset Version 确定性生成。

### 10.7 Legacy Projection

FSD 保留：

```text
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
REPORT_十公司财务指标.md
```

它们是 compatibility projection，不是权威存储。必须能反查 Dataset Version、result_id 和 definition version；删除后可从 v2 对象重建。

---

## 11. Strategy 目录与领域案例

本节保留历史领域知识和事故理由；当前实现细节、候选链和测试位置请查看对应 Metric Card。

### 11.1 B01 Revenue：直接标准事实

**稳定语义**：目标财年、公司整体、合并口径的 revenue。

**可变外壳**：不同公司 concept、taxonomy 年份、Company Facts/accession route。

**关键防线**：annual period、target accession、concept priority、entity/scope、完整 evidence。

**专家问题**：

- 当前命中的 concept 是什么，为什么优先于其他候选？
- duration 是否为目标年而非季度/stub？
- 是否错误选择 segment/product revenue？

**历史经验**：同一经济事实存在多种标准标签；候选链必须记录实际命中，不能按数值大小猜。

### 11.2 B03 EBITDA Margin：复杂 fallback 与 proxy

**稳定语义**：已批准的 GAAP EBITDA proxy / revenue；是否加回 impairment 由 contract 锁定。

**Resolver 工作**：选择 revenue、operating income、D&A；允许的重建路径和 cross-check 由 contract 决定。

**ComputationIR 工作**：对已选 observations 执行可重算公式。

**关键防线**：同 entity/period/accession/unit、annual duration、denominator nonzero、重建 cross-check、EXACT/APPROX 映射。

**专家问题**：

- direct operating income 还是 approved reconstruction？
- D&A 是直接值还是 depreciation + amortization？
- 是否混合 accession 或 period？
- APPROX 是否被 publication policy 明确允许？

### 11.3 B06 Debt-to-Equity：层级 resolver、多 scope 与正确弃权

**稳定语义**：总债务 / shareholders' equity；总债务的层级和禁止项由 contract 锁定。

**复杂性**：direct total、同族 current/noncurrent pair、restricted fallback、captive finance scope、负权益。

**关键防线**：防双计、禁止 DebtSecurities/fair-value/maturity/proceeds、scope 不混合、主值与候选分离。

**专家问题**：

- 选的是 consolidated、industrial 还是其他 scope？
- 为什么拒绝短债-only 或 captive-finance candidate？
- 负权益时是否保留输入 lineage 且返回 NOT_MEANINGFUL？

### 11.4 A01/A02 Basel Ratios：actual 与 threshold 的语义隔离

**稳定语义**：实际 Tier 1/CET1 ratio，带 methodology/entity scope。

**可变外壳**：公司扩展 concept、成员名和 taxonomy 版本。

**关键防线**：标准 methodology axis、unit=pure、actual-role、CET1 与 Tier1 区分、threshold 词法/role 排除、parent/subsidiary scope。

**历史事故**：实际比率和监管最低线可以拥有相同单位、期间和维度；只靠“看起来像 ratio”会把及格线选成公司实际值。

**专家问题**：

- rejected ledger 是否可见 threshold？
- actual 与 well-capitalized/minimum 是否分离？
- standardized/advanced、parent/bank subsidiary 是否明确？

### 11.5 B10/B11 Lodging KPI：表格、布局漂移与行业恒等式

**稳定语义**：approved scope 下的 occupancy/RevPAR absolute value。

**可变外壳**：HTML 排版、表头层级、列顺序、年度列节奏。

**关键防线**：header-by-name、scope priority、absolute-vs-change 区分、范围检查、`RevPAR ≈ ADR × Occupancy` invariant、table locator。

**历史事故**：把 “RevPAR increased 2.0%” 抽成 2.0 USD。vNext 必须保留该百分比候选和 `WRONG_UNIT/SEMANTIC_NEIGHBOR_UNAPPROVED` 拒绝理由。

### 11.6 B12 RPO/cRPO：instance-first 与替代指标诚实性

**稳定语义**：RPO/cRPO 是合同剩余履约义务，不等于 ARR 或 churn。

**关键防线**：structured instance 优先、total vs current/noncurrent reconciliation、USD/period、文本 fallback coverage、名称与经济含义一致。

**历史经验**：结构化事实已经存在时，不应为某家公司写日期句式正则。

### 11.7 C03 Executive Compensation：标准 ECD 与多人语义

**稳定语义**：approved PEO compensation observation；多 PEO 不得随意求和成一个“CEO 薪酬”。

**关键防线**：ECD concept、USD、目标年度、person/context scope、明细与主结果区分。

**历史事故**：系统曾 dump 出正确 ECD inventory 却没有消费，转而抓取无意义文本数字。此事故奠定“inventory/observation 到结果的最后一公里也必须有断言”。

### 11.8 E02 Bankruptcy Events：零是成功观察

**稳定语义**：目标财年窗口内符合 Item 1.03 规则的事件计数。

**关键防线**：完整 filing inventory、所有 roles/CIKs、accession 列表、item parsing 和 COMPLETE coverage receipt。

**专家问题**：

- 0 是否来自完整扫描，而不是缺少 8-K 文件？
- Coverage Receipt 是否包含全部 accession？
- value=0 与 value=null 是否严格区分？

### 11.9 定性风险/法律信号

Qualitative Signal 可以发布，但必须明确：

- 它是观察到的文本主题、存在性或结构化结论；
- 不等于律师意见或风险评分；
- source span、section 和 coverage 必须可审；
- AI 生成摘要若启用，属于独立 `ai_annotation`，不能替代事实观察。

---

## 12. 验证拓扑：Golden、Mutation、Backtest、SEC Suite 与 G0–G6

### 12.1 九层验证

1. Catalog compiler tests；
2. Adapter/parser conformance tests；
3. Strategy unit tests；
4. Property/metamorphic tests；
5. Mutation tests；
6. Filing fixture Golden tests；
7. Historical Catalog Release backtest；
8. Dataset release acceptance；
9. AI-off replay。

### 12.2 Golden 的角色

Golden expected 是版本控制输入，不是运行输出。实际结果不一致时：

```text
validation FAIL
→ 调查来源/实现/方法论
→ 如确需改变，提交 expected_change manifest 和审批
```

不得让 report/repair 自动刷新 expected 或 actual 来维持 PASS。

### 12.3 Property/Metamorphic 不变量

- 相同输入幂等；
- candidate 顺序独立；
- 重复事实不变；
- 加入低优先级候选不变；
- namespace prefix、context ID 和等价表示变化不改变事实身份；
- 公开排序稳定；
- no-change 不产生新 Dataset Version。

### 12.4 Mutation 必须覆盖的危险面

```text
unit/period/accession/scope substitution
semantic-neighbor concept substitution
Basel actual → threshold
scale/sign equivalent and non-equivalent changes
dimension/member substitution
HTML header/column reordering
hidden fact vs visible text conflict
parser fact omission
new taxonomy namespace
unsupported transform
```

每种 mutation 不仅要断言“不发布”，还要固定正确分支：WITHHELD、NEEDS_REVIEW、NOT_MEANINGFUL、N_A 或其他。

### 12.5 Historical Backtest

Catalog、strategy、parser、taxonomy 或 policy 变化时逐字段比较：

```text
value / unit
四维状态
scope / result_role
selected evidence
FormulaIR graph
publication
```

每条变化必须有 expected_change_id，否则为 UNEXPECTED 并阻止 release。

### 12.6 Gate G0–G6

#### G0 Baseline Reproducibility

Legacy/current baseline、raw evidence、Golden、Validation、unittest 可重放，expected 不被运行时改写。

#### G1 Architecture Purity

Metric Kernel/report 不联网；report 只读；无 last-writer-wins；无隐藏 identity branch；strategy 只消费 observations。

#### G2 Data Semantics

四维状态闭包；publication 派生；E02=0、B06 NOT_MEANINGFUL、N_A/PROHIBITED、多 scope 行为正确。

#### G3 Auditability

100% Published numeric 有 graph、lineage、raw asset；selected/rejected 可审；历史版本不可变。

#### G4 Format/Taxonomy Resilience

未知 dialect、material parser disagreement、semantic neighbor 均 fail closed；taxonomy 可追溯；SEC 官方 suite 通过受支持部分；Silent Format Regression Rate=0。

#### G5 Release Mechanics

no-change、原子发布、并发、固定版本 API、legacy rebuild 均通过。

#### G6 AI

AI-off replay；AI 无权威写权限；proposal benchmark 达标；mutation 零泄漏。未达标可关闭 AI，而 G0–G5 系统独立成立。

---

## 13. 专家审计手册

### 13.1 审计 Published Numeric Result

```text
1. 固定 Dataset Version，不审浮动 current。
2. 确认 Catalog Release、definition version、policy version。
3. 确认完整 grain：company/metric/period/scope/role。
4. 阅读四维状态和 publication reason codes。
5. 检查 selected candidate 和关键 rejected candidates。
6. 检查 FormulaIR，并独立 graph recomputation。
7. 沿 lineage 到每个 Canonical Observation。
8. 从 observation 回到 RawAsset 和精确 locator。
9. 检查 taxonomy package、adapter/parser manifest 和 agreement。
10. 检查 Coverage Receipts、Validation、Backtest 和 audit verdict。
```

### 13.2 审计零事件

以 E02 为例：

- value 必须是 `0` 而不是 null；
- observation 必须是 OBSERVED；
- receipt 必须覆盖整个财年窗口、所有目标 CIK/roles 和 8-K accessions；
- parser/source 失败不得存在；
- 搜索规则版本必须固定；
- absence/zero 证据是“完整扫描清单”，不是一条空 quote。

### 13.3 审计“未披露”

`NOT_DISCLOSED_CONFIRMED` 的检查重点不是结果行，而是 Coverage Receipt：

```text
required source set 是否完整？
所有文档是否成功取得？
required sections/capabilities 是否执行？
是否有 FORMAT_UNSUPPORTED/PARSE_FAILED/TAXONOMY_UNREGISTERED？
search terms/semantic scope 是否属于 approved contract？
receipt completeness 是否 COMPLETE？
```

任何缺口都只能是 NOT_FOUND/PARTIAL/WITHHELD，不能宣称“未披露”。

### 13.4 审计 WITHHELD

WITHHELD 不等于低质量垃圾。它可能表示：

- 当前来源格式尚未支持；
- parser material disagreement；
- 语义近邻尚未批准；
- approximate proxy 不被 policy 允许；
- validation P0 失败；
- catalog/approval 未完成。

审核时应确认系统是否**正确地拒绝了不安全发布**，而不是只问“为什么没有值”。

### 13.5 调查 Parser Disagreement

```text
1. 固定同一 RawAsset/taxonomy packages。
2. 对比 parser manifests 和插件参数。
3. 确认 canonical fact key 是否相同。
4. 对比 raw lexical、scale/sign、normalized decimal。
5. 对比 entity/period/unit/dimensions/tuple path。
6. 判断差异是否在强制比较域。
7. 检查官方 SEC suite 是否有相关案例。
8. 添加最小复现 fixture 和 mutation。
9. 修复后离线 replay，不能直接改 Published 结果。
```

### 13.6 审核 Taxonomy Migration

- 查看 package hash 和官方 release diff；
- 查看 concept/type/periodType/balance/relationship/reference 变化；
- 确认 compatibility 分类；
- 名称相似但 BROADER/NARROWER 不得自动替换；
- 查看受影响 Metric Cards 和历史 backtest；
- 查看 parser shadow 和 semantic-neighbor mutation；
- 确认 Finance/Data 审批与新 Catalog Release。

### 13.7 审核 Catalog Change

不只看 Git 文本 diff，要看：

```text
Semantic Diff
Historical Impact Backtest
Selected/Rejected Candidate changes
FormulaIR shape changes
Applicability/trait changes
Coverage/publication changes
Expected Change Manifest
reviewed semantic hash
```

### 13.8 审核 AI Proposal

- source locator 是否能解析到固定 RawAsset；
- quote/cell/fact 是否真实存在；
- proposed concept 是否语义近邻；
- period/unit/entity/dimension 是否正确；
- proposal 是否修改了不允许的字段；
- deterministic replay、mutations、backtest 是否通过；
- AI 模型一致不算事实证明；
- 最终批准必须由相应人类角色完成。

---

## 14. 扩展手册：新公司、新行业、新指标、新格式、新 parser

### 14.1 新增公司

```text
1. 登记稳定 company_id、CIKs、roles、名称历史、fiscal year end。
2. 分配 typed traits，记录来源、理由、有效期。
3. Catalog compile，确保无 applicability conflict。
4. Discovery/ingest 并生成 dialect/capability manifest。
5. Normalize observations；必要时 primary/shadow。
6. Resolve/validate shadow run。
7. 阅读 coverage、withheld 和 candidate review。
8. 对代表指标做人工 audit。
9. 发布新 Dataset Version。
```

“新增公司不改代码”只在其 source dialect、traits 和 strategies 已支持时成立。新格式需要 adapter 是正常扩展，不应通过公司名分支规避。

### 14.2 新增行业或商业模式

- 定义/复用 typed traits，而不是复制一个大 profile；
- 更新 applicability rules 并执行 conflict compile；
- 选择 3–5 家真实公司建立 corpus；
- 先寻找 structured taxonomy facts，再考虑 table/text；
- 对行业 KPI 定义代数/业务 invariant；
- 添加 positive、negative、correct-abstention fixtures；
- 新 Catalog Release + backtest。

### 14.3 新增指标

```text
经济定义与非目标
→ metric kind / grain / scope
→ applicability traits
→ source priority / required capabilities
→ resolver / rejection reasons
→ FormulaIR shape / unit algebra
→ evidence and Coverage Receipt contract
→ quality/publication options
→ positive/negative/abstention examples
→ mutation and historical backtest
→ Finance/Data approval
→ Catalog Release
```

### 14.4 新增 SEC 文件格式或 capability

```text
捕获并 hash RawAsset
→ dialect fingerprint 标记 unknown/new
→ 受影响结果 WITHHELD
→ 编写/升级 adapter
→ Canonical schema validation
→ 官方 SEC suite（如适用）
→ project fixtures/mutations
→ primary/shadow compare
→ offline historical replay
→ parser/adapter manifest release
```

### 14.5 新 taxonomy 年份

```text
登记 package + hash
→ 生成 taxonomy diff
→ 反向索引受影响 contracts
→ compatibility 分类
→ parser shadow
→ semantic-neighbor mutation
→ historical backtest
→ Finance/Data review
→ 新 Catalog Release（仅有语义影响时）
```

### 14.6 引入或更换外部 parser

任何外部 parser，包括 Arelle，都走同一流程：

```text
固定依赖与插件 manifest
→ adapter 输出 CanonicalObservation
→ SEC suite conformance
→ project fixture parity
→ historical corpus shadow
→ material diff 归因
→ G4 release gate
→ 角色提升或拒绝
```

不得因“行业广泛使用”跳过项目验证。

---

## 15. 运行监控、质量北极星与事故响应

### 15.1 核心监控

| 指标 | 定义/目标 |
|---|---|
| Published-Wrong Rate | 随机审计层中，经审核确认错误的 Published 结果 / 已审核 Published 结果；release qualification 目标 0 |
| Targeted Audit Wrong Rate | 定向高风险样本独立报告，不与随机层混算 |
| Published-Unverifiable Rate | 无法从 raw asset + graph + lineage 重放的 Published 比例；目标 0 |
| Silent Format Regression Rate | 格式变化后未告警却改变 Published 结果的比例；目标 0 |
| Parser Disagreement Published Count | material disagreement 仍被发布的数量；目标 0 |
| Coverage Completeness Rate | required receipts 中 COMPLETE 比例，按 capability/metric 分层 |
| Catalog Drift Count | runtime/config 与 APPROVED lock 不一致次数；目标 0 |
| Reproducibility Failure Count | 同版本相同输入重放 hash 不一致次数；目标 0 |
| AI Unauthorized Action Count | AI 越权写入或绕过门禁次数；目标 0 |

### 15.2 随机层与定向层审计

- **随机层**用于估计总体 Published-Wrong Rate，抽样政策必须版本化并保持跨期可比。
- **定向层**覆盖新/变化指标、APPROX、事件零值、N_A、WITHHELD、新 parser/taxonomy、高风险 source class。
- 两层分别报告样本量、错误数和结论，不得把定向高风险样本当总体错误率。

### 15.3 P0 事故触发

以下任一事件必须创建 P0 incident 并冻结受影响发布：

```text
确认 Published value/status 错误
material parser disagreement 被发布
Published lineage/raw asset 缺失
silent format regression
current pointer 原子性失败
已发布 Dataset Version 被改写
Golden expected 被 runtime 修改
AI 获得权威写权限或伪造 locator 进入发布
```

### 15.4 事故处理原则

- 不原地修 Published Dataset；发布新版本。
- 保留失败 run、validation 和事故时间线。
- 根因必须归到 source/adapter/parser/taxonomy/catalog/strategy/policy/release/AI 权限之一。
- 修复必须增加 regression fixture 或 mutation。
- 事故关闭前必须离线 replay、backtest 和 audit。

### 15.5 FSD 落地后的开放风险

- parser comparison canary 与噪声校准；
- 官方 SEC suite 覆盖的是提交验证，不等于所有消费解析场景；
- taxonomy diff/relationship 影响分析的长期成本；
- HTML/text 表格的召回与 layout diversity；
- migration parity 的人工审核峰值；
- Published-Wrong Rate 小样本不确定性；
- 外部 parser/plugin 的供应链、升级和安全响应；
- AI proposal 的低有效率或审阅成本反超收益。

---

## 16. AI Proposal：允许做什么、如何审核、何时关闭

### 16.1 状态

```text
DISABLED
SHADOW
APPROVED_FOR_PROPOSALS
```

AI 状态必须位于 `[生成]` release manifest。未通过 Gate G6 时不得描述为生产启用。

### 16.2 允许任务

- custom/standard concept scouting；
- table/section locator proposal；
- taxonomy mapping proposal；
- Metric Contract patch 草稿；
- positive/negative/mutation fixture 草稿；
- exception triage 和审核摘要。

### 16.3 禁止任务

- 写 Metric Result；
- 修改 APPROVED Catalog；
- 修改 Golden expected；
- 赋予 EXACT/PUBLISHED；
- 直接覆盖 selected candidate；
- 绕过 source pointer、lineage、validation 或审批；
- 因两个模型意见一致自动放行。

### 16.4 Filing 内容是不可信数据

SEC filing 中的文本可能包含任意自然语言。AI 系统必须把它当数据，不当工具指令：

- 无任意工具/网络/写权限；
- source spans 与 prompt 指令隔离；
- schema constrained output；
- 所有 locator 确定性解析；
- 模型、prompt、input/output hash 全记录。

### 16.5 Proposal 晋级流程

```text
AI proposal
→ locator resolve
→ period/unit/entity/dimension validation
→ contract/strategy execution
→ mutation + project fixtures
→ historical backtest
→ Finance/Data review
→ new Catalog Release
```

### 16.6 启用门

AI 层只有在以下条件达到 FSD 指标时才可从 SHADOW 晋级：

- source pointer 可解析率；
- proposal 确定性验证后有效率；
- matched-task benchmark 的中位工程时间下降；
- mutation 泄漏为 Published=0；
- AI-off replay 完整成功。

不达标直接关闭 AI；G0–G5 核心系统不受影响。

---

## 17. 常见错误模式与反模式

### 17.1 把本指南当指标定义源

**症状**：开发者从历史案例复制 concept chain，而不看当前 Metric Card。

**处理**：Catalog Release 是权威；指南只解释 why。

### 17.2 把 SEC 官方套件全绿当业务正确

**症状**：Arelle/adapter 通过 EFM test suite，就认为 A02/B10 正确。

**处理**：官方 suite 只覆盖标准 conformance；必须同时通过 project semantics、Golden、mutation 和 backtest。

### 17.3 把 Arelle 当神谕

**症状**：Arelle 与另一 parser 不同，直接相信 Arelle；或 Arelle validation warning 直接映射业务 status。

**处理**：Arelle 是可替换实现；material disagreement 必须隔离调查。

### 17.4 Parser 在线偷偷取得 taxonomy

**症状**：历史 replay 因远端 package 更新而改变。

**处理**：使用 hash-pinned local taxonomy registry，记录 network policy。

### 17.5 Parser 失败被写成“SEC 未披露”

**处理**：PARSE_FAILED/FORMAT_UNSUPPORTED → WITHHELD；只有 COMPLETE receipt 支撑 NOT_DISCLOSED_CONFIRMED。

### 17.6 有 value，但 evidence/lineage 不支持

**处理**：RESULT P0；不得保留 Published；补 locator/lineage 或修 strategy。

### 17.7 Semantic neighbor 偷渡

**症状**：名称很像的 profit/revenue/debt concept 被自动替换。

**处理**：`SEMANTIC_NEIGHBOR_UNAPPROVED`；taxonomy compatibility + Finance Review。

### 17.8 Actual 与 regulatory threshold 混淆

**处理**：threshold 保留为 rejected candidate，原因 `THRESHOLD_NOT_ACTUAL_RATIO`。

### 17.9 百分比变化当绝对 KPI

**处理**：单位、header、row locator、行业 invariant 和 negative fixture。

### 17.10 Candidate 顺序依赖

**症状**：输入行重排后结果改变。

**处理**：G1/G2 失败；修确定性 rank 和 tie handling。

### 17.11 Reviewer 直接 override publication

**处理**：禁止；形成版本化 candidate/contract/policy 决定后重新运行。

### 17.12 用 Expected Change Manifest 偷渡大面积变化

**处理**：每条变化必须可解释、按 semver 审核；manifest 不是免检白名单。

### 17.13 Legacy CSV 反向成为输入

**处理**：Legacy 只由 Dataset Version 投影；resolver 不得读取。

### 17.14 Report 中修数据或联网

**处理**：G1/G5 失败；报告前后 canonical/Golden hash 必须不变。

### 17.15 隐藏公司身份分支

**症状**：strategy/policy 中比较 company_id/ticker/CIK。

**处理**：`ARCH_HIDDEN_IDENTITY_BRANCH` lint 失败；使用 traits、capabilities 或显式 entity exception。

### 17.16 零与 null 混淆

- `0`：成功观察到零。
- `null`：没有数值，由状态解释。

API、报告和 Legacy projection 必须保持区别。

---

## 18. 当前实现地图、交付物与命令索引

### 18.1 不手工猜物理架构

FSD 允许工程团队选择内部模块和存储。因而本指南只固定逻辑对象；实际代码路径、表名、CLI 和 job ID 必须由 implementation manifest 自动生成。

<!-- GENERATED:IMPLEMENTATION_MAP:START -->

```text
{{IMPLEMENTATION_MODULE_MAP}}
```

<!-- GENERATED:IMPLEMENTATION_MAP:END -->

### 18.2 v2 最小权威输出

FSD 迁移期要求存在以下 canonical outputs（扩展名由实现决定）：

```text
outputs/v2/canonical_observations.*
outputs/v2/coverage_receipts.*
outputs/v2/metric_candidates.*
outputs/v2/metric_results.*
outputs/v2/lineage_edges.*
outputs/v2/validation_results.*
```

另有：

```text
Dataset Version manifest
Catalog Release lock and review artifacts
Computation graphs
RawAsset/SourceObservation manifests
Taxonomy registry
Adapter/parser manifests
Parser agreement / format drift reports
Historical backtest / expected change manifest
```

### 18.3 人类审核产物

必须自动生成：

1. Metric × Trait Applicability Matrix；
2. 单指标审核卡；
3. Catalog Semantic Diff；
4. Historical Impact Backtest；
5. Selected/Rejected Candidate Review；
6. Taxonomy Impact Report；
7. Format Drift/Parser Agreement Report；
8. Release Gate Summary。

### 18.4 Legacy 输出

```text
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
REPORT_十公司财务指标.md
```

这些文件必须标注 deprecated/compatibility，并可反查 Dataset Version。

### 18.5 命令索引

实际命令由 CI 生成，不得在本指南长期手工复制：

<!-- GENERATED:COMMAND_INDEX:START -->

| 逻辑操作 | 当前命令/Job |
|---|---|
| Compile Catalog | `{{CMD_COMPILE_CATALOG}}` |
| Ingest/Discover | `{{CMD_INGEST}}` |
| Normalize Observations | `{{CMD_NORMALIZE}}` |
| Run Primary/Shadow Compare | `{{CMD_PARSER_COMPARE}}` |
| Run SEC Conformance Suite | `{{CMD_SEC_CONFORMANCE}}` |
| Offline Replay | `{{CMD_OFFLINE_REPLAY}}` |
| Resolve Candidate Snapshot | `{{CMD_RESOLVE}}` |
| Validate/Backtest | `{{CMD_VALIDATE}}` |
| Publish Dataset Version | `{{CMD_PUBLISH}}` |
| Render Fixed-Version Report | `{{CMD_RENDER_REPORT}}` |
| Run Hidden Identity Lint | `{{CMD_IDENTITY_LINT}}` |
| Verify Guide Generated Blocks | `{{CMD_DOC_DRIFT_CHECK}}` |

<!-- GENERATED:COMMAND_INDEX:END -->

---

## 19. Legacy Round 3、规则考古与制度记忆

### 19.1 Legacy 基线的正确位置

旧《SEC_metrics 项目全景与专家指南》准确描述 Round 3 spike：10 家公司、单体流水线、M0–M7、legacy status、CSV 主矩阵和 63 Golden/75 Validation/17 unittest。vNext 启用后，应将其冻结为：

```text
docs/legacy/SEC_metrics_spike_round3_项目全景与专家指南.md
```

它的作用是：

- baseline_manifest 和 migration parity；
- 历史事故与设计动机；
- 旧消费者兼容；
- 回归语料和制度记忆。

它不再定义当前系统。

### 19.2 Legacy Round 3 历史实况

[实测/历史] Round 3 曾包含约：

```text
230 条指标结果
226 条证据
63 条 Golden
75 项 repair validation
17 个 unittest
约 14,000 行 sec_pipeline.py
13 个阶段薄封装
```

这些数字应保留在 legacy appendix，不应继续作为 vNext 当前规模。vNext 支持多 scope、alternate/candidate 和 long-form observation 后，行数天然不同。

### 19.3 架构族谱

| Legacy 概念 | vNext 归宿 |
|---|---|
| 公司登记属性 | Entity Registry + versioned typed traits |
| 能力探针 | Adapter Capability Manifest + required source capabilities |
| 词法配置 | Metric Contract parameters / controlled vocabulary |
| industry profile | 可组合 typed traits + applicability compiler |
| marker extractor | Versioned resolver/strategy 或 adapter capability |
| 候选链 | Contract source priority + Candidate Ledger |
| 300–400 天窗 | Approved hard constraint |
| RevPAR 恒等式 | Invariant/cross-check + Formula/validation artifact |
| Basel threshold sidecar | 全指标通用 Rejected Candidate Ledger |
| no-company-literals 工具 | `ARCH_HIDDEN_IDENTITY_BRANCH` CI gate |
| 公司补丁六条件 | Entity Exception schema + approval + expiry |
| Golden 不改期望值 | expected/results 分离 + immutable input |
| 召回棘轮 | Historical backtest + semver + expected change manifest |
| coverage matrix | Coverage Receipts + four-dimensional states |
| metrics_matrix | Dataset Version 的 Legacy projection |
| M7 repair/report | resolve/validate/publish + read-only report |

### 19.4 规则考古表

| 奠基事故/经验 | vNext 机制 |
|---|---|
| RevPAR=2.0，quote 不支持 value | Structured locator、candidate rejection、industry invariant、lineage P0 |
| Basel threshold 赢过 actual ratio | `THRESHOLD_NOT_ACTUAL_RATIO`、candidate ledger、semantic mutation |
| ECD facts 已 dump 却未消费 | Observation→candidate→result coverage 与 Golden |
| RPO 文本正则重造结构化事实 | required capabilities、instance-first resolver |
| Successor stub 被当全年/未披露 | period hard constraint、entity traits、Coverage Receipt |
| E02 零值写成 NOT_AVAILABLE | EVENT metric kind、OBSERVED+EXACT、0/null 分离 |
| B06 负权益写成来源缺失 | OBSERVED + NOT_MEANINGFUL + preserved lineage |
| 报告阶段 repair 和联网 | G1 只读报告、explicit resolve/validate/publish |
| Golden CSV 循环自证 | immutable expected、live recomputation、G0 |
| 公司名分支回潮 | traits/entity exception + identity lint |
| parser scale/sign 风险 | Canonical raw semantics、primary/shadow、SEC suite、mutation |
| 缺陷迁移到未断言维度 | Coverage Receipt、四维状态、mutation 和质量北极星 |

### 19.5 守恒律

项目的核心制度经验仍然成立：

> **门禁边界就是质量边界；被度量的缺陷会减少，未被度量的缺陷会成为新的藏身处。**

vNext 的改进不是宣称“没有缺陷”，而是扩大断言拓扑：给缺席、格式、taxonomy、parser 分歧、候选拒绝、publication、版本不可变和 AI 权限都增加可验证约束。

---

## 20. 专家训练清单与术语表

### 20.1 读完后应能完成

1. 固定 Dataset Version，追踪一个 Published 数值到 RawAsset。
2. 通过 Metric Card 审核经济定义、FormulaIR、fallback 和 publication options。
3. 区分 0、null、NOT_FOUND、NOT_DISCLOSED_CONFIRMED、FORMAT_UNSUPPORTED 和 NOT_MEANINGFUL。
4. 阅读 selected/rejected candidate ledger，解释 actual/threshold/semantic neighbor。
5. 独立重算 ComputationGraph 和检查单位代数。
6. 审核 Coverage Receipt，证明一次“未披露”或零事件结论。
7. 调查 primary/shadow parser disagreement。
8. 解释 SEC 官方 test suite、parser diversity 和 project Golden 各自覆盖什么。
9. 审核 taxonomy migration 和历史 backtest。
10. 新增公司、trait、metric、adapter 或 parser，不引入隐藏身份分支。
11. 识别报告写路径、legacy 反向输入和 publication override 等架构违规。
12. 审核 AI proposal，验证 locator、语义和权限边界。

### 20.2 术语表

```text
RawAsset                 按字节 SHA-256 寻址的不可变原始来源资产
SourceObservation        一次网络/来源观察的请求与结果记录
Source Adapter           把某类来源转成 Canonical Observation 的可替换外壳
Canonical Observation    来源无关、长格式、保留原始语义和 locator 的观察事实
Dialect Fingerprint      filing/package 的格式、namespace、transform、布局等指纹
Primary/Shadow Parser    两个实现独立的解析路径，用于发现 material disagreement
Parser Manifest          parser、插件、runtime、配置和 taxonomy cache 的版本记录
Taxonomy Registry        多年度 taxonomy packages、hash、entry points 和审批状态
Catalog Release          一组原子化、已审批、可运行的指标契约发布
Metric Contract          指标语义、粒度、适用性、resolver、公式、证据和政策契约
Typed Trait              正交的行业、业务模式、实体连续性等属性
Entity Exception         显式审批、带有效期和证据的公司级现实例外
Metric Candidate         某指标/粒度下一个可选择或应拒绝的观察解释
Rejection Ledger         所有决策相关 rejected candidates 与原因
ComputationIR/Graph      受限、可重算、同时生成公式和 lineage 的计算结构
Lineage Edge             result、graph、observation、raw asset 之间的单条关系
Coverage Receipt         证明 required source/search scope 是否完整执行的回执
Applicability Status     REQUIRED/OPTIONAL/N_A_STRUCTURAL/PROHIBITED
Observation Status       OBSERVED/PARTIAL/NOT_FOUND/NOT_DISCLOSED_CONFIRMED 等
Result Quality           EXACT/APPROX/QUALITATIVE/NOT_MEANINGFUL/UNVERIFIED/NO_RESULT
Publication Status       PUBLISHED/WITHHELD/NEEDS_REVIEW；由 policy 计算
Dataset Version          原子、不可变、可固定读取的完整发布快照
Public View              只暴露允许公开消费的结果
Review View              暴露候选、withheld、诊断和审核材料的受限视图
Golden Expected          人工/外部锁定的预期输入，不得被 runtime 修改
Mutation Test            故意改变期间、单位、概念、维度、布局等以验证拒绝能力
Historical Backtest      新旧 Catalog/strategy/parser/taxonomy 的逐字段影响比较
SEC Public Test Suite    SEC 官方 Interactive Data validation 案例库
Arelle                   可作为 primary/shadow/conformance runner 的外部 XBRL processor
Published-Wrong Rate     随机审计层已确认错误 / 已审核 Published 结果
Silent Format Regression 格式变化未告警却改变 Published 结果
AI Proposal              无权威写权限的候选规则、locator、契约或测试草案
Legacy Projection        从固定 Dataset Version 生成的旧 CSV/报告兼容视图
```

---

## 21. 外部规范与参考资料

以下版本必须由 registry/manifest 记录，本文链接只是导航，不是运行时“latest”依赖：

1. [SEC Interactive Data Public Test Suite](https://www.sec.gov/data-research/interactive-data-public-test-suite)
2. [SEC EDGAR Filer Manual](https://www.sec.gov/submit-filings/edgar-filer-manual)
3. [SEC Operating Company Taxonomies](https://www.sec.gov/data-research/structured-data/taxonomies-schemas/standard-taxonomies/operating-companies)
4. [Arelle Open Source XBRL Platform](https://github.com/Arelle/Arelle)
5. `SEC_metrics_vNext_FSD_v1.1.md`
6. 当前 Catalog Release 自动生成的 Metric Cards、Semantic Diff 与 Gate Summary
7. 冻结的 Legacy Round 3 指南和 baseline manifest

[考证] 截至 2026-07-15，SEC 当前公开测试套件页面列出的版本日期为 2026-03-16，EDGAR Filer Manual Volume II 为 Version 77；这些是 registry 输入，不得硬编码成永久常量。Arelle 当前公开说明支持 XBRL 2.1、Dimensions、Taxonomy Packages、Inline XBRL 1.1 和 SEC EFM validation；项目仍必须固定具体版本、插件和运行 manifest，并保留独立 shadow 与项目级业务验证。
