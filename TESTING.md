# SEC_metrics 测试与验证流程

本文件是测试策略、真实命令、full/light 边界、snapshot provenance 和测试副作用的权威入口。所有命令默认从仓库根目录执行；完整阶段顺序以 `README_RUN.md` 为准。

## 1. 测试原则

- 测行为与契约，不用脆弱的源码字符串、固定行数或单个 happy path 替代不变量。
- 默认使用固定 fixture、临时工作区和本地 evidence，保持确定性与隔离。
- 单元级成功不能替代 Golden、repair gate、snapshot checker 或完整阶段场景；light 不能替代 full。
- Bug 修复先加入稳定最小复现，再修实现；跨阶段状态事故还要补 scenario 证据。
- 完整性修复至少考虑：删行、重复、多余集合、字段值、CSV 行形状、顺序/版本、跨 accession/document、symlink/hardlink、publication failure、post-run tamper。
- 任何会联网或覆盖 `evidence/`、`outputs/`、README、报告的命令，都应在干净隔离 checkout 中执行，并先确认 SEC identity。
- 测试记录必须包含原样命令、实际结果、证据路径和未运行原因；不得把预期写成已通过。

## 2. 环境与前提

- 运行时边界为 POSIX 本地文件系统上的 Python 3.9+，当前代码只导入标准库和本地模块。
- 快速回归至少在 Python 3.9 与当前默认解释器各运行一次；仓库没有 CI 自动维护该承诺。
- 建议设置 `PYTHONDONTWRITEBYTECODE=1`，避免生成 `__pycache__`。
- live SEC 命令读取 `config/sec_config.json`，只允许官方 SEC 域名，并写 request ledger 与 raw evidence。
- stage 11 可能在 C04 本地 AuditorName 材料不足时条件式联网；示例 organization/contact email 不能用于合规 live run。
- stage 12 full 模式要求 provenance source-input closure clean。closure 内 tracked、staged 或 untracked 改动都会在主 gate 前失败；生成的 evidence/outputs 不在 source closure 内。

## 3. 测试与验收层级

| 层级 | 命令 / 入口 | 网络 | 仓库写入 | 通过条件 | 不能替代 |
|---|---|---:|---:|---|---|
| 快速回归 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'` | 否 | 测试设计上只写 temp dir | 全部通过；skip 数和原因记录 | full evidence、Golden、完整场景 |
| Provenance 专项 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_validation_provenance` | 否 | temp Git repo | clean/full/light、dirty source、equivalent tree、artifact tamper、postflight fail-closed、README idempotency 通过 | 业务指标/SEC evidence |
| 能力文档对齐 | `python3 tools/check_capability_contract_alignment.py`；PR 再加 `--base-ref <base>` | 否 | 否 | Git/anchor/path/symbol/tombstone/request-history 机械规则通过 | claim 语义 |
| 静态扩展性 | `python3 tools/check_no_company_literals.py` | 否 | 覆盖 scalability audit | 无禁止 identity literal | 指标正确性 |
| Golden | `python3 scripts/10_run_golden_assertions.py` | full 可能联网 | 覆盖 Golden，可能追加 evidence/log | exact assertion set 唯一且全 PASS | repair/provenance/外部验收 |
| Repair gate | `python3 scripts/12_validate_repair.py` | 否 | 覆盖 validation/audit、manifest、report、provenance | 原有 full/light terminal 条件通过，且 sidecar publication/self-check 成功 | live 采集、外部接受 |
| Snapshot 复核 | `python3 tools/check_validation_snapshot.py` | 否 | 否 | source closure clean/等价；artifact key set/hash/size 匹配 | 重新运行 Golden/repair |
| Report build | `python3 scripts/11_build_report.py` | 条件式 | 覆盖多个 outputs、manifest、report、README；删除旧 sidecar | 命令完成只证明报告构建完成 | 独立 stage 12 |
| Live smoke | `python3 scripts/00_smoke_test_sec_access.py` | 是 | request log/raw response | 官方 SEC 请求满足脚本判据 | 后续指标与验证 |
| 完整场景 | 按 README 执行 00–11，再执行 12 和 checker | 是 | 大量 artifact | 每阶段成功；Golden/repair/provenance 全通过 | 外部审计接受 |

## 4. 快速回归覆盖

`tests/test_sec_pipeline_validation.py` 当前覆盖的主要边界包括：

- `LIGHT_REVIEW_MODE`、`WORKSPACE_INCOMPLETE`、marker 与五态 validation；
- metrics matrix 配置派生 exact key set、coverage exact join、删一补重复/未知；
- full Golden assertion exact set、stratified audit deterministic exact sample；
- 8-K request-bound submissions/fiscal inventory/raw hdr/primary/events/component evidence 完整链；
- mutable submissions 最新成功 200、filing-bound conflicting bodies、primary fallback 与零值 scan evidence；
- Basel threshold 排除、actual ratio selection、iXBRL scale/sign/parser route；
- captive finance、RPO/cRPO、第 11 家公司和 company-identity AST scanner；
- 10-K/A 到同期间原始 10-K full-instance fallback；
- C03 PeoTotalCompAmt、C04 current/prior AuditorName 原始重放与同 CIK period；
- numeric evidence 对 value/unit/period/accession/source/concept/method 的完整匹配；
- portable locator 的多 anchor、hash/URL/accession/document identity、clone relocation 与跨 root 拒绝；
- request-log manifest key/type、CSV 精确列宽、Git HEAD/base 有序前缀、并发 publication、downstream/sidecar 反向覆盖；
- no implicit redirect、read timeout/IncompleteRead、persistence failure observation、symlink/hardlink/UUID path 注入；
- report/manifest publication 顺序、stale audit 隔离与 failure propagation；
- capability contract 的 HEAD blob、working bytes、anchor/directive grammar、test symbol 和 Git workspace boundary。

`tests/test_validation_provenance.py` 新增独立覆盖：

- clean Git source closure + full manifest/artifact round trip；
- source path 的 unstaged/staged/untracked dirty 拒绝；
- source tree byte mutation 与 artifact SHA-256 mutation；
- artifact commit/merge commit 改变 SHA、但 source-input tree 等价时 warning；strict 模式仍拒绝 commit mismatch；
- 显式 light package 无 Git 的 `LIGHT_PACKAGE_NO_GIT` sidecar；
- provenance postflight 失败时 manifest→FAILED、report→NO-GO；regular sidecar 删除，unsafe alias 保持不可验收；
- generated README 的 marker-delimited route injection 幂等。

这些测试证明 provenance helper 的内容绑定，不证明 SEC 指标方法或完整 00–12 live handoff。

## 5. Full、light 与不完整 workspace

`validation_package_mode()` 的既有分类保持：

1. `evidence/`、request log 和 concept inventory 形状存在时进入 `FULL_VALIDATION` 初始分类；required-input gate 继续逐项判断 domain evidence。
2. 缺 full materials 且根目录有 `LIGHT_REVIEW_PACKAGE.marker` 时进入 `LIGHT_REVIEW_MODE`。
3. 缺 full materials 且无 marker 时为 `WORKSPACE_INCOMPLETE`。

Provenance 叠加规则：

- full stage 12 必须在 Git checkout 中捕获 clean source closure；
- light 无 Git 时，对随包可见 source files 计算 deterministic tree digest并标为 `LIGHT_PACKAGE_NO_GIT`；
- workspace incomplete 或原有 gate 失败不发布 success sidecar；
- light sidecar只证明随包 bytes，不能补足 Git history 或 raw evidence。

## 6. Snapshot provenance 测试不变量

### 6.1 Source closure

当前 policy 覆盖：`scripts/`、`tools/`、`config/`、`tests/`、能力契约、指标定义、AGENTS/SOP/TESTING/architecture/interact、business guide 和两个稳定概念/provenance 文档。

测试必须证明：

- path set 来自 `git ls-files`，不是目录当前剩余文件自证；
- unstaged、staged 和 untracked source path 均阻断；
- symlink、missing/non-regular source 失败；
- digest 对排序后的 path、byte length 与 per-file SHA-256 records 计算；
- stage 12 运行前后 HEAD、tree digest、file count 与 checkout status 不变。

### 6.2 Artifact closure

full 至少绑定 manifest、report、README、Golden、metrics/evidence/coverage/events、request log/manifest 与 refreshed validation artifacts。light 绑定随包集合。

测试必须证明：

- sidecar artifact key set 与 manifest 推导 expected set 完全一致；
- 缺 key、多余 key、非法 digest schema、size mismatch 和 SHA-256 mismatch 均失败；
- manifest run_id/mode/result/source_commit 与 sidecar identity 一致；
- sidecar 本身不自哈希，避免循环 identity。

### 6.3 Commit 语义

- 同一次 stage 12 publication：HEAD 必须完全相同；
- 后续 checker：commit 相同为直接通过；commit 不同但完整 source tree 等价只产生 warning；tree 不同硬失败；
- 不允许仅凭 `manifest.source_commit` 的 `+dirty` 后缀推断 source 安全或不安全。

## 7. 写入副作用

### 7.1 Stage 11

- 首先删除可安全识别的旧 regular `outputs/validation_snapshot_provenance.json`；alias/非 regular 路径在修改新 artifact 前失败；
- 执行 portable migration、bounded repair、coverage/audit/manifest/report/README；
- 可能条件式追加 C04 SEC evidence/request rows；
- 最后幂等注入 README role routes；
- 不发布 terminal snapshot provenance。

### 7.2 Stage 12

- 首先删除可安全识别的旧 regular sidecar；alias/非 regular 路径直接失败；
- 在运行原有 gate 前捕获 clean source snapshot；
- 原有逻辑写 implementation/spec/stub/stratified/scalability/repair、manifest 和报告；
- 只有 full/PASSED 或 light/PASSED_WITH_CAVEATS 才计算并发布 artifact digests；
- sidecar 原子写入后必须重新读取和自验；
- postflight 失败时删除 regular sidecar；unsafe alias 保持不可验收；manifest 改为 FAILED、报告改为 NO-GO，并非零退出。

### 7.3 Snapshot checker

只读。它不会修复、重签或更新任何 artifact；失败后必须回到 source/run 重新生成，不能手工改 expected digest。

### 7.4 其他现有副作用

- `check_no_company_literals.py` 覆盖 `outputs/scalability_audit.csv`；
- full Golden 可能访问 companyconcept、追加 request log/raw evidence，并覆盖 Golden outputs；
- stage 11/12 不是只读检查；执行后必须检查 `git status --short`。

## 8. 按变更类型选择测试

| 变更类型 | 最低证据 | 追加证据 |
|---|---|---|
| 纯工作流文档 | JSON 解析、capability alignment、`git diff --check` | 文档引用具体代码行为时跑相关快速回归 |
| Provenance source path/schema | provenance 专项 + 快速回归 | 临时 Git repo 负例矩阵、stage wrapper scenario |
| 普通 Python 逻辑 | 快速回归 | scalability；涉及指标/validation 再跑 Golden/repair/checker |
| 公司/CIK/profile/extractor 配置 | 快速回归、第 11 家 fixture、scalability | 隔离 checkout 受影响阶段、Golden、repair、checker |
| parser/期间/evidence/CSV schema | 快速回归 + 受影响阶段 | 隔离完整场景、artifact diff、provenance |
| verdict/manifest/report | 快速回归 + repair + provenance | failure propagation、postflight fail-closed、stage 11 后显式 stage 12 |
| HTTP client/URL | persistence/timeout/redirect/alias/request-log tests | 有效身份 live smoke 与场景 |
| 仅报告/README 文案 | generator或post-processor tests | 若跑 stage 11，随后跑 stage 12/checker |

纯文档变更不强制联网重跑 00–11；不得为了“全绿”无谓覆盖已审计 evidence。但 source closure 内文档变更会使旧 snapshot checker 失败，这是预期行为：更新验收契约后需要新的 provenance 才能声明当前 source 等价。

## 9. 推荐执行顺序

### 普通代码改动

1. 快速回归。
2. provenance 专项（涉及 source/artifact/terminal publication 时必跑）。
3. capability alignment 和 scalability gate。
4. 受影响 Golden/阶段场景。
5. stage 12 repair gate。
6. `tools/check_validation_snapshot.py`。
7. 检查 `git status` 与 artifact diff。

### 数据采集、阶段 handoff 或 schema 改动

1. 创建干净隔离 checkout。
2. 确认有效 SEC identity 和 scope。
3. 按 README 完整执行 00–11。
4. 显式执行 stage 12。
5. 运行 snapshot checker。
6. 核对 metrics/evidence/coverage/report/request/provenance diff。

### 纯文档同步

1. 验证 JSON 和 capability anchors。
2. 运行 capability checker；PR 场景加真实 base。
3. 运行 provenance 专项测试，因为 source closure policy/文档引用可能变化。
4. 运行被引用行为的相关快速回归。
5. 记录没有执行 live/full 的原因和影响。

## 10. 失败定位

- provenance checker：先看 missing sidecar/schema/identity；再看 dirty source/tree mismatch；最后定位具体 artifact path 的 size/SHA mismatch。
- unittest：从失败 method 回到 helper/fixture；不得改 expected 掩盖回归。
- Golden：看 assertion expected/actual/evidence path/notes。
- Repair：先读 manifest，只打开本轮 refreshed audit；再看 `check_id/status/details`。
- 指标/evidence：先核对 matrix exact key set，再 join evidence；8-K 继续顺向检查 ledger→submissions→inventory→raw→events→components。
- request：先验证 request-log manifest、Git prefix、downstream/sidecar 反向覆盖，再看 URL/status/UA/retry/error/body/header/hash。
- light：确认 marker、manifest mode/result、sidecar checkout status 和缺失材料；禁止把 skipped/NOT_EVALUATED 写 PASS。

## 11. 新增或修改测试

- 行为 Bug 必须先有最小复现。
- 跨阶段累计状态、artifact handoff 或 publication 顺序问题必须有 scenario 级回归。
- source closure 新增路径时至少加入：clean、dirty、untracked、tree-equivalent commit 和 byte-mismatch 用例。
- artifact closure 新增路径时至少加入：missing、unexpected、size/hash tamper 用例。
- 不为薄 wrapper 重复写同构测试；wrapper 只测试它新增的 invalidation、preflight、postflight 和 failure propagation。
- 测试职责改变时同步本文件和 capability contract。

## 12. 已知高价值缺口

- `validation_package_mode()` 的 `FULL_VALIDATION` shape 仍缺少独立临时工作区单元测试。
- provenance helper 已有独立 temp Git tests，但尚无录制 SEC fixture 驱动的 stage 00–12 离线 scenario，不能证明完整 handoff。
- 当前 source closure 是显式 path policy；尚无自动检查证明所有未来运行/验收输入都已登记，新增关键路径依赖 code review。
- sidecar 是本地自证明，不是外部签名、透明日志或 WORM；尚无组织级发布签名/attestation。
- postflight fail-closed 会重写 manifest/report，但不回滚 stage 12 已写的其他 artifact。
- Git guard 与后续 Git CLI 非原子，仍有主动同 UID namespace TOCTOU 边界。
- mock transport 尚未覆盖 User-Agent 与完整 retry/backoff 矩阵。
- 8-K expected replay 与生产路径共用 item parser，不是未见格式的独立 oracle。
- 仓库无 CI；所有双解释器、full scenario、capability alignment 和 provenance 检查依赖人工执行。
