# 0. 合同继承与权威顺序

本 Issue 当前正文是 **Contract Revision R3 Addendum（正式 Cutover 增补合同）**，**不是对原 R2 的删减替代版**。

原 R2 的 exact、不可变全文继续完整有效：

- immutable source：[`requirements/ai_first_v3_3_1/ISSUE_CONTRACT.md@a77b9055`](https://github.com/wlvh/SEC_metrics/blob/a77b9055a53de5e5808649551f03fe567cb2de0a/requirements/ai_first_v3_3_1/ISSUE_CONTRACT.md)
- frozen `issue_body_sha256`：`a0c6f48c5df4f86a98d5615497477e85cbbdffaaf84ef35a97c805fa65a1e43a`
- FSD SHA-256：`1cf091812629648095119692c1742d12015e1012ccabf2173820e585e1d42b2b`
- baseline：`requirements/ai_first_v3_3_1/baseline_manifest.json`

**R2 中凡未被本 R3 第 2 节逐项明确 supersede 的条款，全部继续具有规范效力。** 特别是以下内容没有被删除、放宽或降级：

1. R2 §0 的 12 条代码事实基线；
2. R2 §1 的职责边界与八项目标；
3. R2 §2 完整 Scope 与 Non-goals；
4. R2 §3.1–§3.12 的 Requirement、RawBlob/SourceReference、全部 table-grid、AI attempt、canonical/Decimal、MetricSpec DSL、Evidence、ReviewUnit、状态模型、METH-01、Legacy Projection、Publication、Cutover/replay 全部精确约束；
5. R2 SU-00～SU-11：SU 仍是实施与验收边界，不因允许一个 PR 完成而消失；
6. R2 Target State Bridge、代码触点、文档矩阵、测试矩阵；
7. R2 AC-01～AC-28 与 §9 Acceptance Checklist；
8. R2 D-01～D-25 风险/裁决及关闭说明模板。

规范优先级固定为：

```text
当前代码事实与冻结 baseline
→ exact FSD
→ exact R2 ISSUE_CONTRACT
→ 本 R3 中明确列出的 superseding decisions
→ decision_register.json 中后续有效单链决定
→ PR 实现
```

Issue 评论不是 Requirement truth；评论区不承载额外要求。Fresh-context Agent/审核者按以下顺序读取：

1. `AGENTS.md`；
2. 本 Issue R3 正文；
3. 上述 immutable R2 `ISSUE_CONTRACT.md`；
4. `decision_register.json`、`baseline_manifest.json`；
5. 本正文和 R2 明确引用的代码、测试与文档。

---

# 1. 当前基线：PR #13 与 UX 验收

PR #13 已合并：

- PR head：`3618306a896ceb3d1c0cbfc9e523cf73fd11d25f`
- merge commit：`a77b9055a53de5e5808649551f03fe567cb2de0a`
- tested tree：`c023571102669eecdaf38aff7c0cd66488ed3ba6`

PR #13 已完成并保留的 recorded/shadow 基础：

- Requirement Snapshot、Decision chain、canonical JSON、Decimal、独立状态和 semantic identities；
- B01/B03/B10/B11 MetricSpec、有限 DSL、generic Calculator、ExecutionTrace；
- RawBlob/SourceReference、metric-neutral 全表 table-grid、ReaderInputManifest、recorded AI adapter；
- wrong-cell / wrong-locator 不自动修正、不全文找答案、不回退旧 resolver；
- Evidence Checker、安全 renderer、whole ReviewUnit、Decision 单链、TOCTOU；
- OPEN/FROZEN Run、freeze、无 AI replay；
- scoped complete BatchManifest、Legacy Projector、B03 evidence reconciliation；
- immutable bundle、active pointer、CAS、pinned PublicationView、并发和 recovery 原语；
- recorded acceptance 可得到 `PASSED_RECORDED_ONLY`。

2026-08-06 fresh-context UAT 的正式结论：

- recorded R 级机制：`PASS`；
- recorded UX：`FAIL`；
- Issue #12：继续 `OPEN`；
- UAT-03：缺受支持的 OPEN Run/operator end-to-end 入口；
- UAT-05：Review CLI fail closed，但错误诊断和恢复不可用；
- UAT-09：缺 mixed-fiscal-year 专门动态负例；
- UAT-10：缺 mid-bundle/mid-mirror write fault injection；
- 第二真实布局、post-freeze holdout、remote live 三轮、十公司 staging、旧路径退出、active Cutover、真实 rollback/full 均未完成。

当前 root Stage 00–12 与 root CSV/报告仍是 legacy active。本 Issue 完成后这一事实必须改变。

---

# 2. R3 仅有的显式 superseding decisions

除本节外，R2 全部条款原样保留。

## R3-D1｜允许一个分支、一个 PR 完成全部剩余工作

R2 的 SU-00～SU-11 继续作为验收边界，但**不强制拆成多个 PR**。允许一个开发分支、一个 Draft PR、多个 commits，一次完成 recorded UX、live、staging、Cutover、旧路径退出和 rollback。

开发期间 PR 写 `Progress on #12`；只有 R2 + R3 全部 Done gate 真实通过后，才可写 `Closes #12`。

## R3-D2｜唯一产品终态是正式 vNext Cutover

> vNext 成为 B01 / B03 / B10 / B11 的唯一正式 producer；业务用户继续读取现有 CSV/报告；迁移指标与冻结 baseline 保持 R2 规定的 strict compatibility；旧 lodging/B03 production path 退出；发布具备 failure protection、rollback、replay 和完整审计闭环。

PR 不得以“recorded demo 完成”“shadow primitives 完成”或“代码已合并”代替 Cutover Done。

## R3-D3｜D-01 从 pending 改为已批准的 OpenAI remote policy

实现时必须在 `decision_register.json` 中以**新的 superseding decision record**关闭 D-01，不得篡改历史记录。批准选择为：

```json
{
  "provider": "openai",
  "model": "gpt-5.6-terra",
  "api": "responses",
  "endpoint_host": "api.openai.com",
  "region": "provider-managed-global-no-residency-guarantee",
  "retention": "default abuse-monitoring up to 30 days; responses store=false; no ZDR claim",
  "data_use": "not used for training by default; no opt-in sharing",
  "timeout_seconds": 120,
  "retry_count": 2,
  "maximum_payload_bytes": 8388608,
  "filing_egress_policy": "PUBLIC_SEC_FILING_TABLE_GRIDS_ONLY"
}
```

实现要求：

- API key 只读 `OPENAI_API_KEY`；
- 只允许 `api.openai.com`；
- Responses request 显式 `store=false`；
- 使用严格 Structured Output；
- exact outbound body、schema、provider-returned model identity、raw response 和 `TransportObservation` 内容寻址留痕；
- Authorization/header secret、环境变量、本地绝对路径、Git 凭据不得落盘或外发；
- 不启用 web search、file upload、background mode、Code Interpreter、hosted shell、MCP 或其他工具；
- 只发送公开 SEC filing 的全部 table-grid、Spec-derived task contract 与必要公开 metadata；
- 不自动 fallback 到其他模型、旧 resolver 或 caller-supplied transport；
- R2 §3.2、§3.3、§3.6、D-07、D-24 的全部安全与 authority 约束继续有效。

## R3-D4｜SEC identity 决定

- `organization = "axaxl"`；
- contact email 只从 `SEC_CONTACT_EMAIL` 读取；
- 不在仓库硬编码、猜测或伪造第三方邮箱；
- live/full 必须使用真实可联系、非 example/reserved-domain 邮箱；
- 缺失时明确失败 `SEC_CONTACT_EMAIL_REQUIRED`。

这关闭“organization 选什么”的产品决定，不免除 SEC 的可联系邮箱要求。

## R3-D5｜Stage 00–11 属于内部实现自由，但不能删除不变量

Agent 可保留 wrapper、增加统一 orchestrator或重组内部调用，但必须：

- 保留所有非迁移能力和 R2 acceptance surface；
- 不通过删 stage、删 check、缩小 artifact closure 来制造 PASS；
- 对每个旧 lodging producer/check 保留 invariant migration proof；
- Stage 10/11/12、report、snapshot checker 最终读取同一 pinned active PublicationView。

正式入口必须存在：

```bash
python3 tools/run_acceptance.py --scope full --execute-live
```

该命令必须真实执行完整 live batch、vNext staging、Cutover 后验证、rollback/restore 和 final receipt；不能永久把 Stage 00–11 记录为 `NOT_RUN`。`--scope recorded` 继续保持 socket=0。

## R3-D6｜第二布局与 holdout 由 Agent 选择

Agent 从公开 SEC 10-K 自主选择：

- 一个 materially different 的第二 lodging 布局；
- 一个主实现冻结后才加入的独立 holdout。

仍必须满足 R2 D-21 / AC-21：保存最小真实 excerpt 和 accession/source identity；不加入正式十公司 registry；至少两种布局差异；holdout 加入后不得修改 production semantic source，只能增加 fixture、recorded locator/response 和测试。

## R3-D7｜新增 UX 与故障注入验收，不取代原 AC

新增且必须动态通过：

- cold-start operator 不读源码/tests，可完成 recorded end-to-end；
- Review list/show/decide、稳定业务错误码、effective tip、恢复命令、默认无 traceback、`--json`；
- mixed-fiscal-year BatchManifest 负例；
- mid-bundle-write fault；
- mid-mirror-write fault；
- mirrors-written-before-pointer recovery。

这些是 R2 AC 的增补，不会删除或替代任何原 AC。

---

# 3. 用户可见 Done 与 strict compatibility

业务用户继续读取：

```text
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
outputs/coverage_matrix.csv
REPORT_十公司财务指标.md
outputs/validation_run_manifest.json
```

不得要求业务用户从 `artifacts/vnext/` 手工挑 Run。

## 3.1 `metrics_matrix.csv`

完整执行 R2 §3.10，不只比较 value：

- current registry × `[B01, B03, B10, B11]` exact set；
- B01/B03 全部字段 exact parity；
- B10/B11 的业务/兼容字段（含空值）exact parity：

```text
company, cik, metric_id, metric_name, value, unit, status, source_class,
period_start, period_end, fiscal_year, fiscal_period, accession, form,
filed_date, concept_or_section, context_or_dimension, confidence
```

- B10/B11 `confidence=0.85` 仅作为 Phase 1 compatibility constant，不解释为模型 confidence；
- `formula/notes` 可以按 R2 做 versioned declarative delta，必须逐 cell receipt；
- non-lodging B10/B11 为 durable `N_A_STRUCTURAL`，不得缺行；
- 非迁移 rows 的 key/value/unit/status/order 与 R2 要求一致；
- 如新路径与 baseline value 不一致，默认阻塞 Cutover；本 PR 不顺手改业务值，除非新增显式批准决定。

Marriott anchors：

- B01：`26186000000 USD / OK`
- B03：`0.1756281982738868097456656229 ratio / OK`
- B10：`69.3 percent / MDA_OK`
- B11：`128.8 USD / MDA_OK`

Pfizer B03 anchor：`0.3329551446971028619824541779 ratio / OK_APPROX`。

## 3.2 `metric_evidence.csv`

完整执行 R2 §3.10：

- 非迁移 evidence 按 R2 保留；
- B01/B10/B11 一 source binding 一行；
- B03 一 source component 一行，稳定 `evidence_order`；
- final ratio 不伪装成 component raw value；
- reconciliation receipt 必须机械重建冻结 legacy 的 `;` / `+` 聚合；
- `evidence_quote/extraction_method/parser_version` 的 delta 必须诚实记录，不能继续冒充 `lodging_kpi_extractor/sec_pipeline_v1`。

## 3.3 Cutover 后行为

- vNext 是四指标唯一正式 producer；
- 旧 lodging extractor/repair 和旧 B03 resolver 删除或 production-unreachable；
- 旧路径写迁移指标时失败 `LEGACY_PATH_STILL_ACTIVE`；
- root CSV/报告是 committed active vNext bundle 的 compatibility mirrors；
- official consumer 使用 pinned PublicationView；
- latest run 失败/WITHHELD 时 previous active 保持，并显式显示“更新尝试未发布”；
- report、Golden、coverage、validation、Stage 12、snapshot checker 使用同一 pinned view；
- rollback 只切 pointer，不重新启用旧 parser。

---

# 4. 必须完成的剩余开发

## A. 正式 operator / review CLI

不是孤立 toy demo；同一套受支持入口覆盖 recorded 和 live，至少具备：

```text
prepare/init
status
review list/show/decide
resume/finalize
replay
project/publish
```

cold-start operator 只读 `AGENTS.md` 和正式 runbook，即可：

```text
创建 OPEN Run
→ 定位 review.md / ReviewUnit
→ HUMAN APPROVE/REJECT
→ finalize / validation / freeze
→ 无 AI replay
→ complete Batch / Projector
→ prepare / commit publication
→ PublicationView read-back
```

- recorded：socket=0，不修改正式 active；
- live：只有显式 `--execute-live` 才联网；
- 不要求用户读 tests、调用未文档化 helper 或手改 JSON；
- 每一步输出状态、下一步和 artifact path；
- 不自动 APPROVE。

Review CLI 稳定错误码至少包括：

```text
RUN_NOT_OPEN
REVIEW_UNIT_NOT_FOUND
REVIEW_UNIT_AMBIGUOUS
PARALLEL_EFFECTIVE_DECISIONS
SUPERSEDES_NOT_EFFECTIVE_TIP
REVIEW_CONTEXT_STALE
DECISION_ALREADY_EFFECTIVE
```

wrong-tip 必须显示 requested/current tip 与可复制恢复命令；默认不打印 traceback，`--debug` 才打印；支持 `--json`。

## B. live Reader、第二布局、holdout、三次稳定

- 实现正式 OpenAI provider factory；
- 当前 Marriott frozen source/prompt 连续 live 三次；
- 三次 selected values、required claims、compatibility result 与 substantive ReviewUnit identity 相同；
- 第二真实布局通过；
- post-freeze independent holdout 通过且 production semantic source hash 不变；
- wrong-cell、wrong-locator、schema failure、timeout、rate-limit 继续 fail closed；
- AI 不可用时 active 不变，不回退旧 resolver。

## C. 十公司完整 staging parity

生成真实：

```text
current registry × [B01, B03, B10, B11]
```

要求：

- complete exact set，含 applicable 与 `N_A_STRUCTURAL`；
- 同一 fiscal year，混批必须拒绝；
- R2 strict compatibility 全部通过；
- B03 reconciliation exact；
- coverage、Golden、repair validation、report、terminal manifest、publication validation receipt 来自同一 pinned candidate；
- 任一 applicable WITHHELD 阻止整个 candidate。

## D. 正式 Cutover 与旧路径退出

- 将 vNext Bridge 接入正式完整批次；
- Stage 04/09/11、`apply_p0_repairs()`、repair、generic upsert 和其他旧 producer 不再写四指标；
- 旧 lodging functions/route/settings 与旧 B03 resolver 删除或正式不可达；
- 每个旧 producer/check 产生 `legacy_invariant_migration_receipt`：`removed / ported / replaced / obsolete-with-proof`；
- old-resolver-throws full flow 通过；
- root outputs 与 committed active bundle hashes 一致；
- report：AI socket=0、SEC socket=0、repair=0、authoritative write=0。

## E. Publication failure、并发和真实 rollback

在已有 primitive 基础上动态执行：

- mixed-fiscal-year reject；
- mid-bundle-write failure：active 不变，无成功半成品；
- mid-mirror-write failure：previous bytes 恢复；
- mirrors written / pointer not switched：按 active pointer 恢复；
- CAS/concurrency one winner；
- pinned view 不混读；
- WITHHELD 保留 previous active。

真实执行：

```text
commit new publication
→ report → Stage 12 → snapshot checker
→ rollback previous publication
→ report → Stage 12 → snapshot checker
→ restore new publication
→ report → Stage 12 → snapshot checker
```

rollback 期间不得调用旧 parser。

## F. 文档、source closure 与 acceptance runner

同步所有 R2 §7 要求的文档和配置，至少包括：

- `AGENTS.md`
- `README_RUN.md` generator/post-processor
- `SOP.md`
- `TESTING.md`
- `architecture.md`
- `interact.md`
- `capability_contract.json`
- `docs/business_user_guide.md`
- `docs/validation_snapshot_provenance.md`
- `01_SOP...md` / `02_指标定义...md`
- `IMPLEMENTATION_TODO.md`
- `decision_register.json`
- `config/validation_source_policy.json`

新增正式代码、测试、Requirement decision、权威文档和 active bundle roles 必须进入 source/artifact closure。

Acceptance runner：

- `--scope recorded`：真正离线；
- `--scope full` 未提供 `--execute-live`：明确 readiness/configuration 结果，不冒充 full；
- `--scope full --execute-live`：真实运行完整 live、staging、Cutover、rollback/restore；
- `NOT_RUN` 永远不能形成 PASS。

---

# 5. 验收与关闭门

**R2 §9 的每一条 Acceptance Checklist 继续必选。** PR #13 的旧证据可以证明基础设计存在，但最终关闭必须在最终候选 HEAD/环境上刷新需要新鲜度的证据。

R3 额外要求：

## 5.1 基础回归

- [ ] Python 3.9 vNext 全量；
- [ ] 默认解释器 vNext 全量；
- [ ] 默认解释器全仓；
- [ ] provenance/light-package 正负例；
- [ ] semantic audit；
- [ ] company-literal/scalability；
- [ ] capability alignment；
- [ ] 无 GitHub checks 时不写 CI PASS。

## 5.2 UX / live / staging / Cutover

- [ ] cold-start recorded journey；
- [ ] Review list/show/decide 和错误恢复；
- [ ] Marriott live 三次稳定；
- [ ] 第二真实布局；
- [ ] post-freeze holdout且 production hash 不变；
- [ ] 十公司 strict parity；
- [ ] mixed-fiscal-year 负例；
- [ ] committed active pointer；
- [ ] old-resolver-throws full flow；
- [ ] `LEGACY_PATH_STILL_ACTIVE`；
- [ ] invariant migration receipt；
- [ ] report read-only；
- [ ] mid-write faults、recovery、CAS、pinned view、WITHHELD；
- [ ] 真实 rollback/checker/restore。

## 5.3 最终命令与 receipt

以下命令必须真实返回 0：

```bash
python3 tools/run_acceptance.py --scope recorded
python3 tools/run_acceptance.py --scope full --execute-live
python3 tools/check_validation_snapshot.py
```

最终 full receipt 至少引用：

- exact Requirement/FSD/R2/R3/Decision identities；
- provider/model/egress policy 与三次 live attempt；
- 第二布局/holdout source identity；
- ten-company parity receipt；
- FROZEN Runs / complete Batch / projection manifest；
- active publication ID、bundle hash、ledger prefix；
- old-path exit/invariant migration receipt；
- failure/concurrency receipts；
- rollback/restore receipt；
- final snapshot hash。

---

# 6. Non-goals

R2 §2.2 全部 Non-goals 继续有效，包括不建设 Web UI/API/聊天入口、Databricks/数据库/daily scheduler、通用 taxonomy/repository、OS 级强沙箱、自动 GC、额外指标迁移或平台级重写。

不得用非目标扩大范围或推迟四指标正式 Cutover。

---

# 7. PR 与 fresh-context 审核要求

建议 PR 标题：

```text
feat(vnext): complete formal cutover for B01 B03 B10 B11
```

PR body 必须逐项映射：

- R2 SU-00～SU-11；
- R2 AC-01～AC-28 / §9；
- R3 A～F 与 §5；
- baseline → recorded → live → staging → active → rollback → restored active 的 IDs/hashes；
- exact value/field parity；
- second layout/holdout；
- old path call graph 与 migration receipt；
- final full receipt。

只有全部通过后才能 `Closes #12`。任何 NOT_RUN、BLOCKED、缺凭据、缺真实布局、缺 staging、旧 producer 可达、无 active/rollback/full 时，Issue 保持 OPEN。

## Issue Done 的唯一判定

> AI 真正吸收完整表格布局和措辞变化；Checker/Reader/renderer/Projector 没有重建行业 resolver；B03 由确定性 Spec runtime 驱动；Review 绑定实际可见上下文；十公司 CSV/证据 strict compatibility 通过；旧 producer 与旧不变量完成迁移；active publication 在失败、并发、WITHHELD 和 rollback 下始终是一个完整可审计版本；最终 full live acceptance 返回 0。