## 0. 经最新主干代码审计确认的事实基线

1. 最新 `main` 仍为 `c37cecdfe88344d78172dd9dc24bd4c445763901`。当前 checked-in `validation_run_manifest.json` 虽为 `FULL_VALIDATION / PASSED`，但其 `source_commit` 仍是 `7dee963d...+dirty`；现有 provenance 绑定的 clean source tree 也来自 `7dee963d...`。因此它可以证明当前 checked-in artifacts 的既有来源关系，却不能直接充当 `c37cecd` 的精确实施基线。SU-00 必须重新生成独立 baseline manifest。
2. 当前项目仍是本地、配置驱动、SEC-only 的阶段 `00`–`12` 批处理；核心业务、repair、validation、报告和阶段调度集中在约 20,000 行的 `scripts/sec_pipeline.py`。
3. B03 的 Operating Income direct/fallback、D&A direct/composed、1% cross-check、quality 传播和最终公式仍由 Python 控制流实现。当前 companyfacts 选择还依赖有序 concept chain、目标 accession 优先、`filed/accession/unit` 排序等具体语义。
4. B10/B11 仍由酒店专用 resolver 产生。当前路径会按 RevPAR/Occupancy/ADR 关键词切分窗口、识别表头、尝试列排列、搜索 scope 标签、使用数值范围，并以 5% 的酒店恒等式阈值筛选候选。
5. 旧酒店路径不是一个函数，而是一组生产函数与 validation checks。至少包括 `text_has_lodging_kpi_keywords()`、`lodging_table_segments()`、`lodging_metric_orders()`、`lodging_scope_matches()`、`lodging_candidate_from_cells()`、`lodging_kpi_fact_from_text()`、`apply_lodging_kpi_metrics()`、`repair_lodging_kpis()`，以及 `check_lodging_kpi_extractor()`、`check_lodging_header_mapping_not_position_regex()`、`check_lodging_revpar_adr_occupancy_identity()`、`check_eleventh_company_behavior_lodging()`、`check_lodging_ok_recall_not_regressed_without_reason()`。Cutover 不能只删除 producer 而静默缩小这些不变量的验收覆盖。
6. Stage 11 当前不是只读报告阶段。它先创建 `IN_PROGRESS` manifest，再迁移 locator、运行 `apply_p0_repairs()`、改写正式 metrics/evidence、刷新 repair-sensitive Golden，随后才生成 coverage、validation、报告和 README。
7. 当前 `write_csv_file()` 直接以 `w` 打开目标路径；Stage 04 和 repair 路径顺序写入 `metrics_matrix.csv` 与 `metric_evidence.csv`。现状既没有单文件原子替换，也没有多文件事务。
8. 当前 Marriott 基线至少为：B01=`26186000000 USD`；B03=`0.1756281982738868097456656229`；B10=`69.3 percent`；B11=`128.8 USD`。B10/B11 的 `fiscal_year` 与 `form` 当前为空，`confidence=0.85`；B10/B11 evidence 中的 `extraction_method=lodging_kpi_extractor`、`parser_version=sec_pipeline_v1`、旧 raw header/row 窗口和 5% resolver 的 identity 文本都是旧实现副产品。
9. 当前 B03 evidence 把多个 source URL、path、hash、accession、document、context 和 raw value 以分号聚合在一行，concept 以 `+` 聚合；最终 ratio、formula quote 和 unit 又是结果级字段。FSD 要求迁移后按 source binding 多行化，因此不能把“拆行”伪装成机械 CSV split。
10. 当前 production registry 只有一家 lodging 公司（Marriott）。所以“布局变化不改生产 Python”必须主要由严格 fixture/holdout 设计证明，不能只拿同一张生产表自证泛化。
11. 当前 runtime 契约是 Python 3.9+、标准库和本地模块；仓库没有 `pyproject.toml`、requirements、tox 或 CI workflow。任何新依赖、SDK、语法或“CI 已通过”声明都必须显式、真实。
12. 当前 source-input closure 包括 `scripts/`、`tools/`、`config/`、`tests/` 与核心验收文档；terminal artifact closure 绑定 metrics/evidence/coverage/Golden/report/request ledger 等。新增 `requirements/`、`catalog/`、vNext Run、publication bundle、review context 和 publication validation receipt 若未被 policy 分类，就不能声称由最终 snapshot 证明。

---

# 1. 背景与目标（Why）

当前系统已经能生成一套可追溯的 SEC 年度批次，但它把两种高变化成本固化在生产 Python 中：

- **文件布局和公司措辞变化**：酒店表格换列、换表头、换 scope 文案时，需要修改专用搜索、窗口、正则、候选排序和范围规则；
- **财务选择逻辑变化**：B03 的 direct/fallback、guard、cross-check 和质量传播隐藏在程序控制流，业务定义无法独立编译、审计和重放。

本期不是在旧 parser 前面加一个 LLM，也不是让 AI 输出一个数字后由程序再完整“解一遍题”。目标是建立以下职责边界：

```text
现有 SEC request ledger / filing inventory / immutable raw bytes
        ↓
RawBlob + SourceReference + metric-neutral 全表 table-grid
        ↓
AI Reader：找目标表、行、列、年份与 scope，返回候选和精确 locator
        ↓
Evidence Checker：只验证来源、locator、cell、标签、数值和声明式约束
        ↓
HUMAN Review：批准无法低成本机械证明的 period / scope 经济口径
        ↓
Verified Observation
        ↓
MetricSpec + deterministic Calculator：执行选择、guard、公式与 quality
        ↓
MetricResult + ExecutionTrace + FROZEN Run
        ↓
Legacy Projector：合并完整非迁移结果，生成完整 publication candidate
        ↓
Staging Golden / Validation / Report / Provenance
        ↓
单一 active pointer 提交完整 publication bundle
```

完成后必须同时证明：

1. AI 接收到的是 metric-neutral 的完整表格集合，而不是旧关键词 parser 预筛后的“答案候选”；
2. 新酒店布局不再要求新增酒店专用生产 Python；
3. Evidence Checker、prompt builder、renderer、Projector 等可执行模块没有重新长出第二套酒店 resolver；
4. B03 的选择、fallback、guard、cross-check、Decimal 和 quality 语义已从专用 Python 控制流迁入可哈希、可编译的 MetricSpec；
5. B01/B03/B10/B11 能诚实投影回现有用户依赖的完整结果，而不是通过保留旧 parser 的方法描述制造“假 parity”；
6. 任一 AI、review、evidence、withheld、Golden、validation、report、provenance 或 publication 失败，都不能让新的不完整版本取代上一成功 active publication；
7. 旧酒店 producer 与旧 B03 专用生产路径真实退出；历史 FROZEN Run 在没有模型凭据时仍可 replay；
8. 项目最终复杂度从“每个新布局新增 parser”转为“新增 Spec/fixture/AI locator”，而不是把旧复杂度搬进一个更隐蔽的通用函数。

这是一项 **职责迁移、审计闭环和发布边界重构**，不是新增长期双跑链，也不是平台级重写。

---

# 2. Scope / Non-goals

## 2.1 Scope

本 Issue 必须端到端完成：

- B01 Revenue：复用现有确定性 structured-fact 行为，不强制经过 AI；
- B10 Occupancy、B11 RevPAR 与 ADR 支撑 Observation：同一次 lodging disclosure AI extraction；
- B03 EBITDA margin：全部 direct/fallback、guard、cross-check、candidate cardinality、quality 与 formula 由 MetricSpec/声明式 runtime 表达；
- 复用现有 request ledger、filing/accession inventory、raw bytes、content hash、portable locator 与 request-attempt provenance；
- 新增 Requirement Snapshot、Decision Register、RawBlob、SourceReference、DerivedAsset/table-grid、ReaderInputManifest、AIExtractionAttempt、Run、Candidate、EvidenceCheck、ReviewUnit、ReviewDecision、VerifiedObservation、MetricResult、ExecutionTrace、ValidationReceipt、PublicationManifest；
- 新增 canonical serialization、Decimal policy、semantic runtime version、spec/prompt/closure/content/audit/review-unit hash；
- 新增 HUMAN Review 的最小 CLI/文件工作流，不建设 UI；
- 新增安全、不可误导的完整 review context，证明 reviewer 实际看到的内容；
- 新增 Legacy Projector，生成完整 publication candidate，而不是只输出四个指标；
- 让 Golden、repair validation、coverage、report、terminal manifest 和 publication validation receipt 全部针对同一 pinned PublicationView 工作；最终 acceptance receipt 再引用已提交 active publication 与 snapshot；
- 完成 recorded replay、live shadow stability、strict compatibility、Cutover、旧生产者禁用、故障注入、并发、rollback、无 AI replay 和最终 full validation；
- 同步能力契约、用户行为、业务指南、架构、SOP、测试、provenance policy、生成型 README 与 acceptance runner。

## 2.2 Non-goals

本 Issue 明确不实现：

- 通用 deterministic scope parser、Scope Terms Registry 或 CompanyRule engine；
- Source Recipe、layout fingerprint、Recipe cache；
- 默认双 Reader、Critic、Adjudicator 或自动批准毕业机制；
- A02、B06、E02、C/D 类定性指标或其他行业指标迁移；
- 完整 `NOT_DISCLOSED_CONFIRMED` / coverage 平台；
- Databricks current/as-of/NO_CHANGE、生产数据库或 daily scheduler；
- Web UI、API、聊天入口、通用 taxonomy service 或 repository layer；
- 通用 cross-source reconciliation 引擎；
- 为架构整齐而让所有 structured facts 经过 AI；
- 把第二家 lodging 公司加入正式 10-company registry；本期只允许使用测试用真实布局摘录和 holdout fixture，不改变生产公司范围；
- 建设 OS 级模型安全沙箱。PoC 采用诚实的依赖、调用图、egress allowlist 和无 shell/subprocess 写路径约束，不声称同进程模块具有强隔离能力；
- 自动 GC。Phase 1 保留所有 FROZEN Run 和 committed publication bundle；RawBlob 引用既有 content-addressed bytes，不复制大文件；
- 顺带重写整个 `sec_pipeline.py`；只抽离本期 vNext 边界及 staging/publication 必需的公共能力；
- 除本 Issue 明确列出的 `METH-01` 外，借 vNext 修正旧数值、旧口径或旧业务状态。

---

# 3. 契约摘要

## 3.1 需求身份、规范优先级与 Decision Register

实施输入不能只写“v3.3.1”。SU-00 必须创建一个被 source policy 覆盖的 Requirement Snapshot（建议路径 `requirements/ai_first_v3_3_1/`，等价路径可接受），至少包含：

```text
FSD.md                         # exact approved FSD bytes
ISSUE_CONTRACT.md              # 本 Issue 当时批准的完整正文导出
decision_register.json         # 机器可读的人类决策
```

`baseline_manifest.json` 至少记录：

```text
repository_commit
source_input_tree_sha256
fsd_sha256
issue_contract_revision
issue_body_sha256
decision_register_sha256
metrics/evidence/Golden/manifest/provenance hashes
created_at_utc
```

规范优先级固定为：

```text
当前代码事实与已冻结 baseline
→ FSD exact snapshot
→ 本 Issue R2 对 FSD 冲突的显式裁决
→ decision_register.json 中后续获批决定
→ PR 实现
```

Issue 评论不是执行时真相源。`decision_register.json` 每条记录至少包含：

```json
{
  "decision_id": "D-01",
  "status": "APPROVED | REJECTED | SUPERSEDED",
  "choice": {},
  "approved_by": "stable-human-id",
  "approved_at_utc": "...",
  "supersedes_decision_id": null,
  "evidence": "..."
}
```

同一 `decision_id` 的有效记录必须形成单链；出现两个并列有效决定时 fail closed。FSD、Issue Contract 或 Decision Register bytes 改变后，旧 baseline 与依赖它的 approval/publication 不能继续命中。

## 3.2 来源、RawBlob、SourceReference 与 AI 输入契约

- `RAW_BLOB` 必须正式进入 record schema。RawBlob 只代表 exact bytes；SourceReference 代表这些 bytes 在 company/accession/document/source_role 中的身份。
- 相同 bytes 可以对应多个 SourceReference，不得因 hash 相同覆盖 accession/document provenance。
- vNext 不重建 SEC acquisition，不得绕过现有 request ledger、material inventory 和 immutable request attempts。
- RawBlob 默认通过 content hash 引用既有 repository bytes，不在 `artifacts/vnext/` 重复复制完整 10-K HTML；FROZEN Run 固化 SourceReference、derived grid、records 和 hashes。
- table-grid transform 必须是 metric-neutral：只负责重建所有 HTML table 的结构、稳定 `table_id`、row/column path、cell text 与 raw locator，不判断哪张表与 B10/B11 有关。
- **PoC Reader 的语义输入必须包含目标文档全部 table-grid，按文档顺序、无关键词预筛、无 scope 预筛、无“可能含 RevPAR”窗口。** `ReaderInputManifest` 必须列出 DerivedAsset 中每一个 `table_id`、grid hash 和顺序；传给模型的 exact table set 必须与 manifest 完全一致。
- prompt 中出现 Occupancy/RevPAR/ADR 是允许的，因为任务说明来自 Spec；任何可执行代码用这些词筛选送入模型的 bytes 都是禁止的。
- 当前旧 `text_has_lodging_kpi_keywords()` / `lodging_table_segments()` 一类逻辑不得搬入 prompt builder。若所选模型无法接收完整表格集合，本期必须换模型或阻塞 live cutover，不能隐式引入 semantic prefilter。
- AI 指错 locator、但文档其他位置恰好存在正确值时，Checker 仍必须拒绝；不得全文搜索后“帮 AI 找对”。

## 3.3 AI Adapter、attempt 与诚实安全边界

- AI transport 使用独立 adapter，不复用 `SecHttpClient`；SEC 数据来源边界和模型处理/egress 边界分离。
- Phase 1 不声称同进程 Python 模块是安全沙箱。可验证承诺是：adapter 调用图不包含 shell、任意 subprocess、repository authoritative write、数据库写或非 allowlist 网络；模型只能接收显式 ReaderInputManifest 对应的 payload。
- 远程模型默认关闭。启用前必须在 Decision Register 批准 provider、model、endpoint host、region、retention、data-use、timeout、retry、最大 payload 和 filing egress policy。
- secret 只来自环境或未提交本地 secret store；任何 artifacts/outputs/report/review/日志不得写入 key、Authorization header 或完整 secret。加入 key-like test token 扫描。
- 每次 transport attempt 独立记录，不覆盖前次：

```text
attempt_id
status = STARTED | SUCCEEDED | FAILED
provider/model/endpoint_host
sampling parameters
reader_input_manifest_hash
exact outbound request-body SHA-256（不包含 Authorization 等 secret headers）
raw_response_sha256
provider_request_id（如有）
started/finished UTC
error class
```

- temperature 固定为 0；provider seed 如支持可以记录，但不得被当作确定性证明。
- 快速测试一律使用 recorded response/test double，并以 socket 级 guard 阻断真实网络；live shadow 在 Cutover 前至少连续 3 次对同一 frozen source/prompt 产生相同 `review_unit_hash` 和 compatibility result，否则不具备 Cutover 资格。
- 无凭据、timeout、限流、transport error、非法 JSON、duplicate JSON key、schema failure 或缺 required role 时 fail closed；不得回退旧酒店 resolver 继续发布。

## 3.4 Canonical JSON、Decimal 与语义运行时版本

Canonicalization 固定为：

- UTF-8、LF；object key 按 Unicode code point 排序；
- JSON parser 必须拒绝 duplicate keys、NaN、Infinity、lone surrogate 和未知字段；
- list 默认保序；只有 schema 明示 `collection_semantics=set` 的字段才排序，且重复成员直接失败；
- `choose_first` branches、arithmetic `args`、evidence order、source priority、selected/competing order 都是有序数组，换序必须改变 semantic hash；
- semantic string 使用 NFC；raw filing bytes/raw cell text 单独保留，不做 Unicode 归一化后冒充原文；
- Decimal 固定 fixed-point，不使用 exponent；`-0` 统一为 `0`；trailing zeros 规范化；null、空集合和字段缺失保持不同；
- 输入 Decimal 最多 128 个有效数字，绝对 scale 不超过 64；越界 fail closed；
- 所有算术在显式 `localcontext(prec=28, rounding=ROUND_HALF_EVEN)` 中执行，不依赖进程默认 Decimal context，不在中间步骤隐式 quantize；
- semantic runtime 至少有：

```text
canonicalizer_semantic_version
spec_interpreter_semantic_version
calculator_semantic_version
projector_semantic_version
review_renderer_semantic_version
```

这些版本进入 `execution_semantics_hash` 和 Spec closure。实际 code fingerprint 只进入 audit hash；无语义 refactor 不必 bump semantic version，任何执行语义变化必须 bump，不能只靠相同内容 hash 掩盖 runtime 变化。

## 3.5 MetricSpec DSL 的确定性语义

MetricSpec 使用 Markdown + JSON-compatible YAML front matter，Phase 1 不引入通用 YAML 行为。compiler 必须把所有默认值展开进 compiled Spec 和 semantic hash，不允许运行时藏默认。

DSL 只支持本期所需的有限能力：

```text
structured extraction role
reuse_metric_observation
choose_first
add / subtract / multiply / divide
same_accession / same_period / same_entity / compatible_units
annual_duration / denominator_nonzero
optional cross_check
identity_constraints
quality propagation
legacy_projection
```

确定性规则：

1. `choose_first` 严格按 Spec 顺序尝试，第一个满足 cardinality、guard 和 cross-check 的 branch 获胜；每个被拒 branch 和 reason code 进入 Trace。
2. concept priority 按 Spec 列表顺序；structured fact selection policy 必须显式声明或引用有版本的 `legacy_companyfacts_v1`，其完整展开规则进入 closure，不能只是一个隐藏函数名。
3. `legacy_companyfacts_v1` 至少冻结当前行为：目标 period 过滤、form/annual rule、同 concept 内按 `filed/accession/unit` 降序、target accession 优先；任何改变必须导致 semantic version/hash 变化。
4. 每个 role 必须声明 cardinality。需要唯一事实时，0 条返回明确 missing reason；多条在声明 tie-break 后仍不唯一时失败 `AMBIGUOUS_CANDIDATE`，不得静默 `first()`。
5. `reuse_metric_observation: B01` 必须在相同 company、period、scope_key 下唯一，0/多条均失败。
6. AST 最大深度 32、最大节点 256；禁止递归 reference cycle、未知 op、未知 guard、未知 quality 和未声明 fallback。
7. arithmetic args 有序；subtract/divide 不可交换；add/multiply 即使数学上可交换，也保留 Spec 顺序用于 Trace 和 semantic hash。
8. generic runtime 不得包含 B03、lodging、Marriott 或具体 scope 词的控制分支。业务词、concept list、tolerance、notes template 和 legacy projection 只能存在于 Spec/catalog。

## 3.6 Evidence Checker 与声明式约束

Checker 只做以下通用机械检查：

- asset、SourceReference、hash、parent relation 与 source role 一致；
- ReaderInputManifest exact table set 与实际 prompt payload 对齐；
- table/row/column/span/fact locator 可解析；
- selected/competing locator 指向的 raw cell/text 真实存在；
- AI claimed raw value 与该 locator 重读 raw value 完全一致；不一致直接 `REJECTED`，不得用重读值替换后继续；
- header/caption/row/label locator 位于同一目标 table path；
- percent、负号、括号、million/billion 等按统一 numeric policy 规范化；
- required claims 与 ReviewDecision approved claims 做 canonical 结构比对；
- B03 Trace 能从 Verified Observations 重算；
- Spec 中声明的通用 `identity_constraints` 能由通用表达式求值器执行。

酒店恒等式不得以 `lodging_identity_error()` 的专用分支迁入 Checker。lodging disclosure Spec 声明：

```yaml
identity_constraints:
  - expression:
      expected: {op: multiply, args: [adr, occupancy]}
      actual: revpar
    tolerance:
      kind: relative
      value: "0.01"
```

Checker 明确不得：全文搜索目标表、独立选择行列、解释 Comparable/Systemwide/Worldwide 的经济含义、重排语义候选、维护酒店词库、读取旧 resolver 答案、按 metric/company/industry 写控制分支，或根据“数值看起来合理”替换 locator。

Architecture audit 覆盖全部 `scripts/vnext/**`、相关 Bridge/Projector/report adapter，而不只 Checker/Calculator。白名单仅限 `catalog/`、Requirement Snapshot 和 test fixtures。audit 产出逐命中记录（file/line/literal/type/allowed/reason），并用行为测试证明 prompt input exact set 未被业务词过滤；不能只用一条字符串断言自证。

## 3.7 ReviewUnit、ReviewDecision 与安全渲染

酒店三个角色是一个 review unit。`review_unit_hash` 必须覆盖：

```text
Occupancy / RevPAR / ADR selected candidates
全部 competing candidates
全部 unresolved_competing_claims
candidate substantive hashes
source/spec/derived asset/evidence bindings
EvidenceCheck result
canonical review_context_hash
rendered_review_hash
review_renderer_semantic_version
```

Candidate substantive hash 也必须包含 unresolved claims；风险主张变化不能继续命中旧 approval。

审核流程：

- `review_context.json` 是不可变、canonical 的审核输入；`review.md` 是 renderer 生成的展示资产。
- Decision 必须记录 reviewer 当时看到的 `review_context_hash + rendered_review_hash + renderer_semantic_version`。日后可以重新渲染，但不能把新渲染内容冒充旧 reviewer 已看过；内容/hash 变化需要新 Decision。
- review context 展示目标完整 table-grid，或该目标表全部行 × Occupancy/RevPAR/ADR 角色列 × 全部年度列；不得只显示 AI 选出的 selected/competing 子集。
- review view 可以显示同表前期值和机械 identity 计算过程，但不得显示旧 resolver 的答案或“legacy 正确值”作为提示，防止人工审核被 oracle 橡皮图章化。
- filing 内容按不可信文本渲染：禁止 raw HTML；转义 Markdown/HTML；将 C0/C1 control、zero-width 和 bidi override 等不可见/方向字符可视化为 `\uXXXX`；table cell 不得通过 Markdown pipe、code fence 或超长行改变页面结构；页面必须显式标注“不可信 filing 内容”。
- ReviewDecision 只批准 claims，不修改 Candidate、不直接赋值 publication、不手工填值。
- 同一 review unit 的 Decision 必须通过 `supersedes_decision_id` 形成单链；两个并列有效 Decision fail closed。
- freeze 前必须从磁盘重新验证 Candidate、Evidence、review context、Decision、Spec 和 source binding，防止 OPEN 期决定后的 TOCTOU。

## 3.8 状态模型、WITHHELD 与用户可见新鲜度

状态不得混成一个字段：

| 对象 | 状态 |
|---|---|
| AI attempt | `STARTED → SUCCEEDED` 或 `FAILED` |
| Review unit | `PENDING → APPROVED`、`REJECTED` 或 `INVALIDATED` |
| vNext Run | `OPEN → FROZEN` 或 `FAILED` |
| ValidationReceipt | `NOT_RUN → PASSED` 或 `FAILED` |
| Publication candidate | `BLOCKED` 或 `PUBLISHABLE` |
| Publication transaction | `PREPARED → COMMITTED` 或 `ABORTED`；已提交版本可 `SUPERSEDED`，或通过指针回滚重新成为 active |

规则：

- `FROZEN` 只表示不可修改，不等于已验证、可发布或已发布。
- 含 WITHHELD 的 Run 可以 FROZEN，便于审计和 replay；但任一 **APPLICABLE migrated result** 为 WITHHELD 时，整个 publication candidate 必须 `BLOCKED`。Phase 1 不做部分发布，也不让 Projector 给 WITHHELD 猜 Legacy status。
- `N_A_STRUCTURAL` 不是 WITHHELD，可以正常进入完整 publication。
- active publication 与 latest run/attempt 分开记录。新 Run 失败或被 withheld 时，上一 active publication 继续可见，同时 `latest_run_status` 必须显式告诉用户“存在更新尝试但未发布”，不得静默让旧版本看起来像最新成功运行。
- 纠错创建 superseding Run；旧 Run/Decision/Publication 不修改。

## 3.9 数值、容差与唯一批准的方法变更

### METH-01｜酒店 identity 从 legacy 5% 收紧为 1%

FSD 要求 1%，当前 resolver/gate 使用 5%，两者与“Phase 1 不改变旧方法”冲突。本 Issue 作出唯一规范性方法裁决：

- vNext lodging identity 使用 **1%**，这是本 Issue 唯一预先批准的方法行为变化；
- 当前 Marriott anchor 同时通过 5% 和 1%，所以冻结基线的当前 value/status 不发生变化；
- 该变化必须在 Decision Register、MetricSpec、capability/user docs、parity receipt 和 release note 中单独列出，不能被写成“纯重构”；
- 0.99%、1.00%、1.01% 边界测试：`error <= 0.01` 通过，`>0.01` 失败；
- `expected = adr * occupancy_ratio`；若 expected<=0、任一输入缺失/非有限或 unit 不兼容，则 identity 无法成立并 WITHHELD；比较使用完整 Decimal 中间值，不先四舍五入。

B03 cross-check 继续保持当前 1% 方法，并冻结当前 denominator 语义：

```text
reconstructed = pretax - aggregate_nonoperating
expected = revenue - costs_and_expenses
denominator = abs(reconstructed) if reconstructed != 0 else Decimal("1")
relative_error = abs(expected - reconstructed) / denominator
pass iff relative_error <= Decimal("0.01")
```

对 B03 同样加入 0.99%/1.00%/1.01%、zero、negative reconstructed 和外部 Decimal context 污染测试。

## 3.10 Legacy Projection、parity 与 evidence grain

migrated IDs 固定为 `[B01, B03, B10, B11]`。

### metrics_matrix compatibility

- 非 migrated 行逐字节保留；
- B01/B03 的全部字段 exact parity；
- B10/B11 以下业务/兼容字段 exact parity，包含空值：

```text
company, cik, metric_id, metric_name, value, unit, status, source_class,
period_start, period_end, fiscal_year, fiscal_period, accession, form,
filed_date, concept_or_section, context_or_dimension, confidence
```

- B10/B11 的 `confidence=0.85` 在 Phase 1 保留为显式 `compatibility_constant`，不得解释为模型 confidence；Phase 2 是否移除另立需求。
- 方法描述字段必须诚实，不得谎报旧 parser：

```text
formula, notes
```

B10/B11 允许 versioned old→new 声明式 delta；每个 cell 必须进入 compatibility receipt。B01/B03 formula/notes 默认 exact，除非实现发现旧文案事实上描述了已删除路径并由 Decision Register 单独批准。

### metric_evidence grain

- 非 migrated evidence 逐字节保留；
- B01/B10/B11 direct evidence 一 source binding 一行；source/value/period/accession/document identity 与基线 exact 或可机械等价；
- B03 一 source component 一行，稳定 `evidence_order` 与旧聚合顺序一致：
  - component 行的 `unit`、`value_raw`、`value_normalized`、concept/context 对应该 source component；
  - 最终 B03 ratio 不复制到每个 component 行；最终结果存在于 metrics row、ExecutionTrace 和 projection manifest；
  - validation 对 derived result 改为验证“全部 component evidence + Trace 能重算 final metric”，不再要求某一 component row 的 normalized value 等于 final ratio。
- reconciliation receipt 必须能按旧语义重建：

```text
source_url/repo_relative_path/content_sha256/accession/document_name/context/value_raw → 按 evidence_order 用 ";" 拼接
concept_or_section → 按 evidence_order 用 "+" 拼接
```

重建结果必须与 frozen baseline exact match；缺 component、重复、换序或多余 component 均失败。

以下方法字段允许声明式 delta，但必须 old→new 逐 cell 记录并诚实描述新路径：

```text
evidence_quote, extraction_method, parser_version
```

不得为了 byte parity 保留旧 header-window parser 或继续写 `lodging_kpi_extractor/sec_pipeline_v1`。

## 3.11 完整 Publication Bundle、active pointer 与读取保证

publication 不只包含 metrics/evidence。Stage 00 起，每一批次在 run-scoped workspace 中生成派生产物；publication candidate 至少包含：

```text
metrics_matrix.csv
metric_evidence.csv
coverage_matrix.csv
golden_results.csv
repair_validation_results.csv
stratified_audit.csv
scalability/semantic audit
projection_manifest.json
validation_run_manifest.json
publication_validation_receipt.json
REPORT_十公司财务指标.md
README_RUN.md
publication_manifest.json
引用的 FROZEN Run/content/review/trace/derived-asset hashes
```

request ledger、request log manifest 和 immutable request attempts 是独立 append-only audit chain，不因 publication rollback 回滚；publication manifest 只绑定本版本实际使用的 ledger prefix/SourceReference identity。

`publication_validation_receipt.json` 只记录使该 bundle 达到 PUBLISHABLE 的 pre-commit/staging gates。最终 `tools/run_acceptance.py` 在 commit、snapshot checker 和 rollback/restore 完成后另行生成 `outputs/acceptance_receipts/<receipt_id>.json`；它引用 active publication ID、snapshot hash 和真实命令结果，但不反向进入已提交 bundle，避免自引用循环。

Phase 1 规范性实现为：

```text
outputs/publications/<publication_id>/...     # immutable complete bundle
outputs/active_publication.json               # 唯一原子 commit point
artifacts/vnext/latest_run_status.json        # 最新尝试，不等于 active publication
```

- `active_publication.json` 通过同目录 temp + fsync + atomic replace 提交，包含 publication ID、bundle manifest hash、previous publication ID。
- `PublicationView.open()` 只解析 pointer 一次、验证 bundle manifest/hash 后 pin `publication_id`；该 view 生命周期内即使 pointer 切换，也只能读取同一版本。
- Stage 10/11/12、report、snapshot checker 和所有正式 consumer 必须使用同一个 pinned PublicationView，禁止每读一个文件就重新解析 pointer。
- 当前固定根 CSV/报告可以作为 compatibility mirror 保留，但 **任意不持 view 的外部直接读取者不属于组原子保证范围**。terminal acceptance 必须证明 mirror 与 active bundle hashes 一致；官方文档和内部代码以 PublicationView 为权威。不得声称两个独立固定路径对任意 POSIX reader 真正原子。
- 任一 write/fsync/hash/self-check/Golden/Validation/report/provenance/acceptance mirror 失败时，transaction ABORT 或 pointer rollback；上一完整 publication 继续 active。
- 并发 publisher 使用 lock + compare-and-swap precondition；只能一个 commit，loser 不得覆盖 active 或留下可识别为成功的半成品。
- Phase 1 不自动 GC：所有 committed bundle 与 FROZEN Run 保留；exactly one active pointer。非 active bundle 不进入当前 terminal closure，但各自 manifest/hash 必须自洽，可用于 rollback/replay。

## 3.12 Cutover、报告、replay 与旧不变量迁移

- shadow 可以读取旧结果作为 compatibility oracle，但旧值不得进入 HUMAN review context，也不得成为新 path 的运行时 fallback。
- Cutover 后 stage 04/09/11、`apply_p0_repairs()`、通用 upsert 和任何旧 producer 都不得向 publication candidate 写 B01/B03/B10/B11；检测到即失败 `LEGACY_PATH_STILL_ACTIVE`。
- 旧 lodging production functions 删除或生产不可达；旧 B03 专用 resolver 不再被正式运行。测试中可保留 frozen expected fixture，不保留可调用 production oracle。
- 对每个旧 lodging production function 和五条旧 validation check 生成 `legacy_invariant_migration_receipt`：`removed / ported / replaced / obsolete-with-proof`。重点是每条不变量有等价证明，不用“新 check 数量”这种可博弈指标。
- Cutover full-flow 测试必须把旧 lodging/B03 resolver monkeypatch 为立即抛错，完整流程仍通过。
- 报告严格只读 active PublicationView：AI socket=0、SEC socket=0、repair=0、authoritative write=0。
- FROZEN Run replay 禁止 AI；只读取冻结 SourceReference/DerivedAsset/Candidate/Evidence/Review/Observation/Trace/Spec/semantic runtime versions。缺失或 tamper fail closed。
- rollback 只切换 active pointer 到上一 committed bundle；不得重新启用旧 parser。最终关闭 Issue 前必须在隔离 checkout 真实执行一次 rollback→report→snapshot checker→切回新版本。

---

# 4. 开发任务拆解（按 SU）

> SU 是同一 Issue 内的实施与验收边界，不是子 Issue。每个 PR 必须列出覆盖的 SU、未完成条件和对当前生产路径的影响；基础 PR 在最终 Cutover 前不得让 current main 失去可运行终态。

## SU-00｜冻结 Requirement Snapshot、精确 baseline 与 Decision Register

- [ ] 导出并保存 exact FSD、Issue Contract R2 和机器可读 Decision Register；加入 source policy。
- [ ] 生成 `c37cecd...` 精确 baseline manifest，而不是复用 `source_commit=7dee...+dirty` 的旧 run manifest。
- [ ] 冻结 source-input tree、current metrics/evidence/Golden/manifest/provenance、字段顺序、行顺序、Marriott/Pfizer anchors、B10/B11 空字段与方法元数据。
- [ ] 冻结旧 lodging production functions、validation checks 与旧 B03 control-flow inventory，供最终 migration receipt 对账。
- [ ] 关闭 live Cutover 前唯一外部人类决策：AI runtime/provider/egress/retention；测试和本地 recorded flow 不依赖该批准。
- [ ] 将本 Issue 已解决的裁决写入 register：完整全表输入、1% METH-01、batch-level publish block、publication pointer、parity field classes、ReviewUnit binding、诚实非沙箱边界。

**SU 验收**：所有后续 hash/parity/approval 都引用 immutable Requirement Snapshot 和 baseline manifest；任何需求 bytes 变化都会使旧 closure 失效。

## SU-01｜vNext 包边界、schema、状态与 canonical runtime

- [ ] 新建 `scripts/vnext/` 或等价清晰包边界，不继续把全部逻辑堆入 `sec_pipeline.py`。
- [ ] 定义 Requirement/Source/Attempt/Run/Candidate/Evidence/Review/Observation/Result/Trace/Validation/Publication schemas 和独立状态。
- [ ] 实现 duplicate-key rejecting canonical JSON、NFC semantic strings、ordered-list/set semantics、Decimal limits、fixed-point、`-0`、null/missing 区分。
- [ ] 所有算术使用显式 local Decimal context 28/HALF_EVEN；加入外部 context 污染测试。
- [ ] 实现 semantic runtime versions、spec/prompt/candidate/review-unit/approval/observation/scope/closure/content/audit/publication hashes。
- [ ] 定义 `PublicationView` 接口：pointer 只解析一次并 pin publication ID；实现可在 SU-09 完成，但接口和读取不变量在本 SU 冻结。
- [ ] 保持 Python 3.9；加入禁止 `match`、`tomllib`、`datetime.UTC`、`hashlib.file_digest`、`dataclass(slots=True)` 等越界 API 的兼容测试或静态检查。

**SU 验收**：AC-23、AC-27 的 canonical/Decimal 子集通过；语义不变的 metadata/refactor 不改 content hash，实质顺序/locator/claim/runtime semantics 变化必改 hash。

## SU-02｜复用 SEC evidence，构建全部 table-grid 与 ReaderInputManifest

- [ ] 从现有 request ledger/material inventory/raw bytes 构建 RawBlob/SourceReference adapter，不重新抓取已有 filing、不复制完整 HTML。
- [ ] 支持同 bytes 多 SourceReference；缺/歧义 provenance fail closed。
- [ ] 生成 content-addressed table-grid DerivedAsset，稳定处理 table order、header、rowspan/colspan、空 cell、footnote 和 raw locator。
- [ ] locator round-trip 到 exact cell/raw text；跨表、ambiguous merged cell、hash mismatch 被拒绝。
- [ ] `ReaderInputManifest` exact-list 文档全部 table IDs/hash/order；prompt payload table set 必须 exact match。
- [ ] 加 behavior test：改变 metric task terms 不改变 input table exact set；prompt builder 不接收“关键词筛表”回调或 query 参数。
- [ ] 真实布局测试只保存小型、明确标注的 table-grid/HTML excerpt，不复制第二份 2MB 10-K 到 tests；测试摘录不得进入正式 SEC evidence。

**SU 验收**：AC-20、AC-24 通过；旧 `lodging_table_segments()` 等逻辑没有出现在 transform/prompt input path。

## SU-03｜Company Traits、MetricSpecs、DSL Compiler 与声明式约束

- [ ] 新增 B01/B03/B10/B11 和 lodging disclosure group Specs。
- [ ] company traits 由现有 registry/SIC/profile 确定性投影或成为唯一权威，不能形成双真相源；若投影，加入 exact regeneration gate。
- [ ] compiler 展开全部 defaults、selection policy、cardinality、tie-break、Decimal/numeric policy、identity constraints、legacy projection 和 templates，并纳入 semantic hash。
- [ ] 实现有限 DSL：ordered choose_first、structured role、reuse、四则运算、guards、cross-check、identity、quality、projection；拒绝未知 op/guard/role、cycle、超深/超大 AST。
- [ ] B03 closure 包含 B01；B03 OI direct/reconstruction、D&A direct/composed、cross-check denominator、guard 和 quality 全部在 Spec 可见。
- [ ] lodging 1% identity 存在 Spec，不存在 Checker 专用分支。
- [ ] B10/B11 compatibility constant、exact fields 和允许 delta templates 明确。

**SU 验收**：AC-23、AC-27 通过；背景文案不改 semantic hash，公式/guard/order/tolerance/runtime semantic version 变化必改 closure。

## SU-04｜AI Adapter、metric-neutral 全表 Reader 与 recorded/live attempts

- [ ] 独立 AI adapter，不复用 `SecHttpClient`；默认 recorded/test-double 可运行。
- [ ] 无 remote Decision 时真实网络 fail closed；secret 不落盘。
- [ ] 一个 logical lodging extraction 同时返回 Occupancy/RevPAR/ADR、table locator、selected/competing/unresolved claims。
- [ ] Reader 输入为 ReaderInputManifest 的全部 tables；严格 schema validation，duplicate role/unknown field/非法 locator/非法 claims 失败。
- [ ] 每次 retry 独立 attempt，记录 input/payload/response hash、provider request ID 与错误。
- [ ] prompt injection fixtures；system contract 与 untrusted filing data 清晰分区。
- [ ] tests 使用 socket guard；live cutover gate 至少 3 次相同 review_unit_hash。
- [ ] audit metadata 不包含 key；扫描 artifacts/outputs/report/review 的 secret-like test token。

**SU 验收**：无凭据/timeout/schema failure 只产生可审计失败；不回退旧 resolver；AI input 没有旧语义 prefilter。

## SU-05｜通用 Evidence Checker、generic constraint evaluator 与安全 Review Renderer

- [ ] 实现 source/hash/locator/cell/local-label/numeric normalization/selected+competing replay。
- [ ] AI value 与 cell 不一致直接 reject；正确值在其他位置也不搜索。
- [ ] identity 由 Spec AST + generic evaluator 执行，Checker executable 不含 lodging/metric/company 词。
- [ ] 生成 canonical `review_context.json` 和 escaped `review.md`；绑定 exact rendered hash/version。
- [ ] 展示完整目标表、selected/competing/unresolved、Evidence、identity 过程和 claim status；不展示旧 resolver 答案。
- [ ] 对 Markdown/HTML/control/zero-width/bidi/超长 cell 注入做中性化 fixture。
- [ ] semantic audit 覆盖全部 vNext/Bridge executable，输出逐命中 receipt；行为测试验证 input exact set。

**SU 验收**：AC-01～AC-06、AC-20、AC-25 通过；Checker 只能证明“该来源/单元格/标签/约束真实”，不能自行批准经济 scope。

## SU-06｜ReviewUnit、Decision 单链、freeze TOCTOU 与无 AI replay

- [ ] 最小 review CLI 接受显式 HUMAN reviewer ID、APPROVE/REJECT、approved claims、reason 和 supersedes ID。
- [ ] reviewer ID 使用稳定 opaque ID，格式/长度显式校验；不隐式采用 OS 用户或模型身份。
- [ ] review_unit_hash 覆盖 selected/competing/unresolved、Evidence、Spec/source 和实际 rendered context。
- [ ] 同一 review unit 并列有效 Decision fail closed；变化使旧 Decision INVALIDATED。
- [ ] freeze 前从磁盘重新校验全部 binding/hash，结果进入 manifest；冻结后写入失败。
- [ ] Run 可以在 WITHHELD 状态 FROZEN，但不能成为 PUBLISHABLE；active publication 不变，latest run status 可见。
- [ ] 纠错创建 superseding Run；旧 Run/Decision 保持 immutable。
- [ ] replay 完全禁用 AI socket，缺 asset/decision/trace/runtime semantics fail closed。

**SU 验收**：AC-03～05、AC-12、AC-17、AC-19、AC-26 通过。

## SU-07｜Slice A + Slice B Shadow：B01 与 lodging disclosure group

- [ ] 将现有 B01 structured selection 适配为 vNext VerifiedObservation，不复制第二套 Revenue resolver。
- [ ] B01 selection policy、accession、duration、unit、continuity 和 fields 与 baseline exact parity。
- [ ] lodging 一次 AI extraction → Evidence → HUMAN Review → canonical Observations；B10/B11 投影，ADR 只作支撑。
- [ ] non-lodging 不调用 AI，保持 `N_A_STRUCTURAL`。
- [ ] shadow 只写 vNext run-scoped workspace，不改 active publication/root artifacts。
- [ ] 预先固定至少两种 materially different 布局：当前 Marriott + 第二个真实 lodging filing 的测试摘录；另含 prompt/render adversarial fixture。
- [ ] 实现冻结后由未编写实现的人加入第三种 holdout 布局；只允许 tests/fixture/recorded locator 变化，`scripts/` production tree hash 不变。
- [ ] 对 current baseline 做字段分类 parity；方法字段 delta 逐 cell receipt。
- [ ] live reader 连续 3 次 review_unit_hash 稳定后才满足 Cutover gate。

**SU 验收**：AC-07、AC-13、AC-21 和 live stability 通过；无 HUMAN Review 时整个 publication candidate BLOCKED。

## SU-08｜Slice C：Spec-driven B03、Calculator 与 Trace

- [ ] generic role resolver 只消费 compiled Spec 和 structured candidate facts，不写 B03 专用分支。
- [ ] 复用唯一 B01 Observation；0/多条失败。
- [ ] OI direct/reconstruction、aggregate bridge only、CostsAndExpenses cross-check 全部按 Spec。
- [ ] D&A direct/composed、防双计；combined direct 命中后不叠加 standalone amortization。
- [ ] same accession/period/entity/unit、annual duration、denominator 和 quality 生效。
- [ ] Decimal 28/HALF_EVEN 与 frozen B03 denominator/tolerance 语义生效。
- [ ] Trace 记录 candidate order、拒绝原因、branch、每步 Decimal、cross-check、quality 和 final result，可完全重算。
- [ ] 全部非金融公司 shadow parity；重点 Marriott exact、Pfizer APPROX 与 NOT_MEANINGFUL。
- [ ] 旧 B03 resolver 从 production call graph 移除；expected 只保留 fixture。

**SU 验收**：AC-08～AC-11、AC-23、AC-27 通过；外部 Decimal default 改变不影响结果。

## SU-09｜Legacy Projector、完整 staging bundle 与 pinned PublicationView

- [ ] Projector 输入：完整 legacy 非迁移结果、FROZEN vNext Run、migrated IDs、compiled legacy projection、baseline manifest。
- [ ] 生成完整 publication candidate 所需全部 artifacts，不只 metrics/evidence。
- [ ] 非 migrated rows/evidence exact preserve；migrated fields 按 exact/delta 分类投影。
- [ ] B03 component evidence 多行化和 reconciliation receipt 能精确重建旧聚合字段。
- [ ] 实现 `PublicationView`：对 staging/bundle 读取时 pin 一个 candidate/publication ID；Golden/validation/report 不再隐式读取 `WORKDIR/outputs`。
- [ ] Golden/validation 只消费 frozen expected 和 staging view，不在验证中刷新 expected、不先覆盖正式文件。
- [ ] 将非迁移 repair 移入 run-scoped legacy preparation；report 只消费 candidate view。
- [ ] 生成 validation、report、terminal manifest 和 acceptance inputs，确认任何 WITHHELD 使 candidate BLOCKED。
- [ ] 保留阶段 00–12 对外编号；Bridge 可作为 09 与 10 之间的具名内部阶段，不重排全部 wrapper。

**SU 验收**：AC-14、AC-18、AC-28 的 staging 部分通过；active pointer 尚未切换。

## SU-10｜事务性 Publication、Cutover、旧 producer/旧 checks 迁移与 rollback

- [ ] 实现 immutable bundle、single active pointer、fsync/hash/self-check、CAS/lock、crash recovery、rollback。
- [ ] request ledger 独立 append-only；publication 绑定使用的 ledger prefix/SourceReferences。
- [ ] pointer 在读中切换时，已打开 PublicationView 仍只读一个 publication。
- [ ] compatibility mirrors 与 active hashes 对齐；任意 direct root reader 不冒充原子保证。
- [ ] 任一 failure point 保持/回滚到上一 active；并发只能一位 commit。
- [ ] `latest_run_status` 与 active publication 分离；新 run 失败时用户可见 stale active 情况。
- [ ] migrated legacy write gate `LEGACY_PATH_STILL_ACTIVE`；旧 lodging/B03 production resolver monkeypatch 立即抛错，full flow 仍通过。
- [ ] 删除/生产不可达旧 lodging semantic functions，退役旧 scope/range settings。
- [ ] 对五条旧 lodging validation check 和全部旧 producer 生成 invariant migration receipt；每个旧不变量有 ported/replaced proof，不能因删除 check 缩小验收面。
- [ ] provenance/snapshot checker exact-bind active pointer、bundle、FROZEN Run、review context/decision、Trace、derived assets、publication validation receipt。
- [ ] 在隔离 checkout 真实执行 previous bundle rollback、report、snapshot checker，再切回新 bundle。

**SU 验收**：AC-15、AC-16、AC-18、AC-22、AC-26、AC-28 通过；正式视图只可能是上一完整版本或下一完整版本。

## SU-11｜文档、Acceptance Runner、全量回归与关闭证据

- [ ] 更新 capability contract、interact、business guide、architecture、TESTING、AGENTS、SOP、01/02 方法文档、provenance 文档和 source policy。
- [ ] 修改 `build_readme()` 或稳定 post-processor；不得只手改生成 README。
- [ ] Requirement Snapshot、`catalog/` 和 vNext executable 进入 source closure；active bundle closure 动态 exact-bind。
- [ ] 新增标准库 `tools/run_acceptance.py` 或等价 runner，按规定顺序执行命令，记录原样 argv、interpreter、return code、duration、stdout/stderr digest、关键 artifact hashes 和未运行原因，生成 `outputs/acceptance_receipts/<receipt_id>.json`。
- [ ] runner 不把命令失败吞成报告成功，不把 SKIP/NOT_EVALUATED 写成 PASS，不自行联网以外的隐式副作用。
- [ ] Python 3.9 与默认解释器快速回归；recorded tests 全局 socket blocked。
- [ ] 干净隔离 checkout 完整 Stage 00–11、独立 Stage 12、snapshot checker、semantic/capability alignment、publication/rollback 全部执行。
- [ ] 最终提供 baseline→shadow→staging→active→rollback→active 的 hashes/receipts 和旧路径 call graph。

**SU 验收**：第 9 节全部勾选，真实 acceptance receipt 与关闭说明齐全。

---

# 5. Target State Bridge 摘要

| 用户/审核者看到的行为 | Target State |
|---|---|
| 判断当前展示版本 | 同时读取 `active_publication` 与 `latest_run_status`。active 是当前可用版本；latest run 可能失败/withheld，必须显式显示“更新尝试未发布”，不能把旧 active 冒充最新 run。 |
| 查看常规结果 | 仍能取得完整 legacy-compatible metrics/evidence/coverage/report；内部与正式验收通过 pinned PublicationView 读取一个 publication ID。固定根文件只是 compatibility mirror，terminal 时必须与 active hash 一致。 |
| 查看 B10/B11 | 从结果进入对应 FROZEN Run，看到完整目标表、selected/competing/unresolved、cell 重读、identity、Evidence 和 HUMAN Decision；页面对 filing 文本做安全转义。 |
| AI 输入 | Reader 收到文档全部 table-grid exact set，而不是旧关键词预筛窗口。 |
| AI 数值与 cell 不一致 | Candidate REJECTED；即使文件别处存在正确值也不搜索、不自动修正、不回退旧 parser。publication candidate BLOCKED，上一 active 保持。 |
| 判断酒店 scope | 程序只证明标签和 cell 存在；Comparable/Systemwide/Worldwide 的经济含义由 HUMAN ReviewUnit 批准。 |
| 查看 B03 | Spec、selection policy、candidate order、guards、cross-check denominator、Decimal steps、quality 和结果都能从 Trace 重放。 |
| 非 lodging 公司 | 不调用 AI，继续投影 `N_A_STRUCTURAL`。 |
| 模型不可用 | 新 attempt fail closed；历史 FROZEN Run 无 AI replay；上一 active publication 不变。 |
| WITHHELD | 可以冻结为审计 Run，但整个 migrated publication candidate 不发布；Legacy Projector 不猜 status。 |
| Validation/Report/Publication 失败 | active pointer 不变或原子回滚，不出现混合 metrics/evidence/report/manifest。 |
| 报告生成 | 只读 pinned publication；AI/SEC socket、repair 和 authoritative write 均为 0。 |
| 纠错 | 新建 superseding Run/Decision；旧审计链和旧 bundle 不修改。 |
| rollback | 只切 active pointer 到上一 committed bundle，并重新跑 report/snapshot checker；不启用旧 resolver。 |

建议新增/更新能力契约 anchors：

- `CAPABILITY.reviewed_ai_lodging_extraction`
- `CAPABILITY.single_active_publication_view`
- `BEHAVIOR.ai_reader_receives_metric_neutral_table_set`
- `BEHAVIOR.ai_claim_never_publishes_directly`
- `BEHAVIOR.review_decision_binds_rendered_context`
- `BEHAVIOR.frozen_vnext_run_replays_without_ai`
- `BEHAVIOR.withheld_run_does_not_replace_active_publication`
- `BEHAVIOR.publication_view_pins_one_version`
- `BEHAVIOR.failed_projection_keeps_previous_publication`
- `RESPONSIBILITY.human_approves_poc_lodging_claims`
- 更新 `BOUNDARY.not_production_service`：删除“尚未完成 vNext 切换”这一过期部分，但继续保留无 UI/API/daily scheduler/生产数据库。
- 更新 SEC-only 表述：事实来源仍仅 SEC；远程 AI 若获批，是受控处理器和 filing egress，不是证据来源，也不进入 SEC request ledger。

---

# 6. 预测的代码触点（非承诺）

> 下表基于 `main@c37cecd...` 的当前职责和调用图。真实 diff 应以最小充分边界为准，不要求机械使用相同文件名。

## 6.1 确认会受影响

| 当前文件/边界 | 预计变化 |
|---|---|
| `scripts/sec_pipeline.py` | 接入 run-scoped legacy preparation、vNext Bridge、Artifact/PublicationView；拆出 migrated logic；Stage 11 去 repair；禁用 migrated legacy writes；保留非迁移流程。 |
| `scripts/11_build_report.py` | 只读 pinned active/candidate view；不得触发 repair 或 AI/SEC 网络。 |
| `scripts/12_validate_repair.py` | 对一个 pinned active publication 做终态 gate，并发布/验证包含 vNext closure 的 provenance。 |
| `scripts/validation_provenance.py` | 绑定 Requirement Snapshot、active pointer/bundle、FROZEN Run、review context/decision、Trace、derived assets、publication validation receipt；更新 fault handling。 |
| `tools/check_validation_snapshot.py` | 只解析一次 active pointer，验证 exact bundle、latest/active 关系和 compatibility mirrors。 |
| `tools/check_no_company_literals.py` / 新 semantic audit | 检测全部 vNext executable 中重新出现的 metric/company/industry semantic literal/branch，并生成逐命中 receipt。 |
| 新 `tools/run_acceptance.py` | 顺序执行本 Issue 的真实验收命令并产出不可冒充的 receipt。 |
| `config/metric_applicability.yaml` | 退役 `LodgingKpiExtractor` 旧 route、scope priority、range 语义，或仅保留 profile trait；不能继续驱动旧 resolver。 |
| `config/company_registry.csv` | 原则上只读；traits 投影若需 schema 变化才改，不增加第二家生产 lodging 公司。 |
| `config/validation_source_policy.json` | 加入 Requirement Snapshot、`catalog/`、vNext executable、active publication/acceptance 角色。 |
| `tests/test_sec_pipeline_validation.py` | Artifact/PublicationView、Stage 11/12、legacy-write guard、旧 lodging invariants migration 与 full flow；新测试不应继续全部塞入此单文件。 |
| `tests/test_validation_provenance.py` / light package tests | active pointer/bundle/run/review/trace/receipt exact closure、tamper、missing/extra、postflight rollback。 |

## 6.2 很可能新增

```text
requirements/ai_first_v3_3_1/
  FSD.md
  ISSUE_CONTRACT.md
  decision_register.json

catalog/
  company_traits.yaml
  metrics/B01_revenue.md
  metrics/B03_ebitda_margin.md
  metrics/B10_occupancy.md
  metrics/B11_revpar.md
  disclosures/lodging_kpi_table.md

scripts/vnext/
  canonical.py
  records.py
  states.py
  specs.py
  sources.py
  table_grid.py
  reader_input.py
  ai_adapter.py
  reader.py
  evidence.py
  constraints.py
  review.py
  calculator.py
  projector.py
  publication.py
  replay.py
  render.py

artifacts/vnext/
  runs/<run_id>/...
  reports/<run_id>/...
  latest_run_status.json

outputs/publications/<publication_id>/...
outputs/active_publication.json

tests/vnext/...
```

目录名可调整，但 Requirement、Spec、Source、AI adapter、mechanical Evidence、Review、Calculator、Projector、Publication、Replay 必须可独立测试，不能回到一个新单体函数。

## 6.3 不应成为 AI 通道

- `scripts/sec_http.py` 继续只负责官方 SEC acquisition；AI 使用独立 adapter、allowlist、egress audit。
- `config/sec_config.json` 不承载模型密钥。
- report/validation/provenance 不得隐式调用 AI。

## 6.4 旧路径清理触点

必须调查并在 migration receipt 中逐项处理：

- 旧 lodging keyword/header/table-window/scope/order/cell/range/identity/extractor/repair 函数；
- `apply_p0_repairs()` 对 lodging 的调用；
- B03 `resolve_operating_income_component()`、`resolve_da_component()` 及其 production call graph；
- 五条 lodging validation checks；
- `metric_applicability.yaml` 中旧 extractor route/settings；
- README/report 中仍声明旧 parser/repair 的生成文案。

---

# 7. 文档更新预测

## 7.1 必须更新

| 文件 | 必须反映的变化 |
|---|---|
| `requirements/ai_first_v3_3_1/*` | exact FSD、Issue Contract R2、Decision Register 和 hash 规则。 |
| `architecture.md` | 全表 Reader input、AI/SEC 双网络边界、诚实非沙箱声明、对象状态、ReviewUnit、staging、complete bundle、active pointer、pinned view、report read-only、rollback/replay。 |
| `capability_contract.json` | 新 reviewed AI capability、AI 不直发、context-bound review、withheld 不替换 active、frozen replay、human responsibility、最新/active 区分。 |
| `interact.md` | 酒店审核旅程、untrusted text、active/latest、WITHHELD、stale active、PublicationView、失败/rollback 行为。 |
| `docs/business_user_guide.md` | 怎样判断 active 是否陈旧、怎样看 B10/B11 review context、B03 Trace、何时停止采信 root mirror。 |
| `TESTING.md` | recorded/socket-blocked tests、live 3-run stability、holdout fixture、canonical/Decimal、publication/rollback、acceptance runner、Python 3.9 红线。 |
| `AGENTS.md` | Requirement/Spec/vNext/publication 目录地图、review/freeze/project/publish/replay 路径与权威边界。 |
| `SOP.md` | 保持导航风格，新增 Requirement freeze、AI review、Run freeze、candidate validation、publish、rollback、终态验收动作和权威引用。 |
| `01_SOP_SEC_10公司单年指标计算_直接SEC.md` | 当前直接 repair 流程改为 run-scoped legacy preparation + vNext Bridge + publication。 |
| `02_指标定义_SEC_10公司单年指标.md` | B01/B03/B10/B11 Spec 权威、METH-01、canonical/legacy units、ReviewUnit、evidence grain、compatibility deltas。 |
| `docs/validation_snapshot_provenance.md` | Requirement/source closure、active pointer/bundle closure、latest/active、request ledger prefix、publication validation receipt、最终 acceptance receipt 的非循环引用和 rollback。 |
| `config/validation_source_policy.json` | Requirement Snapshot、catalog、vNext runtime、generated/active/committed bundle、test fixture 和 governance roles。 |
| `README_RUN.md` generator/post-processor | 新批次、review/freeze/publish/rollback/acceptance 命令；不得手改生成文件。 |

## 7.2 评估后更新

- `PR_Checklist.md` / `.github/pull_request_template.md`：记录覆盖 SU、Decision hashes、remote egress approval、live attempts、legacy invariant receipt、publication/rollback evidence；
- `.gitignore`：local secrets、OPEN/FAILED 临时 workspace、provider cache；不能忽略 source closure 内 Requirement/Spec；
- `CIK变更应对方案.md`：只有 SourceReference/superseding Run 改变跨 CIK 用户行为时才改；
- `SEC_metrics_Project_Overview_and_Expert_Guide.md`：仅解释性同步，不得成为运行权威。

无需补造根目录 `README.md`；权威运行入口仍由生成型 `README_RUN.md` 承担。

---

# 8. 测试更新预测

## 8.1 建议新增 `tests/vnext/`

| 测试组 | 核心证明 |
|---|---|
| `test_requirement_baseline.py` | FSD/Issue/Decision hashes、supersedes 单链、旧 baseline 不可复用。 |
| `test_canonical_hashes.py` | duplicate keys、NFC/raw 分离、list/set、`-0`、Decimal limits、semantic runtime versions。 |
| `test_state_model.py` | attempt/run/review/validation/publication 独立状态，FROZEN≠PUBLISHABLE，WITHHELD batch block。 |
| `test_source_records.py` | RawBlob/SourceReference 一对多、existing bytes 引用、missing role/hash mismatch。 |
| `test_table_grid_locator.py` | all tables、merged cells、grid rebuild、locator round-trip、wrong-locator/no-search。 |
| `test_reader_input_manifest.py` | prompt input exact-set、task words不影响 table set、无 semantic prefilter。 |
| `test_spec_compiler.py` | JSON-compatible front matter、ordered DSL、cardinality、tie-break expansion、cycle/depth/node limits、closure。 |
| `test_ai_reader_contract.py` | 单 group 三角色、recorded responses、schema/duplicate key、retry attempts、socket guard、secret scan。 |
| `test_evidence_checker.py` | AI/cell mismatch、local labels、numeric policy、generic identity、禁止语义重解。 |
| `test_review_renderer.py` | complete table、rendered hash、Markdown/HTML/control/bidi/zero-width 注入、无 legacy oracle。 |
| `test_review_binding.py` | unresolved claim 变化、source/spec/context/renderer 变化失效、Decision 单链、freeze TOCTOU。 |
| `test_lodging_slice.py` | Marriott、第二真实布局摘录、第三 holdout、non-lodging zero AI、1% boundaries、whole-batch block。 |
| `test_b03_calculator.py` | selection order、cardinality、D&A 防双计、cross-accession、cross-check denominator/boundaries、Decimal context、Trace。 |
| `test_legacy_projector.py` | full matrix、exact fields、method delta receipt、B03 component grain 和旧聚合重建。 |
| `test_publication.py` | complete bundle、pointer、pinned view、failure points、concurrency、root mirrors、latest/active、rollback。 |
| `test_replay.py` | FROZEN 无 AI replay、缺/tamper asset/decision/semantics fail closed。 |
| `test_report_read_only.py` | socket=0、repair=0、authoritative writes=0、单 PublicationView。 |
| `test_semantic_audit.py` | 全 vNext executable 无业务 literal/branch、旧 producer throw 仍全链通过、invariant migration receipt 完整。 |
| `test_acceptance_runner.py` | 原样命令/返回码/hash、FAIL/SKIP 不能冒充 PASS。 |

## 8.2 必须修改/扩充现有测试

- `tests/test_sec_pipeline_validation.py`：Artifact/PublicationView、matrix/evidence exact set、coverage、Golden、Stage 11/12、旧 lodging check 等价迁移、legacy write guard；
- `tests/test_validation_provenance.py`：Requirement + active bundle/run/review/trace/acceptance exact closure；
- `tests/test_validation_provenance_light_package.py`：light 不能因缺 AI/raw/run assets 冒充 full，不能删 Requirement/Spec 缩小 closure；
- capability alignment：新增 anchors、真实 test anchors、Decision/Requirement paths；
- Golden/compatibility fixtures：B01/B03/B10/B11、Pfizer APPROX、NOT_MEANINGFUL、B10/B11 空字段、method delta、B03 reconciliation；
- previous OK snapshot：Cutover 不得把 Marriott B10/B11 回退为 missing；
- old lodging checks：每条映射到 vNext invariant，不能直接删除；
- AI tests：全部 recorded；真实 model 只进入明确 live shadow receipt。

## 8.3 新增验收场景 AC-18～AC-28

- **AC-18｜Pinned PublicationView**：读取中途切换 active pointer，已打开 view 的所有文件仍来自同一 publication ID。
- **AC-19｜Unresolved claim 变化**：只改变 unresolved competing claim，旧 ReviewDecision 必须失效。
- **AC-20｜错 locator 不全文纠正**：AI locator 指错，但文件别处存在正确值；Checker 必须拒绝。
- **AC-21｜第三 holdout 布局**：实现冻结后加入第三种布局，`scripts/` production tree hash 不变，仅 fixture/recorded locator 变化。
- **AC-22｜旧 resolver 真实退出**：把旧 lodging/B03 resolver monkeypatch 为立即抛错，Cutover full flow 仍通过。
- **AC-23｜有序/集合语义**：`choose_first`、subtract/divide args 或 evidence order 换序改变 semantic hash；真正 set 字段换序不变，重复成员失败。
- **AC-24｜AI 输入 exact set**：全部 table IDs 进入 ReaderInputManifest；修改任务关键词不改变 table set。
- **AC-25｜Review renderer injection**：HTML、Markdown pipe、code fence、zero-width、bidi override 和控制字符不能改变审核页面结构或隐藏 cell。
- **AC-26｜WITHHELD 不替换 active**：FROZEN Run 有任一 APPLICABLE migrated result WITHHELD，candidate BLOCKED，active 保持，latest status 显示失败/withheld。
- **AC-27｜1%/Decimal 边界**：lodging 与 B03 在 0.99/1.00/1.01%、zero/negative、外部 Decimal context 下符合冻结语义。
- **AC-28｜完整版本与 rollback**：active bundle 覆盖 metrics/evidence/coverage/Golden/validation/report/manifest/provenance；真实 rollback 后 report/snapshot checker 通过。

## 8.4 最终必跑层级

1. Python 3.9 与默认解释器快速 unittest；
2. recorded vNext tests，全局 socket blocked；
3. provenance 与 light-package 负例；
4. capability alignment；
5. company identity/scalability + semantic audit；
6. staging Golden、repair validation、matrix/evidence exact set、method delta/reconciliation receipts；
7. live lodging Reader frozen source/prompt 连续 3 次稳定；
8. 干净隔离 checkout 完整 Stage 00–11；
9. 单独 Stage 12；
10. snapshot checker；
11. Cutover old-resolver-throws full flow；
12. previous publication rollback→report→snapshot checker→new publication restore；
13. `tools/run_acceptance.py` 生成最终 receipt。

---

# 9. Acceptance Checklist

## 9.1 Requirement、baseline、schema 与 canonical runtime

- [ ] exact FSD SHA 为 `1cf091812629648095119692c1742d12015e1012ccabf2173820e585e1d42b2b`，Issue Contract/Decision Register hashes 已落盘并进入 source closure。
- [ ] 新 baseline 明确基于 `main@c37cecd...`，未把 `source_commit=7dee...+dirty` 的旧 manifest 冒充精确 baseline。
- [ ] Requirement/Decision 改动会使旧 closure/approval/publication 失效。
- [ ] `RAW_BLOB` 等所有 record type 和对象状态严格校验。
- [ ] duplicate JSON key、unknown field、NaN/Infinity、lone surrogate、超限 Decimal fail closed。
- [ ] object/list/set/order/Unicode/`-0`/fixed-point 规则按契约运行。
- [ ] 外部修改 Decimal default context 不影响 B03/identity。
- [ ] semantic runtime version 变化进入 closure；无语义 code fingerprint 只影响 audit hash。
- [ ] Python 3.9 兼容，无未声明第三方依赖或 3.10/3.11 API。

## 9.2 AI 输入、attempt 与 Evidence（AC-01、02、06、20、24、27）

- [ ] ReaderInputManifest 覆盖目标文档全部 tables，顺序/hash exact；无关键词/scope prefilter。
- [ ] 改变任务词不改变 input table exact set。
- [ ] AI claimed `73.1%`、locator cell=`71.3%` 时 Candidate REJECTED，未采用 `71.3%`。
- [ ] AI locator 不存在时 REJECTED；正确值在别处也不全文搜索。
- [ ] lodging identity 由 Spec generic constraint 执行，0.99/1.00/1.01% 边界正确。
- [ ] AI transport 与 SEC transport 分离；attempt 独立留痕，payload/response hash 可核对。
- [ ] recorded tests socket blocked；无 secret 落入 artifacts/outputs/report/review。
- [ ] live frozen source/prompt 连续 3 次产生相同 review_unit_hash 和 compatibility result。
- [ ] AI 不可用时不触发旧 resolver，active publication 不变。

## 9.3 ReviewUnit 与 Renderer（AC-03～05、12、19、25、26）

- [ ] ReviewUnit 覆盖三角色、selected/competing/unresolved、Evidence、Spec/source、canonical/rendered context。
- [ ] 只改变 unresolved claim、locator、source、Spec、renderer semantic version 或 rendered bytes，旧 Decision 失效。
- [ ] 同一 review unit 两个并列有效 Decision fail closed；supersedes 单链可审计。
- [ ] ReviewDecision 只批准 claims，不改 Candidate、不赋值 publication。
- [ ] review.md 展示完整目标表/全部相关角色和年度，不显示旧 resolver 答案。
- [ ] untrusted filing 的 Markdown/HTML/control/zero-width/bidi 注入不能误导页面。
- [ ] freeze 前重新验证全部 binding，冻结后不可写。
- [ ] FROZEN+WITHHELD 可审计但不能 PUBLISHABLE；active 与 latest run 状态明确分开。

## 9.4 B01/B10/B11 Slice 与泛化（AC-07、13、21）

- [ ] B01 structured selection 没有复制第二套 resolver，字段 exact parity。
- [ ] 一次 lodging extraction 同时产生 Occupancy/RevPAR/ADR。
- [ ] non-lodging AI call=0，`N_A_STRUCTURAL` 保留。
- [ ] 当前 Marriott + 第二真实布局摘录通过同一 production code。
- [ ] 第三 holdout 在实现冻结后加入，`scripts/` production hash 不变。
- [ ] B10/B11 exact compatibility fields（含空 fiscal_year/form、confidence=0.85）保持；formula/notes delta 有逐 cell receipt且诚实。
- [ ] 无有效 HUMAN Review 时 publication candidate 整体 BLOCKED。

## 9.5 B03（AC-08～11、23、27）

- [ ] `choose_first`、concept priority、cardinality、tie-break、guards 和 fallback 全在 compiled Spec/Trace。
- [ ] combined D&A=100、standalone amortization=20 时使用 100，不是 120，quality=EXACT。
- [ ] Revenue/OI/D&A 跨 accession/period/entity/unit 时 B03 WITHHELD。
- [ ] CostsAndExpenses cross-check denominator 与 0.99/1.00/1.01% 边界符合冻结规则。
- [ ] cross-check 不存在时继续并记录 `CROSS_CHECK_UNAVAILABLE`；不兼容时不使用。
- [ ] annual duration 不在 300–400 或 denominator=0 时 `NOT_MEANINGFUL` 可见。
- [ ] OI reconstruction=APPROX；D&A exact composition 不降级。
- [ ] B03 可从 Spec、Observation IDs、semantic runtime versions 和 Trace 完全重算。
- [ ] Marriott/Pfizer 与全部非金融公司 parity 通过。
- [ ] 旧 B03 production resolver 退出；monkeypatch throw 不影响 full flow。

## 9.6 Projector 与 compatibility

- [ ] Projector 输出完整 matrix/evidence/coverage/Golden/validation/report bundle，不丢非迁移指标。
- [ ] 非 migrated rows/evidence exact preserve，顺序稳定。
- [ ] B01/B03 metrics exact parity；B10/B11 exact fields 和允许 method deltas 符合契约。
- [ ] B03 component evidence 一行一 source，reconciliation receipt 能 exact 重建旧 `;`/`+` 聚合。
- [ ] derived metric validation 通过 component evidence + Trace 重算 final ratio，不要求 component row 伪装 final ratio。
- [ ] projection manifest 绑定 legacy input、Requirement/Decision、vNext content、migrated IDs、candidate artifacts 和 gate results。
- [ ] WITHHELD 不被 Projector 猜成 Legacy status，也不进入 active candidate。

## 9.7 Publication、Cutover、旧不变量与 rollback（AC-14～18、22、26、28）

- [ ] publication bundle 覆盖全部用户可见 artifacts 与 pre-commit validation artifacts；最终 acceptance receipt 位于 bundle 之外并引用 active/snapshot，request ledger 作为独立 append-only chain 绑定其使用前缀。
- [ ] active pointer 是唯一 commit point，PublicationView 只解析一次并 pin ID。
- [ ] pointer 读取中途切换，已打开 view 不混读。
- [ ] 任一 write/fsync/hash/Golden/Validation/report/provenance/mirror 失败只保留或回滚到上一 active。
- [ ] concurrent publishers 无 lost update、双 active 或半成品成功态。
- [ ] root compatibility mirrors 在 terminal 时与 active hash 一致，且文档未声称任意 direct reader 具备组原子保证。
- [ ] latest run 失败/withheld 时用户能看到 active 仍是旧版本。
- [ ] `LEGACY_PATH_STILL_ACTIVE` 能阻止 migrated legacy write。
- [ ] 旧 lodging/B03 resolver monkeypatch throw，Cutover full flow 仍通过。
- [ ] 每个旧 lodging producer/check 有 invariant migration receipt；没有静默缩小 validation。
- [ ] 报告 socket=0、repair=0、authoritative write=0。
- [ ] 真实 rollback→report→snapshot checker→restore 通过，不启用旧 parser。

## 9.8 Replay、provenance、文档与最终 gate

- [ ] FROZEN Run 无模型凭据/网络可 replay 相同 Result/content hash。
- [ ] missing/tampered asset、Decision、review context、Trace、Spec、runtime semantics 或 source binding fail closed。
- [ ] active provenance exact-bind Requirement、pointer/bundle、Run、review、Trace、derived assets、publication validation receipt 和 ledger prefix；最终 acceptance receipt 独立引用该 snapshot，不进入 bundle 自哈希。
- [ ] OPEN/FAILED/staging/non-active artifact 不能冒充 terminal active。
- [ ] capability contract、interact、business guide、architecture、TESTING、AGENTS、SOP、01/02 方法、provenance、source policy 全部同步。
- [ ] README_RUN 来自 generator/post-processor。
- [ ] Python 3.9/default tests、recorded socket-blocked tests、provenance、alignment、semantic audit、staging、live stability 全部通过。
- [ ] 干净隔离 checkout 完整 Stage 00–11、独立 Stage 12、snapshot checker 通过。
- [ ] acceptance runner 记录原样命令、真实 return code/hash、未运行原因；没有用 light/shadow/旧 manifest 冒充 full。

**Issue Done 的唯一判定**：AI 真正吸收了完整表格布局和措辞变化；Checker/prompt builder/Projector/renderer 没有重新实现行业语义；B03 由确定性 Spec runtime 驱动；Review 绑定 reviewer 实际看到的不可变上下文；旧 producer 与旧不变量完成迁移；active publication 在失败、并发、withheld 和 rollback 下始终是一个完整可审计版本。

---

# 10. 风险与开放问题

> 本节不拆子 Issue。除 D-01 的真实 provider/egress 批准外，关键实现选择已经由本 Issue 给出默认裁决，开发者不得自行选择相反语义。D-01 未批准不阻塞 recorded/schema/shadow 基础开发，但阻塞真实模型 Cutover。

| ID | 级别 | 风险/问题 | 本 Issue 裁决 / 处理 |
|---|---|---|---|
| D-01 | P0 外部批准 | 本地还是远程模型；filing 是否允许外发 | provider-neutral adapter；远程默认关闭。真实 Cutover 前 Decision Register 批准 provider/model/host/region/retention/data-use/payload；否则只能 recorded/local。 |
| D-02 | P0 | timeout/无凭据/限流/非法 JSON/schema | attempt FAILED、Run 可 FAILED/FROZEN-withheld、candidate BLOCKED；不回退旧 resolver，active 不变。 |
| D-03 | P0 | lodging 一项失败能否部分发布 | 已解决：whole migrated publication candidate BLOCKED；不做部分发布，Projector 不猜 WITHHELD status。 |
| D-04 | P0 | 两个固定 CSV 无法对任意 reader 组原子 | 已解决：immutable complete bundle + atomic active pointer + pinned PublicationView。root 仅 compatibility mirror，任意 direct reader 不在原子保证内。 |
| D-05 | P0 | strict parity 与新 evidence/method truth 冲突 | 已解决：业务/兼容字段 exact；B10/B11 方法字段声明式 delta；B03 component evidence 多行 + exact reconstruction receipt。 |
| D-06 | P0 | reviewer 到底批准什么 | 已解决：批准整个 ReviewUnit，绑定 selected/competing/unresolved、Evidence、Spec/source 和实际 rendered context；Decision 单链。 |
| D-07 | P0 | AI 输入可能被旧 parser 预筛 | 已解决：全部 table-grid exact set；ReaderInputManifest；行为+semantic audit；模型装不下则阻塞，不引入关键词筛选。 |
| D-08 | P0 | 5% legacy vs 1% FSD | 已解决：METH-01 明确批准 1%，当前 anchor 不变，边界测试和文档显式。 |
| D-09 | P0 | Run/FROZEN/Validation/Publication 混用 | 已解决：对象状态拆分；FROZEN≠PUBLISHABLE；active/latest 分离。 |
| D-10 | P1 | YAML/SDK/Schema 依赖破坏标准库/Python 3.9 | JSON-compatible front matter + explicit validators + provider-neutral adapter；新依赖需 Decision 和锁定。 |
| D-11 | P1 | table-grid merged cells/footnotes 不稳定 | content-addressed transform、semantic version、round-trip fixtures、ambiguous fail closed。 |
| D-12 | P1 | old oracle 长期存活/污染 review | shadow 过渡后 production 路径删除；expected 固化 fixture；review 不显示旧答案；throw test。 |
| D-13 | P1 | artifact 体积与 GC | RawBlob 引用既有 bytes；derived content-addressed；Phase 1 无自动 GC，保留 FROZEN/committed history。 |
| D-14 | P1 | AI network 与 SEC-only 文案冲突 | 数据事实来源仍 SEC；AI 是独立受控处理器/egress，不是 evidence source、不写 SEC ledger。 |
| D-15 | P1 | Stage 11 repair/report 强耦合 | 全部生成在 run-scoped candidate；非迁移 repair 前置；report 只读 pinned view。 |
| D-16 | P1 | review/freeze/publish race | Decision append/supersedes、freeze revalidation、publisher lock+CAS、failure tests。 |
| D-17 | P1 | review.md 过宽/被 filing 注入 | canonical context + renderer hash/version；安全转义、不可见字符可视化；可分页但不得语义裁剪。 |
| D-18 | P1 | FSD/Issue/Decision 同名漂移 | Requirement Snapshot + exact hashes + source closure；Issue 评论不作 runtime truth。 |
| D-19 | P1 | publication 只保护 metrics/evidence，其他 artifacts 混版 | complete user-visible bundle；request ledger 独立；view pin ID。 |
| D-20 | P1 | AI 非确定性导致一次侥幸 parity | recorded deterministic tests + live frozen source/prompt 连续 3 次相同 review_unit_hash。 |
| D-21 | P1 | 只有 Marriott，泛化自证 | current + 第二真实布局测试摘录 + implementation-freeze 后第三 holdout；不扩生产 registry。 |
| D-22 | P1 | 旧 validation checks 被删除造成验收缩水 | legacy invariant migration receipt；按不变量 port/replace，不按 check 数量。 |
| D-23 | P1 | Decimal 默认 context/排序隐藏漂移 | explicit localcontext、ordered DSL、semantic runtime versions、边界测试。 |
| D-24 | P1 | AI 模块被误称为安全沙箱 | 明确收窄为调用图/依赖/egress 约束；不声称同进程强隔离。 |
| D-25 | P2 | 无 CI，关闭时测试记录易失真 | acceptance runner 记录真实命令/return code/hash；仍不宣称 CI。 |

---

## 关闭说明模板

关闭本 Issue 时必须附：

1. Requirement Snapshot、Decision Register 和最终 hashes；
2. 真实 diff、删除/不可达路径、production call graph 与 `LEGACY_PATH_STILL_ACTIVE` 证据；
3. old lodging functions/checks → vNext invariant migration receipt；
4. baseline → recorded shadow → live 3-run shadow → staging → active publication compatibility receipts；
5. HUMAN ReviewUnit/Decision 示例，含 rendered context hash 和注入防护证据；
6. B03 Spec/Trace/Decimal/reconciliation 示例；
7. publication failure/concurrency/pinned-view/latest-vs-active 证据；
8. previous bundle rollback→report→snapshot checker→restore 的真实隔离运行证据；
9. 完整 Stage 00–12、snapshot checker、capability/semantic alignment 和 acceptance runner 的原样命令、return codes、artifact hashes；
10. 未完成任何必选项时保持 Issue open，不得写成“后续优化”。
