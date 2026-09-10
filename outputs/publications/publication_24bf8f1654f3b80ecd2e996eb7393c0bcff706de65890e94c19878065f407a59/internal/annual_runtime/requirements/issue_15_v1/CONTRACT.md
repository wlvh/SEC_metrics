# [vNext] 全行业统一交付：39 指标迁入 Spec 驱动平台、AI 调用控制、legacy 语义生产者退出

**STATUS: BLOCKED\_FOR\_AUTHORITY\_TRANSFER** 在 `requirements/issue_15_v1/` 快照、transfer manifest、frozen producer inventory、baseline receipt 与第 5 节全部新 Decision 合并前，本文仅为 proposed authority。**不得据此修改任何 production semantics，不得发起任何付费 provider 调用。**

**Requirement Authority**：本 Issue 冻结后的 exact bytes → `requirements/issue_15_v1/CONTRACT.md`。运行时权威始终是仓库文件（`requirements.py::load_requirement_snapshot` 校验 `sha256_file`，从不读取 live issue）。 **Parent closure**：`ai_first_v3_3_1`。继承其 evidence / publication / fail-closed invariants；第 5 节列出的条目被新 Decision 取代。 **Supersedes**：Issue #12 的全部未完成产品责任。#12 关闭为 superseded，正文不再修改。

> **代码引用约定**：一律使用 `path::symbol`，不使用行号。exact 代码版本由 `baseline_manifest.repository_commit` 绑定。

---

## 1. 交付目标（范围不可缩小）

将当前 39 个财务指标**全部**迁入统一的 Spec 驱动平台，使 legacy 语义生产者全部退出生产路径。

关闭条件只有一个：**第 39 个指标进入累计 migrated set，且冻结清单中最后一个 legacy semantic producer 被证明 production-unreachable。**

**范围 ≠ 原子首发。** 一个 Requirement Authority、一个不可缩小的 39 指标范围、一个最终 Done；内部采用单调 ratchet 降低每次生产切换的故障域。跨行业 Reader 不得延期到本 Issue 之外，也不要求 39 个指标在同一次 publication 事务中首次切换。

**为什么必须一次覆盖全部指标**：四指标切换后的稳态是双体系并存——两套指标定义、两套 Evidence 模型、两套 Review、两套 publication producer、两套失败状态语义。`scripts/vnext/` 现有 35,148 行只服务 4 个指标，legacy 管道 60,175 行服务其余 35 个。FSD §18 的"新布局不修改生产 Python"在 4/39 迁移度下等于未达成。本 Issue 的产品价值是**消灭第二套系统**。

---

## 2. 事实基线

正文只给出摘要供人阅读。**Requirement Authority 是 WB-1 离线生成的** **`requirements/issue_15_v1/source_strategy_baseline_receipt.json`****，不是本节的人工汇总。** 二者冲突时以 receipt 为准。

```
outputs/metrics_matrix.csv        230 行 / 39 metric_id / 10 家公司
稀疏分布                          A01–A13 各 1 行（仅 JPM）；B01 9 行、B03 9 行（缺 JPM）；
                                  B10/B11 各 1 行（仅 Marriott）；B12 1 行；B13 2 行；C/D/E 各 10 行
config/company_registry.csv       10 家公司 / 9 个 profile（manufacturing 有 2 家）
outputs/active_publication.json   不存在；当前无任何 committed active pointer
full acceptance                   全部 BLOCKED / FAILED，从未成功

```

**切分 A：按指标的当前 status 构成分类**（合计 39 指标 / 230 行）。此处的标签描述**当前 legacy status**，不是目标路由——A09 / A13 / D04 在目标路由中是 `structured_first_ai_fallback`，实现者不得因本表标签跳过结构化路径。

```
类别              指标数  行数   指标
DET_ONLY            16     81    A01 A02 A05 A06 A07 A08 A10 B01 B02 B03 B04 B05 B07 B08 B09 B12
MIXED                8     79    B06 C01 C03 C04 D02 E01 E03 E05
AI_STATUS_ONLY      13     50    A03 A04 A09 A11 A12 A13 B10 B11 B13 C02 D01 D03 D04
ABSENCE_ONLY         2     20    E02 E04（全部 NOT_AVAILABLE_SEC，需 CLOSED_WORLD coverage）

```

**切分 B：按 status 的行分布**（同样合计 230，**与切分 A 不可相加**）：确定性 status 136 行 / AI status 63 行 / 缺失 status 31 行。

```
成本事故（10 份 fixtures/vnext/layouts/*/provider_response.json 累加）
  prompt 5,180,046 / completion 17,714 / total 5,197,760
  cache hit 1,138,304 / miss 4,041,742 / input 占比 99.66%；被替代的 8 次占 80.14%
  hilton-v4 与 v5 的 request sha256 完全相同（重复付费 474,677 tokens）
  其余 6 次两两不同（每次 task contract 微调）→ exact-hash 复用只能挽回 9.1%

单次请求构成（hilton-2024-sec-layout-v7）
  envelope 1,727,203 B ＝ system 5,118 B ＋ user 1,507,768 B
  user ＝ untrusted_table_data 1,505,424 B ＋ manifest 2,365 B ＋ task 759 B ＋ system_contract 113 B
  实测 prompt_tokens 472,736 → 3.2 bytes/token
  16 张表 / 8,784 cell；空 cell 5,348（60.9%）、non-origin 展开 cell 4,648（52.9%）
  已验证 731 个 non-origin cell 与其 origin 逐字段相同（纯冗余）

```

`source_strategy_baseline_receipt.json` 至少含：`matrix_sha256` / `row_count` / `metric_id_set` / `metric_id_set_hash` / `rows_by_metric` / `rows_by_current_status` / `metrics_by_target_source_mode`。

---

## 3. 从 #12 继承的确切边界

**INHERITED\_IMPLEMENTED**：R2/R3 合同、MetricSpec 编译器、Run/Evidence/Review/Calculator、recorded 与 live operator、review CLI、Projector、PublicationView、CAS、failure protection、rollback primitives、`release_input_plan_id` 内容寻址计划机制。

**INHERITED\_REUSABLE\_EVIDENCE**（按当前 repository authority 重新验证后可直接复用，**不需重新下载**）：exact SEC raw bytes、immutable request-attempt evidence、SourceReference、accession/document identity、SEC acquisition receipt。

**INVALIDATED\_QUALIFICATION**（只失效语义层，不失效上述原始字节）：provider request/response qualification、Reader schema qualification、prompt 与 serialization qualification、`review_unit_hash` stability evidence。凡 serialization / scope contract / task contract / prompt / schema 变更，对应 family 的 qualification 失效。

**INHERITED\_PENDING**：Marriott 正式 live、十公司 staging、strict compatibility、`outputs/active_publication.json`、committed predecessor/active publication、真实 new→rollback→restore terminal receipts、full acceptance return code 0。

---

## 4. 三个 key 集合（D-30）

`projector.py::_release_context` 按 `registry × migrated_metric_ids` 生成内部结果坐标；`projector.py::project_metric_rows` 保留全部未迁移 legacy 行、替换已迁移行、把 legacy 中不存在的 migrated key **追加**到尾部。三个集合不得混用：

```
Vn = registry × cumulative_migrated_metric_ids     vNext 必须生成的内部结果坐标
L  = frozen legacy public key set = 230            冻结的 legacy 公开坐标
Pn = L ∪ Vn                                        第 n 档完整 public matrix 的 key set

```

```
四指标档：V=40,  L=230, P=250
终档：    V=390, L⊂V,   P=390

```

**机械门禁（每档）**：

```
vNext result key set      == registry × cumulative_migrated_metric_ids
public candidate key set  == frozen_legacy_key_set ∪ vNext_result_key_set
new public keys           == vNext_result_key_set − frozen_legacy_key_set
所有 new public keys 的 applicability == N_A_STRUCTURAL 且 status == N_A_STRUCTURAL
frozen_legacy_key_set 的 keyset hash 在全部档位不变

```

### D-30：最终 public matrix 采用 dense key policy（显式产品批准）

这是产品选择，**不是"因为 Projector 这样实现所以必须这样"**。已评估的替代方案 B（internal dense 390 / public sparse 230）同样可行，代价是 Projector 需要一条显式 sparse projection 规则、internal 与 public 集合永久不同。本 Issue 选择方案 A。

```
{
  "result_key_policy": "DENSE_REGISTRY_X_FINAL_METRICS",
  "company_count": 10,
  "final_metric_count": 39,
  "final_vnext_result_key_count": 390,
  "frozen_legacy_key_count": 230,
  "frozen_legacy_keyset_hash": "sha256:...",
  "row_order_policy": "LEGACY_ORDER_THEN_SORTED_ADDITIONS",
  "row_order_is_authoritative": false
}

```

**每档 ReleasePlan 必须绑定全部 authority hash**（否则等量替换一个 company ID 或 metric ID 无法被发现）：

```
company_registry_sha256
final_metric_id_set_hash
source_strategy_registry_sha256
producer_inventory_sha256
qualification_matrix_subset_hash
frozen_legacy_keyset_hash

```

- **不做终档重排。** 重排只会制造第二次全表 byte mutation、全文件 diff、额外 receipt 与 rollback 场景，无业务价值。
- **对冲条款（写入** **`docs/business_user_guide.md`** **与 capability contract）**：`(company, metric_id)` 是唯一稳定标识，**行序不具权威性**，下游不得依赖行号或行序。
- 业务报告默认隐藏 `N_A_STRUCTURAL`；root CSV 保留完整矩阵。

---

## 5. Decision（WB-1 必须落盘）

`requirements.py::_resolve_decisions` 按 `decision_id` 分组解析 supersede 链，parent hash 必须存在于**同一分组**，否则 `Decision chain has a detached parent`。**因此不存在跨 ID supersede，也不为此改造 Decision 引擎。**

| ID | 关系 | 内容 |
|---|---|---|
| **D-01（新 tip）** | `decision_id = D-01`；`supersedes_decision_id = 当前 effective D-01 的 record hash` | TransportPolicy 完整字段保留；`retry_count: 0`（不改字段名）；`maximum_payload_bytes: 8388608` 保留为次级护栏 |
| **D-26（新 tip）** | `decision_id = D-26`；`supersedes_decision_id = 当前 effective D-26 的 record hash` | 完整替换 TestPolicy；保留 fast/local 原则，但不得再禁止本 Issue 所需的短小确定性 freeze/replay、并发、rollback 测试，见 §10 |
| **D-30** | 新增 | dense 390-key policy、三集合公式、authority hash 集合、行序非权威 |
| **D-31** | 新增；使 Reader scope contract v1 的 semantic version 失效 | scope contract v2：维度数组 + 多对多证据 + Spec 拥有规范化 |
| **D-32** | 新增；取代 #15 旧稿“disclosure group 必须一次 request” | 合并降级为成本优化规则 |
| **D-33** | 新增 | 三档 publication policy、qualitative strict compatibility、报告兼容规则 |
| **D-34** | 新增 | OPEN_WORLD / CLOSED_WORLD coverage 契约 |
| **D-35** | 新增，独立权威 | InvocationRetryPolicy：orchestrator 层 terminal/retryable 分类与 batch stop |
| **D-36** | 新增，独立权威 | InvocationBudgetPolicy：estimator、双预算、三段计价、usage audit |
| **D-37** | 新增；transfer manifest 将旧 D-20 缓解措施标记为 `SUPERSEDED_BY_NEW_DECISION` | FreshSamplePolicy；保留 D-20 的风险目标，改为按 family 风险分层，见 §8 |
| **D-38** | 新增 | ComplexityPolicy，见 §9 |

**D-07 当前 tip 保持有效**：仍发送全部 table-grid、文档顺序不变、无 semantic prefilter。只有 WB-4 的 measurement receipt 证明 compact 后真实 `prompt_tokens` 仍超预算时，才允许创建一个新的 **D-07 tip**（`decision_id = D-07`，`supersedes_decision_id = 当前 D-07 record hash`）引入 selector；不得用其他 Decision ID 跨链 supersede D-07。

**WB-1 验收**：D-01 与 D-26 的新 tip 分别正确 supersede 各自旧 record hash；D-30～D-38 作为独立 effective decisions 存在；`load_requirement_snapshot` 通过。

---

## 6. 建设块（十块）

### WB-1 Authority Transfer + Frozen Producer Inventory（阻塞其余全部工作）

**`requirements/ai_first_v3_3_1/`** **下不修改任何字节**（其 hash 已写入 42 份 acceptance receipt 与全部历史 Run）。全部新内容进入新目录：

```
requirements/issue_15_v1/
  CONTRACT.md
  transfer_manifest.json
  decision_register.json
  baseline_manifest.json                        parent_requirement_closure_hash → ai_first_v3_3_1
  legacy_semantic_producer_inventory.json       parent_legacy_inventory_sha256 → 旧 legacy_path_inventory.json
  source_strategy_baseline_receipt.json
  foundation_verification_receipt.json
    绑定 foundation commit、tag、merge commit 与 fresh offline verification

```

#### `decision_register.json` 组成规则（自包含历史链）

`requirements/issue_15_v1/decision_register.json` 必须是可由当前 loader **独立解析**的完整快照，而不是只保存新增记录的 delta。`requirements.py::_resolve_decisions` 会按 `decision_id` 分组，并要求每个 `supersedes_decision_id` 指向的 parent record 已存在于同一份 register、同一分组；缺少任一历史 parent 都会触发 `Decision chain has a detached parent`。

- 按父快照原有顺序，原样携带 `ai_first_v3_3_1/decision_register.json` 的全部 **12 条 `decisions` 记录**，以及 `pending_decisions` 中的 D-01 历史根记录。每条旧记录的字段和值不得改写；其 canonical record hash 必须与父快照完全一致。
- D-01 新 tip 追加在当前 DeepSeek effective record `sha256:8e980afbd5a167abf33d4fe9d723d0c7229021f024c976e330dce6f4614471e8` 之后。
- D-26 新 tip 追加在旧 D-26 record `sha256:44a58a5d3bf7bc6c580ab092b343d6d53a64e78ed957914101bcbd8954f4c3d7` 之后。
- D-30～D-38 作为各自 `decision_id` 的新根记录追加。D-03 / D-04 / D-05 / D-06 / D-07 / D-08 / D-24 原样保留，不新增 tip。
- D-01 pending root 继续保留在 `pending_decisions`；它是 D-01 链的历史根，不代表新快照仍被阻塞。解析后的 D-01 effective tip 必须是新 APPROVED 记录，因此 `pending_decision_ids` 必须为空。
- 禁止把任何旧 `supersedes_decision_id` 改为 `null`，禁止删除历史链中间记录，也不为此建设跨快照 parent 解析或通用多版本 Decision 引擎。

**机械验收**：

```text
decision_chains["D-01"] = pending → OpenAI → DeepSeek → D-01 新 tip
decision_chains["D-26"] = 旧 D-26 → D-26 新 tip
effective decision IDs exact set =
  {D-01,D-03,D-04,D-05,D-06,D-07,D-08,D-24,D-26,
   D-30,D-31,D-32,D-33,D-34,D-35,D-36,D-37,D-38}
pending_decision_ids = []
```

producer inventory：

```
{
  "parent_legacy_inventory_sha256": "...",
  "baseline_source_commit": "...",
  "producers": [
    {"producer_id": "scripts/09_extract_mda_and_risk_text.py::going_concern",
     "covered_metric_ids": ["D04"], "kind": "SEMANTIC_PRODUCER"}
  ],
  "producer_exact_set_hash": "sha256:..."
}

```

必须区分 **SEMANTIC\_PRODUCER**（语义抽取/判定，必须退出）与 **SHARED\_PLUMBING**（SEC 下载、HTTP、路径工具，可继续存在）。不得因某函数仍被共享下载逻辑调用就误判 semantic producer 存活；也不得因函数改名就忽略同一语义被复制到另一路径。

**不建** **`config/legacy_retirement_ledger.json`**——迁移状态已由 ReleasePlan 管理，再加一个可变 config ledger 会形成第二套权威。退役证据链为：

```
frozen producer inventory（Requirement 层，不可变）
      ↓ 每档 ReleasePlan.retired_legacy_producer_ids
      ↓ 每档 active bundle 内的 legacy_retirement_receipt.json（publication-bound）
      ↓ 终档 cumulative retired set == frozen inventory exact set

```

同时更新 `AGENTS.md` / `SOP.md` / `TESTING.md` /
`capability_contract.json` 的权威导航。

Foundation transition 已完成（既成事实，WB-1 只验证并绑定，不再执行）：

foundation_source_commit =
f1cc44342e6814522ec2688cf3674f7ec442be8d

foundation_tag =
issue-15-foundation-v1

foundation_merge_commit =
4d02db6a474f93eec9e058d780e206b4504ab24d

PR #14 已作为 inherited implementation foundation 合并入 main；
Issue #12 已关闭为 superseded / not planned。

WB-1 合并前，仍禁止新增 Reader family、修改 production semantics、
创建 active publication、发起付费 provider 调用。

**验收**：新快照可加载；Decision 链如 §5；全仓 `Progress on #12` 命中数 = 0（历史目录除外）；producer inventory 与 baseline receipt 的 set hash 已冻结。

---

### WB-2 SourceStrategy / Reader-family Registry（只描述目标路由）

`config/source_strategy_registry.json`，**不保存任何当前迁移状态**——处于 `ROUTE_INVENTORY_ONLY` / `SHADOW_ONLY` / `MIGRATED_PRODUCTION` 哪一档，唯一由 ReleasePlan 的 `cumulative_metric_ids` 决定。

`forbidden_production_literals` 属于 family 而非单个 metric：

```
{
  "families": {
    "risk_legal_text": {
      "reader_contract_id": "risk_legal_text_v1",
      "forbidden_production_literals": ["going concern", "substantial doubt",
                                        "material weakness", "regulatory investigation"]
    }
  },
  "metrics": {
    "D04": {
      "reader_family_id": "risk_legal_text",
      "source_mode": "structured_first_ai_fallback",
      "structured_route_id": "auditor_report_facts_v1",
      "fallback_trigger_codes": ["STRUCTURED_SOURCE_AMBIGUOUS"],
      "coverage_mode": "CLOSED_WORLD",
      "applicability_rule_id": "all_companies",
      "budget_policy_id": "risk_legal_small",
      "legacy_producer_ids": ["scripts/09_extract_mda_and_risk_text.py::going_concern"]
    }
  }
}

```

`source_mode` ∈ `structured_only` / `structured_first_ai_fallback` / `ai_table` / `ai_text`。（`ai_event_text` 已删除：全部事件指标走确定性路由，见 WB-2B 事件路由表。）

**本块验收**（不含 zero-AI receipt——该证明需 WB-2B + WB-3 到位才可能产生，列入联合验收与最终 Done）：39 条 exact coverage；registry schema 校验通过；合并后 `outputs/metrics_matrix.csv` 的 sha256 **不变**。

---

### WB-2B Deterministic Source Router & Multi-Source Release Plan

现状：`cutover.py::_RELEASE_INPUT_PLAN_FIELDS` 与 `_prepare_live_receipt` 只认 `companyfacts_source` 与 `table_source` 两个槽位。accession XBRL、ECD XBRL、auditor fact、8-K item index **没有位置可放**。缺这一块，39 条 SourceStrategy 写完后大部分 `structured_only` 指标仍只能调用旧 `sec_pipeline.py`——那不算 legacy producer 退出。

**所有 source role 统一使用数组形态**（单源时长度为 1，不引入第二种 shape），并绑定 exact source-set identity：

```
{
  "sources": [
    {"source_role": "companyfacts", "source_mode": "STRUCTURED_JSON",
     "source_reference_ids": ["..."], "source_set_manifest_id": "sha256:..."},
    {"source_role": "target_accession_instance", "source_mode": "ACCESSION_XBRL",
     "source_reference_ids": ["..."], "source_set_manifest_id": "sha256:..."},
    {"source_role": "def14a_ecd", "source_mode": "ECD_XBRL", "...": "..."},
    {"source_role": "auditor_facts", "source_mode": "AUDITOR_FACT", "...": "..."},
    {"source_role": "fy_8k_item_inventory", "source_mode": "ITEM_CODE_INDEX", "...": "..."}
  ]
}

```

`source_set_manifest` 至少绑定：`company_id` / `source_role` / `form_types` / `fiscal_or_date_window` / `discovery_policy` / `sec_submissions_inventory_hash` / `ordered_source_reference_ids` / `cutoff_timestamp_or_pinned_submissions_attempt`。

**这不是通用数据目录，而是让"全年没有 Item 1.03 / 4.02"可证明。** 没有 source-set manifest，任何 coverage proof 都只能证明"检查了给我的文件"，不能证明 release planner 没有漏给一份 8-K。

只建设当前 39 指标需要的五个确定性 adapter：`companyfacts` / `accession_xbrl` / `ecd_xbrl` / `auditor_fact` / `8k_item_index`，统一转成 `SourceReference → deterministic VerifiedObservation | VerifiedClaim → Result/Trace`。

覆盖示例：A01/A02 非普通 companyfacts；C03 走 ECD XBRL；C04 需当期/上期 auditor facts；A09/A13 在进入 AI fallback 前先跑 accession-level dimensional facts。

**事件路由表（全部确定性，零 AI；****`8k_item_index`** **adapter 必须捕获 item briefs——hdr.sgml 主路径 + primary-document heading fallback——而非仅 item code 清单，否则 E01 的关键词门没有输入）**：

```
C01 / E03   同一个 Item 5.02 确定性 Observation，两个 metric 各自投影（不建两个 parser）
            口径保持 legacy：这是「5.02 领导相关事件信号」，不是精确的 CEO/CFO 变动分类；
            将来若需精确分类，新建 metric/observation contract，不得悄悄改变 C01/E03 含义
E02         Item 1.03；零结果必须绑定完整财年 8-K source_set_manifest（CLOSED_WORLD）
E04         Item 4.02；同上
E05         Item 1.01（legacy 明确不抽合同条款）
E01         Item 1.01/2.01 直接命中；
            Item 8.01 走 Spec-owned 声明式关键词规则（aliases 存于 catalog：
            merger / acquisition / combine / transaction，与 legacy
            sec_pipeline.py::_matching_events 的 8.01 keyword gate 逐字对齐）；
            共享 Python 只执行通用声明式匹配，不得出现 if metric_id == "E01"

```

**E01 catalog contract 还必须冻结匹配语义**：`text_normalization` / `match_mode` / `brief_source_priority` 与上述四个 aliases。strict compatibility 必须证明新声明式规则产生的 matched event key set 与 legacy `sec_pipeline.py::_matching_events` 的 matched event key set 逐一相等；不得只比较最终 count。以后增加或修改 alias（例如 `divestiture`）属于显式 Spec 变更，必须重新生成 compatibility evidence。

---

### WB-3 Invocation Control（先于任何新 AI family）

三层身份，扩展现有 `release_input_plan_id`，**不新建平行 CLI、不建数据库服务**：

```
release_input_plan_id   来源集合、公司、目标期间、result keys、Spec closure、authority hashes
ai_invocation_plan_id   task_contract_hash + output_schema_hash + serialization_version
                        + model + estimator + budget + provider_request_body_sha256
execution_id            一次明确授权的执行；其下是不可变 attempt 序列

```

**两种身份不得混用**：

```
付费 response 复用与 single-flight 身份
  = provider_request_body_sha256 + provider + model + api
  （system prompt 或 provider envelope 变化时，task contract hash 不一定捕捉得到）

semantic_invocation_id（qualification / stability 分组身份）
  = source + selected_representation + task_contract_hash
    + output_schema_hash + serialization_version + model，其下记录 sample_ordinal

```

**Reservation 必须是真正的互斥。**`canonical.py::atomic_write_bytes` 用 `os.replace`，两个进程都会成功、都会付费。必须使用 `O_CREAT | O_EXCL` 或与 publication 相同的独占锁 + CAS。

```
不变量：只有成功创建 reservation 的 execution owner 才能打开 provider socket。
        reservation 已存在时，其他 execution 必须在 request bytes 构造完成后、
        socket 打开前失败。

Reservation record 至少保存：
  execution_id / owner_token / reserved_at / egress_started_at（可空）/ attempt_ordinal

```

**Attempt 不可变，execution 汇总**（不得原地把失败改成成功）：

```
execution_id
  attempt_1 = FAILED_RETRYABLE      ← 不可变记录，永久保留
  attempt_2 = SUCCEEDED | FAILED_TERMINAL | FAILED_RETRYABLE_FINAL

```

**崩溃窗口（必须显式建模，否则清 stale lock 重跑会重复付费）**：

```
ABANDONED_BEFORE_EGRESS
  egress_started_at 为空，已机械证明 socket 未打开
  → 允许同 execution 恢复或新建 execution

UNKNOWN_REMOTE_OUTCOME
  egress_started_at 非空但无完整 terminal attempt receipt
  → 禁止自动重试；batch 终止；需人工与 provider request 记录核对

```

**错误矩阵（D-35）**：

```
400 / 401 / 402 / 422 / schema violation / evidence failure / budget exceeded → terminal
429 / timeout / 可恢复 5xx                                                     → 至多一次重试
terminal → 终止当前 execution → 终止整个 batch
        → 不继续后续 attempt 与 stability ordinal → previous active 不变
余额恢复后 operator 可显式创建新 execution，仍引用同一 immutable invocation plan。

```

**必须修复**：`cutover.py::_prepare_runs` 现为 `3 stability × (retry_count + 2) attempts`＝单公司最多 12 次付费 attempt，失败分支 `continue` 不检查 error\_class。改错误码名无效，必须改这个循环。

**预算与计价（D-36）**：`estimator_id/version`、`serialization_version`、`pricing_snapshot_hash`、per-call 与 batch 双预算，价格快照**必须三段分列**（成本基线本身就是按 cache 命中区分的）：

```
cache_hit_input_price_per_million
cache_miss_input_price_per_million
output_price_per_million

```

**验收（可机检）**：并发两个相同 plan → 实际网络调用 = 1；模拟 402 → 实际调用 = 1 且 batch 立即终止；budget preflight 失败 → 调用 = 0；已有成功 exact response 时 resume → 调用 = 0；注入 egress 后崩溃 → 状态为 `UNKNOWN_REMOTE_OUTCOME` 且不自动重试。

---

### WB-4 Compact Table Transport（保留 D-07）

```
expanded grid   = 本地 Evidence Authority（不变）
compact payload = AI transport representation（新增）

```

去掉 non-origin 展开 cell 与 synthetic blank cell、使用紧凑字段名，**全部表格与文档顺序不变**。

**必然触及**：`table_grid.py`（expanded 权威保留）、`reader_input.py::build_reader_payload`（encoder）、新 decoder、`ai_adapter.py` 的逐表字段校验、`evidence.py::_verify_payload`（由 `payload == derived_asset["tables"]` 改为 `decode(payload) == derived_asset["tables"]`）、attempt audit（同时绑定 expanded 与 compact identity）、fixtures、qualification。`render.py` 的 review renderer 继续读 expanded grid，不受影响。

新增绑定：`table_payload_serialization_version` / `expanded_derived_asset_id` / `expanded_grid_sha256` / `compact_payload_sha256` / `decoder_semantic_version` / `round_trip_receipt_id`。

**硬门禁**：`decode(encode(expanded_grid)) == expanded_grid`，**逐字段相等**（table\_id / order / caption / caption\_raw\_text / row\_count / column\_count / row\_index / column\_index / origin\_row\_index / origin\_column\_index / rowspan / colspan / header / is\_origin / raw\_text / text），在 Marriott production source、Hilton 全部 7 个布局、Hyatt 全部 3 个 holdout 上成立。

**离线测算参考（非承诺值）**：1,505,424 B → 79,878 B；加 overhead 8,355 B ≈ 88 KB；按实测 3.2 B/token 约 27.6k tokens，按保守 2.0 B/token 约 44k tokens。实际值以本块 measurement receipt 为准，receipt 必须分列 `expanded_reader_payload_bytes` / `compact_reader_payload_bytes` / `provider_envelope_bytes` / `estimated_input_tokens` / `actual_prompt_tokens`。

---

### WB-5 Generic Scope（D-31）

`ai_adapter.py` 的 `_SCOPE_SCHEMA` 现为硬编码酒店口径 `{property_population, operating_scope, geography}`，required 全部、`additionalProperties: false`。A04 的 `tax_equivalent_basis`、A12 的 `confidence_level` / `holding_period` 无法表达。

**模型只主张 raw，不提供 canonical。** 让模型既找值、又声称语义、又自报规范化结果、再被自动批准，等于把第二次主张当成机械证据。

```
"claimed_scope": [
  {"dimension": "confidence_level", "raw_value": "99%",     "evidence_locator_ids": ["e1"]},
  {"dimension": "holding_period",   "raw_value": "one day", "evidence_locator_ids": ["e1"]}
],
"scope_evidence_locators": [
  {"id": "e1", "supports_dimensions": ["confidence_level", "holding_period"],
   "location_type": "header", "locator": {...}, "text": "99% one-day VaR"}
]

```

Spec 声明 **scope\_contract**：`required_dimensions` / `allowed_dimensions` / 每维度的 exact\_enum alias 表 / `selection_preference` / `cross_dimension_constraints`（合法组合）。

Evidence Checker（**只有 exact\_enum alias 一种规范化机制**；percent\_to\_ratio / integer\_days / decimal / raw\_text 自动审批均已删除——scope 值从不参与 Calculator 算术，只做身份/守门，当前 39 指标的 scope 全为有限集合）：

```
1. 从 locator 机械重取 raw_value
2. 查 Spec 声明的 alias 表（如 "99%" / "99 percent" → "99_percent"）
3. 命中 alias → canonical enum → 生成 normalized_scope
4. 未命中 → 该 candidate 走 HUMAN review，不自动猜测
5. 不接受模型自报的 canonical value

```

**判定条件是** **`normalized_scope satisfies Spec scope_contract`****，不是等于某个预先写死的 scope**（VaR 的 confidence\_level 可能是 99% 或 95%，holding\_period 可能是 1day 或 10days）。仅当 Spec 明确声明 exact expected scope 时才要求完全相等。

**SYSTEM approval 的边界**：

```
可机械审批：required dimensions 全部存在；raw value 全部机械重取成功；
            canonical value 全部由 exact_enum alias 命中；
            normalized_scope satisfies scope_contract；无 unresolved / competing claims

任何 alias 未命中的维度 → 该 candidate 必须走 HUMAN；不存在其他自动规范化路径

```

**状态归属不得混淆**（`records.py` 对 VerifiedObservation 断言 `quality ∈ {EXACT, APPROX}`）：

```
Candidate.status = REVIEW_REQUIRED   ← 尚未审核，不生成 VerifiedObservation
        ↓ HUMAN APPROVE
VerifiedObservation.quality = EXACT | APPROX   ← 审核后的业务质量
不得给 quality enum 新增 REVIEW_REQUIRED。

```

**连带改动（不得遗漏）**：candidate hash、Evidence normalized scope、`render.py` review renderer、`records.py` 的 `required_claims` 比对、SYSTEM approval gate、`observations.py::reviewed_observation`（`scope = decision["approved_claims"]`）、VerifiedObservation `scope_key`、compatibility receipt。

---

### WB-6 Single-table Task Contracts（无 runtime planner，无 selector）

`reader.py::validate_reader_output` 要求 selected / competing / scope\_evidence 的全部 locator 留在根 `table_locator` 的同一张表内——这是 Evidence Checker 机械重取紧致性的基础（INV-03）。**保留。**

`reader_input.py::build_reader_task_contract` 完全由 `catalog/disclosures/*.md` 驱动：

```
不要：financial_table = {A03 LCR, A04 NIM, A11 AUM, A12 VaR}
而是：financial_lcr_table / financial_nim_table / financial_aum_table / financial_var_table
每个请求仍接收完整 compact table set，由模型自行选定目标表。
qualification 证明两个 role 稳定共表后，才允许合并进同一 contract。

```

**门禁表述**：新增或拆分一个 single-table task contract，**不得新增 family-specific production Python**。（本块依赖 WB-2B / WB-3 先支持"一家公司执行多个 task contract"，因此不宣称"零 Python"。）

**D-32**：合并是成本优化规则，不是 correctness invariant。合并条件为「同一 source、同一 period、同一 target table、review contract 兼容」。拆分时记录 `split_reason` / `estimated_incremental_tokens` / `actual_incremental_tokens`。

---

### WB-7 Section/Span DerivedAsset

只支持当前 39 指标需要的边界：10-K Item sections、notes、auditor report、DEF 14A sections、8-K Item 正文。

**坐标空间现在就定死，不留给实现者**：

```
offset_coordinate_space = UTF-8 byte offsets over canonical normalized section text

RawBlob (HTML)
   ↓ text_transform_version
SectionSpan DerivedAsset
   canonical_normalized_utf8_text
   derived_text_start_byte / derived_text_end_byte
   parent_raw_asset_id
   section_identity
   content_hash

```

理由：raw HTML offset 受标签、HTML entity、嵌套节点影响；字符索引受 Unicode 实现差异影响；规范化文本上的 UTF-8 byte offset 可稳定重取；RawBlob 仍通过 parent binding 保留原始来源；与 table-grid「原始文件 → 内容寻址 DerivedAsset」模式一致。

字段名使用 `derived_text_start_byte` / `derived_text_end_byte`，**不使用** **`source_offsets`**（后者会被误读为直接定位原始 HTML 字节）。

**不做**：通用搜索引擎、知识库、语义索引服务。

---

### WB-8 VERIFIED\_CLAIM（TEXT，仅内部记录，无公开 claims artifact）

```
VERIFIED_OBSERVATION   record type 本身隐含 NUMERIC；**不新增任何字段**
                       （新增 claim_kind 会改变历史 record schema、hash 与全部历史 Run）
VERIFIED_CLAIM（新）   claim_kind = TEXT（**唯一取值；COLLECTION 已删除**）
                       共用同一 Run / Review / Publication 主状态机

```

`TEXT`：`claim_id` / `claim_type` / `polarity` / `classification` / `statement` / `source_span_ids` / `section_identity` / `content_hash`。**COLLECTION（items[] / item\_identity / ORDERED|SET / duplicate\_policy / 逐 item hash）整体删除**——事件走 WB-2B 确定性路由后，其唯一客户是 C02，而 C02 的 legacy 口径本就是 `TEXT_QUAL` 引述段落，从未有结构化名册。将来若需完整董事名单、逐人独立性标记、委员会结构或年度 diff，作为产品升级新建 metric/observation contract，不借迁移顺手实现。

**claim 保持 Run 内 content-addressed（不可压成字符串）**——这保住 Review 绑定、replay 与 span 机械重取；**删除的只是公开层**：不新增 `outputs/metric_claims.jsonl`，不建 claim-backed report template，不引入 template semantic version。

```
VERIFIED_CLAIM.claim_id
      ↓ EXECUTION_TRACE.input_claim_ids
      ↓ METRIC_RESULT（qualitative 时 value = null, unit = null, quality = EXACT）
      ↓ ProjectionManifest.claim_bindings（绑定 evidence row hashes）
      ↓ 投影进现有 artifact：metrics_matrix.csv 的 status/notes 与
        metric_evidence.csv 的 evidence_quote / span 摘要
公开层文件集合不变；REPORT 继续从现有 CSV 渲染，不得重读 filing、不得调用 AI。

```

**删除公开 claims artifact 不得削弱 immutable read-back**：Publication validation 与 committed bundle 的 immutable read-back 必须从 BatchManifest 绑定的 exact FROZEN Run 解析每个 `claim_id`，重新验证 Claim → Trace → Result → Projection → evidence row hash 的完整链。任一 Claim 缺失、被篡改或绑定不一致时，candidate 不得 commit；对已提交 bundle 的 read-back 也必须 fail closed。

> **合同注解**：qualitative result 的 `quality = EXACT` 表示 claim、source span、Review 与 projection 的绑定完全一致，**不表示自然语言判断不存在认识论不确定性**。此约定用于避免新增 quality enum。

**qualitative strict compatibility（D-33）**：

```
metrics_matrix.csv / metric_evidence.csv 旧行默认 exact；
若某指标需改变 root CSV 的 status / notes / value / metric_name，
必须在该 MetricSpec 中逐字段列出 approved delta，
不得由统一的 MIGRATED_PRODUCTION 状态自动放行。

```

**B12 特别约束**：现有 B12 行是 RPO/cRPO 替代观测，不等于 ARR。ARR / churn / NRR 若进入产品必须新建 metric ID 或独立 observation contract；未经方法论 Decision 不得改变 B12 legacy projection。

---

### WB-9 Closed-world Coverage（D-34；作为 EVIDENCE\_CHECK 子结构，不建独立 artifact）

```
OPEN_WORLD    正向存在性事实 → exact span/locator 即可
CLOSED_WORLD  absence、完整计数、全章节摘要 → coverage proof 必须 COMPLETE

```

CLOSED\_WORLD 覆盖：D02/D03/D04 的"无"、E01–E05 的全年无事件结论、D01"Item 1A 主要风险主题摘要"。

**不建独立** **`CoverageReceipt.json`** **artifact / record type**；coverage proof 作为 `EVIDENCE_CHECK` 的 content-addressed 子结构保留，且必须到 **section 级**（source-role 级不够——"看过这份 10-K"不能证明"看过 Item 3 + contingency notes + 审计报告"）：

```
required_source_set_manifest_ids
required_sections
examined_section_ids
examined_span_set_hash
unexamined_required_sections
coverage_complete
planner_version

```

**`coverage_complete`** **只能由本地确定性 planner 计算，模型不得自报**；`required ⊆ examined` 不成立 → WITHHELD。事件类（E02/E04 等）的 coverage 由 WB-2B 的 source\_set\_manifest 承担（完整财年 8-K 集合即其 required set）。

**`NOT_FOUND_IN_SELECTED_SLICES`** **语义写死**：

```
publication = WITHHELD
reason_code = COVERAGE_INCOMPLETE
不得进入 MIGRATED_PRODUCTION active candidate；可保留在 SHADOW_ONLY audit 中
CLOSED_WORLD family 的 coverage 无法 COMPLETE
  → 不能进入下一档 cumulative migrated set → previous active 保持不变

```

---

## 7. Ratchet 交付模型

排序依据 §2 切分 A：**先做零 AI、退役 legacy producer 最多的部分。**（事件指标经 WB-2B 确定性路由后不再有独立 AI 档；原 R7 取消。）

```
R0  frozen verified legacy root baseline
    无 committed active pointer；仅作为首次 Cutover 的 predecessor A 来源

R1  B01 / B03（MetricSpec 已存在，只需 companyfacts）
    首次 cold-start transaction：
      1. 导入并提交 verified legacy predecessor A
      2. 提交 B01/B03 successor B
      3. active = B
      4. rollback → A
      5. restore → B
    **本档 provider call count 必须为 0**

R2  其余 14 个 DET_ONLY 指标 + 全部事件指标 C01 / E01–E05
    依赖 WB-2B；零 AI、零 qualification、零预算风险
    R1+R2 合计 141 行（61%）在第一次付费调用之前完成迁移
    （其中 E01 = item code + 声明式关键词规则，不是纯 item code）

R3  lodging B10/B11 + ADR       compact transport + generic scope 下重新 qualification
R4  financial table             A03 A04 A09 A11 A12 A13
R5  其余 table 与混合            B06 B13 C03 C04
R6  governance / risk / legal   C02 D01 D02 D03 D04（TEXT）
Rf  39 指标全部迁移 + legacy producer 清零

每档 ReleasePlan 记录：`release_plan_id` / `parent_release_plan_id` / `added_metric_ids` / `cumulative_metric_ids` / `cumulative_vnext_result_keys` / `retired_legacy_producer_ids` / `reader_family_versions` / `requirement_closure_hash` / §4 的全部 authority hash。

**机械门禁**：`cumulative(Rn) ⊇ cumulative(Rn-1)`；removed keys = 0；removed metric IDs = 0。

**失败行为（无 per-metric demotion）**：

```

新 family qualification 失败       → 不生成 Rn → Rn-1 保持 active（迁移前 QUARANTINED） APPLICABLE migrated 出现 WITHHELD  → Rn 不 commit → previous active 不变 Rn 已 commit 后发现系统级故障      → 整包回滚到 Rn-1 → 修复后 restore Rn

```
**已知代价并接受**：commit 后单指标失败只能整包回滚，会连带丢失同档其他指标的新鲜数据。**不为此建 partial publication 机制**，写入运维文档。

**rollback/restore 演练（D-26 新 tip）**：R1、Rf、以及任何改动 publication schema / CAS / pointer / recovery 逻辑的档**必做**完整 `active → rollback → restore`；纯增 Reader/MetricSpec 的档只做 active terminal validation + predecessor pointer 可用性证明。

---

## 8. Qualification 制度

`config/qualification_matrix.json`，每个 Reader family 在开发前冻结：


```

family\_id / reader\_contract\_id development source        (company / CIK / accession / document) second\_layout\_required    由风险分级决定，不做 table/text 一刀切： 必须 second layout + holdout —— ai\_table 主路径； CLOSED\_WORLD 文本结论（D01 摘要、D04 无持续经营疑虑）； 布局差异大的文本源（C02 DEF 14A）； 任何人工难以发现漏项且直接进 production 的 family 可只做 post-freeze holdout —— 低频 structured fallback； OPEN\_WORLD 正向存在性分类； 失败只导致 WITHHELD、不形成 absence 结论的 family second\_layout source      materially different 的判定必须写成可核对条件 post\_freeze\_holdout source expected claim set / expected locator range / expected output status coverage expectation      CLOSED\_WORLD 需正负两个 fixture fresh\_samples\_required max\_estimated\_tokens / max\_actual\_tokens / max\_cost review policy / negative cases

```

acquisition 清单由该矩阵派生，**不预先拍公司数量**。已知约束：registry 9 个 profile 各 1 家公司（manufacturing 2 家），因此 financial 等 family 的 holdout 必然来自 registry 外。**复用优先**：§3 的 INHERITED_REUSABLE_EVIDENCE 允许直接复用已有 SEC raw bytes 与 acquisition receipt。

**D-37 FreshSamplePolicy**：

```

lodging          继承 D-20 的 3 次 fresh stability（除非新 Decision 显式修改） 新 Reader family 默认 fresh\_samples\_required = 1 泛化证据由 second layout + post-freeze holdout + 本地 Evidence 重取承担 高歧义 / 高风险  qualification\_matrix 可显式提高到 2 或 3 全局 model nondeterminism receipt 可保存，只作补充观测，不替代 family qualification

```

**qualification 失效由 dependency closure 决定**：serialization / scope contract / task contract / prompt / schema 变更 → 该 family 失效；无关 family 不失效；不影响 payload/schema/selection 的渲染层变更不强制重新付费。

**resume 与 stability 的复用规则**：

```

普通 resume        已有成功 exact response（按 provider\_request\_body\_sha256 身份）→ 复用，不重新付费 D-20 stability     计划中显式授权 N 个 fresh ordinal，每个 ordinal 只能成功一次； 进程中断后复用已完成 ordinal，只执行缺失的

```

---

## 9. 复杂度门禁（D-38）

**Blocking gates**：

```

G-1  新增同 family 的一个指标        shared Python 改动 = 0 G-3  新增一个已支持布局的公司        production Python 改动 = 0 G-5  终档 scripts/vnext/\*.py 中 business literal 命中数 = 0 （词表 = 全部 family 的 forbidden\_production\_literals 并集） G-6  AST 检查（客观可机判部分），对显式声明的 shared module 集合生效： 不得出现 if metric\_id == "..." / company literal / 固定 table\_id

```

**G-6(b)（blocking code review，非 AST）**：新 family 不得要求在共享 Reader / Evidence / Projector 中加入本 family 专用 if/elif 分支——"某个分支是否 family-specific"需要业务语义判断（`if coverage_mode == "CLOSED_WORLD"` 可能合法也可能是变相特判），AST 无法可靠区分，故此条为 blocking 人工审查项，并以每档 family-specific branch delta 作为 audit metric 记录。

**Audit metrics（记录但不 blocking，因文件数与分支数均可被规避或主观化）**：`shared-engine file diff count per new family`、`family-specific branch delta per ratchet`。

**semantic lint 升级**：`tools/check_vnext_semantics.py` 的 `BUSINESS_LITERAL_PATTERN` 现只覆盖 lodging 词与 b01/b03/b10/b11。改为从 registry 的 per-family `forbidden_production_literals` 派生。**不得把 risk / value / event / income / current 这类通用词加入词表。** catalog / fixtures / tests 允许出现，生产代码不允许。

---

## 10. 测试政策（D-26 新 tip）

保留"不要求全仓回归、隔离 worktree、长串行套件"。但下列不变量必须有短小、确定性、直接的测试：


```

semantic freeze 后 mutation 被拒绝 FROZEN Run replay 的网络调用数 = 0 rollback / restore 的网络调用数 = 0 两个并发相同 plan 最多一个取得 reservation（真实互斥，非原子替换） egress 后崩溃 → UNKNOWN\_REMOTE\_OUTCOME 且不自动重试 402 场景下实际调用数 = 1 且 batch 立即终止 budget preflight 失败时实际调用数 = 0 decode(encode(expanded\_grid)) == expanded\_grid 逐字段相等 public key set == frozen\_legacy\_key\_set ∪ vNext\_result\_key\_set new public keys 全部为 N\_A\_STRUCTURAL structured\_only 指标 provider call count = 0 EVIDENCE\_CHECK 的 coverage 子结构不完整时 publication = WITHHELD alias 未命中的 scope 维度不产生 SYSTEM approval（必走 HUMAN）
Publication validation / immutable read-back 从 BatchManifest 绑定的 exact FROZEN Run 重验全部 claim_id；Claim 缺失、篡改或绑定不一致时 fail closed

```

---

## 11. 执行顺序


```

WB-1 Authority Transfer + frozen inventory + baseline receipt   ← 阻塞一切 │  当前 main 已包含 PR #14 inherited foundation │ └─ 并行：离线 measurement spike 本地 encode/decode + 逐字段 round-trip + 字节测量 + 用已有 provider usage 校准的 bytes/token 估算 + recorded replay 【禁止任何付费调用】 ↓ WB-2 Registry ── WB-2B Deterministic Source Router ── WB-3 Invocation Control ↓ R1（B01/B03）cold-start：predecessor A → active B → rollback → restore provider call count = 0 ↓ R2（其余 14 个 DET\_ONLY 指标 + C01/E01–E05 事件路由，零 AI） ↓ WB-4 Compact Transport ── WB-5 Generic Scope ── WB-6 Single-table Contracts ↓ serializer / scope / task contract 冻结 ↓ 第一条真实付费调用 （直接作为新契约下的 qualification evidence，不是用完即废的 measurement call） ↓ R3 lodging → R4 financial ↓ WB-7 Section/Span ── WB-8 VERIFIED\_CLAIM(TEXT) ── WB-9 Coverage 子结构 ↓ R5 → R6 → Rf

```

---

## 12. 明确不做

`ai_event_text` source mode 与任何 Event AI Reader family（事件全部走 WB-2B 确定性路由）；COLLECTION claim 类型（结构化董事名册 / 事件对象明细属于产品升级，另开 issue）；`outputs/metric_claims.jsonl` 及任何新公开 claims artifact；claim-backed report template 与 template semantic version；percent_to_ratio / integer_days / decimal / raw_text 自动规范化（scope 只有 exact_enum aliases）；candidate-table selector（除非 WB-4 实测仍超预算，届时仅允许创建新的 D-07 tip 显式 supersede 当前 D-07）；per-role locator / 多表响应；per-family scope schema 生成器；per-metric demotion；partial publication；终档行序重排；跨 ID supersede 的 Decision 引擎改造；可变的 `config/legacy_retirement_ledger.json`；通用多版本 Requirement 平台；平行的 plan/execute CLI；provider billing 财务级对账平台；通用文本搜索或知识库；新的 quality enum；为未来未知指标预留的抽象层。

---

## 13. 最终 Done


```

[ ] 39 个 metric ID 全部进入 cumulative migrated set [ ] vNext result key set = 390，与 registry × final\_metric\_ids 的公式派生值一致 [ ] public matrix key set = frozen\_legacy\_key\_set ∪ vNext\_result\_key\_set = 390 [ ] 相对 frozen legacy 的全部 new public keys 均为 N\_A\_STRUCTURAL [ ] 每档 ReleasePlan 的 authority hash 集合完整且一致 [ ] quarantined\_metric\_ids = []，demoted\_metric\_ids 字段不存在 [ ] structured\_only 指标 provider call count = 0（机器证明） [ ] 全部 APPLICABLE AI 结果通过 Evidence 机械重取与 Review [ ] 全部 CLOSED\_WORLD 结论的 EVIDENCE\_CHECK coverage 子结构为 COMPLETE （section 级 required ⊆ examined，planner 计算）； 无 NOT\_FOUND\_IN\_SELECTED\_SLICES 进入 active [ ] 所有 qualitative Result 绑定 content-addressed VERIFIED\_CLAIM(TEXT)； root 公开文件集合不变（无新增 claims artifact），REPORT 从现有 CSV 渲染 [ ] Publication validation 与 immutable read-back 可从 BatchManifest 绑定的 exact FROZEN Run 重验全部 claim_id；无 Claim 缺失、篡改或绑定不一致 [ ] final legacy\_retirement\_receipt 的 producer exact set == WB-1 冻结的 producer\_exact\_set\_hash，且全部 status = PRODUCTION\_UNREACHABLE [ ] 复杂度 blocking gates G-1 / G-3 / G-5 / G-6(a-AST) 全部通过；G-6(b) 经 blocking code review [ ] root CSV / evidence / report 全部等于最终 active bundle [ ] final active → rollback → restore 真实完成 [ ] 以下命令返回 0，final receipt status = PASSED，active pointer = restored final publication：

```
python3 tools/run_acceptance.py --scope full --execute-live

```

```

**只有以上全部满足时，Issue #15 关闭。**

```
