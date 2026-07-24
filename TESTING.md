# SEC_metrics 测试与验证流程

本文件是项目测试策略、真实命令、full/light 边界和测试副作用的权威入口。所有命令默认在仓库根目录执行；完整阶段顺序以 `README_RUN.md` 为准。

## 1. 测试原则

- 测行为与契约，不用脆弱的源码字符串或固定数量断言替代真实结果。
- 默认使用固定 fixture、临时工作区和本地 evidence，保持确定性与隔离。
- 单元级成功不能替代 Golden、repair gate、snapshot checker 或完整阶段场景；light review 不能替代 full validation。
- 新增测试前先说明它覆盖的真实缺口；避免为 13 个薄 wrapper 重复编写同构测试。
- Bug 修复先加入能稳定复现的最小回归，再修实现；跨阶段状态事故还需要场景级回归。
- 任何会联网或覆盖 `evidence/`、`outputs/`、报告的命令，都应在干净且隔离的 checkout 中运行，并在执行前确认配置。
- 测试记录必须包含原样命令、结果、证据路径和未运行原因；不能把预期结果写成已通过。

## 2. 环境与前提

- 运行时兼容边界为 POSIX 本地文件系统上的 Python 3.9+，当前代码只导入标准库和本地模块；快速回归至少在 Python 3.9 与当前默认解释器各运行一次。
- 仓库没有 `pyproject.toml`、requirements、tox 或 CI workflow；Python 3.9 下限由本测试契约和双解释器回归维护，不代表已有 CI 自动执行。
- 快速测试建议设置 `PYTHONDONTWRITEBYTECODE=1`，避免在仓库生成 `__pycache__`。
- live SEC 命令读取 `config/sec_config.json`，只允许官方 SEC 域名，并写入请求日志和 raw evidence。阶段 11 也可能在 C04 AuditorName 本地材料缺失时条件式联网。
- 当前 `config/sec_config.json` 的联系邮箱是示例值；任何可能联网的命令（包括上述阶段 11 条件分支）运行前，必须由运行负责人换成有效 organization/contact email。
- stage 12 full 模式要求 provenance source-input closure clean；closure 内 tracked、staged 或 untracked 改动会在主 gate 前失败。生成的 evidence/outputs 不属于 source closure。

## 3. 真实测试与验证层级

| 层级 | 命令 / 入口 | 网络 | 仓库写入 | 通过条件 | 不能替代 |
|---|---|---:|---:|---|---|
| 快速回归 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'` | 否 | 测试设计上只写临时目录 | unittest 全部通过；允许的 skip 必须在记录中说明 | full evidence、Golden、完整阶段 |
| Provenance 专项 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_validation_provenance tests.test_validation_provenance_light_package` | 否 | 只写临时目录和临时 Git 仓库 | source policy schema/角色、SOP 权威引用、`01_SOP...md` dirty 负例、clean/full/light、缺 acceptance source、equivalent tree、artifact tamper 与 postflight fail-closed 回归通过 | 业务指标、Golden、SEC evidence |
| 能力文档对齐 | `python3 tools/check_capability_contract_alignment.py`；PR 再加 `--base-ref <base>` | 否 | 否 | 清除会重定向仓库的 Git 环境变量并禁用 replacement refs 后，证据路径存在于 HEAD、是 regular blob 且工作树 bytes 未偏离 HEAD；anchor grammar/唯一性、type/status 枚举、null anchor 的 `untested_reason`/`pending_since`、`file::symbol` 与 Markdown directive 均合法；跨 base tombstone 不删除/复用，base 与 HEAD 的每条 request row 严格匹配其 current/legacy CSV schema，legacy row 独立规范化为 portable 完整字段，current row 逐字段保留有序前缀且只尾部追加 | claim 语义与证据强度判断 |
| 静态扩展性 gate | `python3 tools/check_no_company_literals.py` | 否 | 是，覆盖 `outputs/scalability_audit.csv` | 无禁止 identity literal，进程退出 0 | 指标正确性、场景回归 |
| Golden | `python3 scripts/10_run_golden_assertions.py` | full 模式会联网；light 不联网 | full 模式覆盖 Golden outputs，并可能追加 evidence/log | 所有适用 assertion PASS；light 只能得到受限完整性结果 | repair gate、snapshot checker、外部验收 |
| Repair / validation gate | `python3 scripts/12_validate_repair.py` | 否 | 是，覆盖多个 validation/audit outputs、run manifest、报告与 provenance sidecar | 原有 full/light terminal 条件通过，且 source/artifact provenance publication/self-check 成功 | live 数据采集、完整场景 |
| Snapshot 复核 | `python3 tools/check_validation_snapshot.py` | 否 | 否 | source closure clean/等价；artifact key set、SHA-256 与 size 匹配 | 重新运行 Golden/repair、外部审计 |
| Report build | `python3 scripts/11_build_report.py` | 条件式：C04 AuditorName 本地材料缺失时联网 | 是，先使旧 provenance 失效，再应用 repair；可能追加 SEC evidence，并重建 outputs、报告和 `README_RUN.md` | 命令完成只证明产物已生成 | 独立阶段 12 gate |
| Live smoke | `python3 scripts/00_smoke_test_sec_access.py` | 是 | 是，写 request log 与 raw response | 官方 SEC 请求满足脚本判据 | 后续指标与验证 |
| 完整场景 | 按 `README_RUN.md` 从 `00` 运行到 `11`，再运行 `12` 和 snapshot checker | 是 | 是，大量 evidence/outputs/report | 每阶段成功，Golden、repair gate 与 provenance 均通过 | 外部审计接受 |

## 4. 快速回归覆盖

当前 `tests/test_sec_pipeline_validation.py` 覆盖：

- `LIGHT_REVIEW_MODE` 与 `WORKSPACE_INCOMPLETE` 的工作区形状和 marker 行为。
- light snapshot、fixture 与 metrics matrix 篡改检测。
- metrics matrix 的配置派生 `(company, metric_id)` unique exact set，以及 coverage 与 matrix exact key set 对齐；删一补重复、删一补未知和 coverage 缩集均不能 PASS。
- full Golden 的配置/fixture expected assertion exact set、唯一性与删行/增行检测；stratified audit 的五层 deterministic exact set、唯一性与缩集检测。
- 8-K 从 manifest 验证后的有序 request ledger 取得 request-bound base/supplement submissions bytes（当前 bytes 必须匹配同 URL/document 的最新成功 200 完整身份），推导 FY inventory，再从 raw hdr/primary bytes 重放 item，并与 `events.csv` 做 row-multiset exact set；删除 filing/event、重复 item、回滚到旧成功 submissions 后同步缩减 inventory/events、修改未登记工作副本、删除 supplement、正向 count/accession 或其他确定性 metric 字段漂移、删除 component evidence，以及把真实命中伪装成零均不能 PASS。filing-bound raw 文档出现冲突成功 bodies 也必须失败。hdr 无 item时的 primary fallback、primary-only 成功路径与两者都无 item 的失败边界由固定 fixture 覆盖；正向事件按每个被计数组件保留独立 filing identity，零值必须保留完整 scan evidence。
- Basel threshold 排除、actual ratio 选择与 iXBRL scale/parser route；inline namespace fixture 同时覆盖官方 DEI URI 的自定义 prefix、伪 DEI prefix 和冲突 namespace 声明 fail closed。
- captive finance recall/exclusion 与第 11 家 financial institution fixture。
- 10-K/A 到同期间原始 10-K full-instance fallback。
- AST string-addition constant folding 与 I1-I8 implementation map。
- 缺失 JPM CET1 evidence 不得形成空 failure list 或 PASS。
- full/light 中 `NOT_EVALUATED_MISSING_EVIDENCE` 对 report verdict 的不同影响。
- validation run manifest 的 refreshed/not-refreshed 清单、stale CSV 隔离，以及报告写入失败时不得提前暴露成功终态。
- clone A 生成 locator、移动到不同绝对路径的 clone B 后直接执行阶段 11；clone A 的祖先目录与仓库内目录重复使用 `evidence` anchor 时，迁移必须按 hash、URL、accession、document 与 filing directory 选择唯一的当前 clone 后缀，无匹配或多匹配均 fail closed，不能简单取首个或最后一个 anchor。同一 request 的 body/header 必须来自同一个旧仓库根；body 只命中内层候选而 sidecar 只命中外层候选的混合 observation 必须由生产迁移和独立 checker 同时拒绝。已有 hash 不得被迁移重签，`..` 与 symlink 不得逃逸仓库；同名同 hash 的跨 accession 文件不得被重定位；多 source/accession 对单路径的豁免只能由明确的 `events.csv` 派生语义触发，不得根据字段数量猜测。
- RPO claim 所需 instance fact 缺失、Golden fixture 缺失或 metrics 为空时不能 PASS。
- 同一逻辑请求路径的多次 attempt 保留各自 content-addressed body/header；两个独立进程并发追加同一 request ledger 时不得丢行，且 manifest 必须保持有效；request-log manifest 的 JSON key/type 与 CSV 行列宽必须严格。working ledger 必须保留 Git HEAD 的完整有序前缀；runtime committed-HEAD parser 与 PR checker 都拒绝 current row 的多余/缺失单元格，checker 的 current 接受集合不得比 runtime 更宽。PR checker 还对 legacy/current base 与 HEAD 的 prefix、appended tail 逐行校验精确 shape，对 legacy base 独立规范化 portable path、hash、URL-derived accession/document，并以独立实现覆盖重复 anchor 的唯一命中与歧义拒绝；current base 比较完整 row，之后只允许合法尾部追加。重排、删行、identity 字段改写及重签不能把旧响应重新定义为最新。下游 locator、已存 response sidecar 与 URL/accession/document 联合身份继续提供反向约束；hash mismatch 显式 NOT_EVALUATED。
- mock transport 的 response-read timeout、`IncompleteRead` 和已发请求后的 persistence failure 必须形成明确 observation；初始 URL 必须是精确官方 HTTPS origin，redirect 只保留首跳 3xx observation 而不自动请求下一跳；snapshot symlink、大小写 namespace alias、目录型文件目标、hash-prefix symlink，以及最终文件名在检查后的 symlink/hardlink 注入均不得覆盖仓库内外 victim；working/log/manifest hardlink 必须通过新 inode 替换断开，UUID transaction path 预占必须 fail closed。
- C04 必须先检查 `target_10k`（含 10-K/A），只有本地 AuditorName 不可用时才回退同 CIK、同期间原始 10-K；已有有序候选事实时不触发 fetch。空白或纯标点名称不是事实，不同 canonical 名称冲突时不得 first-win 或联网掩盖；后续 200 material observation 覆盖同 identity 的旧 503 current row。full C04 gate 必须从 request-bound accession index 分别重建当期候选/上期 10-K 实例集；同一 filing-bound URL/document 的多个成功 bodies 必须一致，删除 derived material row 不能隐藏已有原始事实；validator 不得复用生产 metric/evidence row builder。两期事实可用时 evidence 必须保留双 raw locator；事实缺失/冲突时必须精确绑定对应 raw scan，把 locator 换成同 accession 的无关合法文档也必须失败；同步篡改完整 C04 metric 与 evidence 不能替代原始 DEI 事实重算。C04 期间起点只取同 CIK prior；没有同 CIK prior 时回退当年 1 月 1 日，不能跨 successor/predecessor CIK 拼接；生产 repair 路径必须把该期间同时写入 metric 与 evidence，不能只测试 period helper；损坏 metrics/evidence/inventory row schema 必须返回 FAIL 而非逃逸崩溃。
- numeric OK evidence 必须同时匹配 value、unit、period、accession，并具备 SEC source、concept/section 与 extraction method。
- capability contract 的 live alignment、repo root 必须等于实际 Git toplevel、HEAD regular blob 与工作树逐字节一致、Git replacement ref/assume-unchanged/仓库重定向环境变量不得改写证据、anchor/directive grammar、type/status 枚举、null metadata、跨 base tombstone 不复用、legacy/current request row 精确行形状、legacy→portable 独立规范化、current→current 完整字段有序前缀，以及本地 `PR_BODY.md` 隔离；嵌在父 Git 仓库、无 `.git` 的离线包、object-store symlink 或 `objects/info/alternates`/`http-alternates` 不能借用其他 checkout 的 HEAD。真实 `git worktree add` 场景中，无 alias 的登记目录必须通过；gitdir 最终 component、gitdir 中间 component 和 commondir 中间 component 任一为 symlink 时，即使 Git 本身仍能解析 HEAD，guard 与下游 source-commit / base-history 读取也必须 fail closed。

`tests/test_validation_provenance.py` 与 `tests/test_validation_provenance_light_package.py` 额外覆盖：

- `config/validation_source_policy.json` 的 exact schema、互斥角色与 SOP 权威引用分类；`01_SOP...md` 或 CIK identity rules 作为 acceptance source，Expert Guide 作为解释性非权威文档，PR Checklist 作为发布治理；
- 只修改 `01_SOP...md` 时 source capture 必须明确拒绝，不能保持相同 digest/count 与 `GIT_CLEAN`；从 policy 删除该 SOP 权威输入也必须 fail closed；
- clean full/light round-trip、manifest source-commit 绑定和内容等价 merge commit warning；
- staged、untracked、ignored 或修改后的 source input 拒绝；
- 无 Git light package 缺少任一显式 singleton source 文件时失败，不能通过删文件缩小 closure；
- provenance key set、artifact hash/size、source tree、stale/unsafe sidecar 和 postflight failure 篡改检测；
- stage 11/12 wrapper 与 README/report notice 的 publication/idempotency 行为。

边界说明：

- `validation_package_mode()` 的 `FULL_VALIDATION` 工作区分类目前没有独立 unittest；完整模式仍依赖真实完整工作区、Golden 和 repair gate 的运行证据。
- `FullInstanceFallbackTest` 只覆盖 10-K/A 到同期间原始 10-K 的 full-instance fallback，不得计入 package-mode coverage；它在缺少 `evidence/submissions/` 时整类 skip，必须在测试记录中保留 skip 数量与原因。
- 依赖当前 full 工作区的 8-K 真实证据回放测试，只在 submissions 或对应 raw 8-K 材料不可用时 skip 该真实形状用例；request-bound 缩集、primary fallback 和 parser 固定 fixture 不依赖 full 工作区，不得被同步 skip。
- 快速回归中的重复-anchor clone A/B 场景覆盖 locator 迁移、唯一身份选择、歧义拒绝、request body/header 共同旧仓库根和阶段 11 消费边界；它仍不等于真实 SEC 全批次重跑。
- 8-K expected-event replay 与生产路径共用 item parser；固定 hdr/primary parser fixture 只锚定已支持格式，不是独立的通用 SEC 文档 oracle，因此 full gate 不单独证明所有未见格式的解析完整性。
- 快速回归不访问网络，也不证明阶段 00-12 的完整 artifact handoff。

## 5. Fixture 简介

| 路径 | 用途 |
|---|---|
| `tests/fixtures/sec_10_company_spike/golden_expected_values.csv` | 固定结构与数值 Golden expected |
| `tests/fixtures/eleventh_company_smoke/` | 配置驱动的新增公司/profile 行为与去公司特例边界 |
| `tests/fixtures/inline_scale_route/mock_inline_scale.xml` | iXBRL scale、sign 与 parser route 回归 |
| `tests/fixtures/regression/previous_ok_status_snapshot.csv` | 已有 OK recall 的回退防护 |

fixture 可以包含公司身份；生产 `scripts/` 与 `tools/` 不得用公司身份触发业务分支。

## 6. FULL、LIGHT 与不完整 workspace

`validation_package_mode()` 当前按工作区形状判定：

1. `evidence/`、`evidence/requests_log.csv` 和至少一个 `outputs/concept_inventory/*.csv` 存在时，进入 `FULL_VALIDATION` 形状；required-input gate 仍逐项检查核心输出和每家公司需要的 instance/ecd evidence。
2. 上述材料有缺失且根目录存在 `LIGHT_REVIEW_PACKAGE.marker` 时，返回 `LIGHT_REVIEW_MODE`。
3. 材料有缺失且没有 marker 时，返回 `WORKSPACE_INCOMPLETE`。

重要限制：

- `FULL_VALIDATION` 只是初始形状分类，不证明每个 raw evidence 文件都齐全；缺少关键 domain evidence 必须写成 `NOT_EVALUATED_MISSING_EVIDENCE` 并阻止正常 GO。
- 完整工作区优先于 marker；不能仅靠 marker 强制降为 light。
- repair validation 的 status 只允许 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。
- light 中依赖 raw evidence 或 concept inventory 的检查必须显示 `SKIPPED_LIGHT_PACKAGE` 或 `NOT_EVALUATED_MISSING_EVIDENCE`，manifest result 只能是带 caveat 的受限通过。
- 无 Git light package 的 provenance 只证明随包 source/artifact bytes；显式 singleton source 文件缺失时必须失败，且永远不能升级为 full validation。
- helper 缺少验证所需 evidence 时不得用空 failures 形成 PASS。
- 未声明的部分工作区必须硬失败，不能自动降级为 light。

## 7. 写入副作用

### 7.1 静态扩展性 gate

`tools/check_no_company_literals.py` 会覆盖 `outputs/scalability_audit.csv`。运行后必须用 `git status --short` 检查是否产生非预期 diff。

### 7.2 Golden

full 模式会通过 G2 访问 SEC companyconcept，可能更新 `evidence/requests_log.csv` 和 raw response，并覆盖：

- `outputs/golden_results.csv`
- `outputs/golden_candidates.csv`

light 模式只做随包 snapshot integrity，不能被记录成 full Golden 重算。

### 7.3 Repair gate

阶段 12 在任何 validation 写入前创建 `outputs/validation_run_manifest.json`，然后逐项登记 `refreshed_artifacts`。它总会先重建 implementation map 与 spec audit；full 模式还写 stub-period sidecar。FULL/LIGHT 工作区继续重建 stratified/scalability audit 与 repair validation。若工作区为 `WORKSPACE_INCOMPLETE`，它只写 repair validation 的失败行，不会刷新 stratified/scalability audit；此时已有文件必须留在 `not_refreshed_artifacts`，不得作为本次运行证据。阶段 12 先用 projected terminal manifest 构建并写入报告，报告持久化成功后才把 manifest 从 `IN_PROGRESS` 写成终态；报告写入失败必须保留 `IN_PROGRESS`。它是 gate，但不是只读检查。

### 7.4 Report build

阶段 11 会先把 locator-bearing artifact 迁移为 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`；对 request log，只在已有 exact-set manifest 验证成功后执行常规 normalization，缺 manifest 的 legacy schema 必须离开常规阶段做显式一次性 bootstrap；随后执行 bounded P0 repair，生成 coverage、crosscheck、异常清单、审计、run manifest、最终报告与 `README_RUN.md`。bounded repair primarily uses local artifacts；C04 repair 先检查 filed target（含 amendment），再遍历同期间原始 10-K fallback，只有有序本地候选仍无事实时才最小补抓官方 SEC material，空白/冲突事实必须降级；C04 期间不跨 CIK。full C04 gate 从 request-bound accession index 分别重建当期候选与上期 10-K 实例集，重放两期官方 DEI `AuditorName`，不以可缩减的 derived material/concept inventory 定义原始证据集。8-K repair 复用阶段 07 的 event→metric/evidence 实现；full validation 另从 request-bound submissions 与 raw filing 重放 expected set。submissions 必须匹配有序 ledger 中最新成功 200；filing-bound raw 文档若存在冲突成功 bodies 则失败。新请求的每次有响应体 attempt 使用 content-addressed immutable body/header；`evidence/requests_log_manifest.json` 记录整份日志的 row count 与 SHA-256，validation 要求 working ledger 保留 Git HEAD 有序前缀，PR checker 要求 base/HEAD 的每条 current/legacy row 形状严格且 HEAD 保留 base 的 migration-neutral 有序前缀，两层都只允许合法尾部追加；下游 locator 与已存 response sidecar 提供反向覆盖。任一不一致都不能 PASS。该 HEAD 基线只在 Git checkout 中存在；无 `.git` 的离线包必须显示 `NOT_EVALUATED_MISSING_EVIDENCE:request_log_history_baseline_unavailable`，FULL validation 因此阻断，LIGHT 本就不执行该 full gate。历史 request row 的 hash 若已无法解析到原 bytes，full gate 也必须写成 NOT_EVALUATED。该分支会追加请求日志及 manifest、raw response、headers/hash、accession material inventory 和 instance inventory；所以阶段 11 不是保证离线的命令。内部 deferred validation 只有在报告和 README 写入成功后才发布 manifest 终态，且不能替代独立阶段 12。

### 7.5 Validation snapshot provenance

stage 11/12 开始时先使旧 `outputs/validation_snapshot_provenance.json` 失效。stage 12 只在既有 terminal gate 成功后计算 source-input tree 与关键 artifact SHA-256/size，原子写 sidecar并从磁盘重新验证；任一 postflight 失败都尝试把 manifest 降为 `FAILED`、把报告改为 `NO-GO` 并非零退出。checker 本身只读，不修复也不重签 artifact。

## 8. 按变更类型选择测试

| 变更类型 | 最低证据 | 追加证据 |
|---|---|---|
| 纯工作流文档 | `python3 tools/check_capability_contract_alignment.py`、JSON 解析与 `git diff --check` | 只有文档声明引用了代码行为时，运行相关快速回归 |
| 普通 Python 逻辑 | 快速回归 | scalability gate；涉及指标/验证时再跑 Golden 与 repair gate |
| 公司、CIK、profile 或 extractor 配置 | 快速回归、第 11 家 fixture、scalability gate | 在隔离 checkout 跑受影响阶段、Golden 与 repair gate |
| parser、期间、证据或 CSV schema | 快速回归 + 受影响阶段 | 隔离 checkout 中完整场景、Golden、repair gate 与产物 diff |
| validation / report verdict / provenance | 快速回归 + provenance 专项 + source policy JSON/SOP authority alignment + Golden + repair gate | 阶段 11 后显式跑 12 和 snapshot checker，验证失败传播、sidecar 与报告内容 |
| SEC HTTP 客户端或 URL | 快速回归中的本地 persistence failure/path、read-timeout、symlink 与 request-log exact-set 测试 | 有效身份下的 live smoke 与 retry/backoff mock，再按影响范围跑场景 |
| 仅报告文案 | 生成器相关检查，不能手改生成报告替代代码 | 若运行阶段 11，必须随后运行阶段 12 和 snapshot checker |

纯文档变更不强制重跑联网阶段 00-11；不得为了“全绿”无谓覆盖已审计的 evidence 与 outputs。

## 9. 推荐执行顺序

### 9.1 普通代码改动

1. 快速回归。
2. provenance 专项（涉及 source/artifact binding 时）。
3. 静态扩展性 gate。
4. 受影响的 Golden 或阶段场景。
5. 最终 repair gate。
6. snapshot checker。
7. 检查 `git status`，确认生成 artifact 与预期一致。

### 9.2 数据采集、阶段 handoff 或 schema 改动

1. 创建干净、隔离的 checkout。
2. 确认有效 SEC 身份配置与目标 scope。
3. 按 `README_RUN.md` 执行完整阶段。
4. 显式执行阶段 12。
5. 运行 snapshot checker。
6. 核对 metrics/evidence/coverage/report、请求日志与 artifact diff。

### 9.3 纯工作流文档同步

1. 验证 `capability_contract.json` 是 UTF-8 合法 JSON。
2. 运行 `python3 tools/check_capability_contract_alignment.py`；PR 场景再以实际 base 运行 `python3 tools/check_capability_contract_alignment.py --base-ref <base>`，机械检查 HEAD regular-file/blob 与工作树 bytes 一致性、anchor、必填 metadata、test symbol、tombstone 历史，以及 base/HEAD request row 的严格行形状和有序前缀。
3. 运行与所引用行为相关的快速回归。
4. 运行固定上游对应的 workflow docs 机械检查。
5. 记录机械检查只证明最终文件状态，不证明分析、审计或测试历史。

## 10. 失败定位

- unittest：从失败 test method 回到对应 helper 与 fixture；不要用改 expected 的方式消除真实回归。
- Golden：查看 `outputs/golden_results.csv` 的 expected、actual、evidence path 与 notes。
- Repair：先读 `outputs/validation_run_manifest.json`，只打开 `refreshed_artifacts` 中的 validation/audit 文件；再查看 `outputs/repair_validation_results.csv` 的 `check_id`、status 与 details。
- Snapshot：运行 `python3 tools/check_validation_snapshot.py`，先区分 source policy schema/角色或 SOP authority mismatch、missing/unsafe sidecar、source dirty/tree/file-count mismatch、manifest identity mismatch 与具体 artifact SHA-256/size mismatch。
- 指标/证据不一致：先核对 `metrics_matrix.csv` 是否恰好包含 registry/profile/applicability contract 推导的 unique `(company, metric_id)` set，再与 `metric_evidence.csv` join；8-K 指标还要从 request ledger→submissions bytes→inventory→raw filing bytes→events→metric/component evidence 顺向核对。
- coverage：先核对 `coverage_matrix.csv` 的 unique key set 是否与 metrics matrix 完全一致，再检查 status、has_evidence、needs_review 与 reason。
- live 请求：在阶段顺序运行前提下，先核对 `evidence/requests_log_manifest.json` 的整表 row count/hash、Git HEAD/base 有序前缀、下游 locator 与已存 sidecar 反向覆盖，再检查 `evidence/requests_log.csv` 的 URL、status、User-Agent、retry_attempt、error，以及 body/header locator 与 `content_sha256`；完整性不一致是 FAIL，历史 bytes mismatch 只能是 NOT_EVALUATED。同一 repository 的 log publication 在 cooperating threads / POSIX processes 间串行化，但限速仍是 per-client，且不承诺网络文件系统锁语义。
- light 包：先确认 marker、manifest mode/result、显式 source singleton 与缺失材料，禁止把 skipped、NOT_EVALUATED 或 `LIGHT_PACKAGE_NO_GIT` 当作 full PASS。

## 11. 新增或修改测试

- 行为性 Bug 必须先有可复现的最小回归。
- 只有跨阶段累计状态、阶段间 artifact 或固定顺序才能暴露的问题，必须增加 scenario 级回归；单 helper 测试不能替代。
- 测试新增或职责改变时更新本文件的覆盖与 fixture 简介。
- 不为薄 wrapper 重复写同构测试，不用正则统计源码中的指标/检查数量，不自动测试教学文案风格。

## 12. 已知高价值缺口

- `validation_package_mode()` 的 `FULL_VALIDATION` shape 缺少临时工作区单元测试。
- mock transport 已覆盖精确官方 origin、禁用自动 redirect、response-read timeout、请求前 working/root/namespace alias preflight，以及响应后动态 snapshot/persistence failure observation；尚未覆盖 User-Agent 与完整 retry/backoff 矩阵。
- immutable request snapshot 与 validation provenance sidecar 都是仓库内完整性机制，不是外部签名、透明日志或针对恶意同 UID 进程的 WORM；能同时修改全部文件并重签的人仍在本地信任边界内。
- Git workspace 回归证明检查时已存在的 gitdir/commondir lexical path alias 会被拒绝；guard 与后续 Git CLI 不是原子系统调用，尚未覆盖恶意同 UID 进程在两者之间主动切换 namespace 的 TOCTOU。
- 尚无使用录制 SEC fixture、临时工作区贯穿阶段 00-12 artifact 契约的离线 scenario test。
