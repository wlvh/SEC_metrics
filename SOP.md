# SEC_metrics 标准操作流程导航

## 使用原则

每一步只包含动作、权威引用和验收。SOP 不复制会变化的脚本清单、测试命令或指标规范；发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。`config/validation_source_policy.json` 必须把每个权威引用分类为运行/验收 source、snapshot artifact 或非批次治理角色；解释性非权威文档不能作为本表的运行权威。

## Issue #15 D-26 测试执行边界

`requirements/issue_15_v1/decision_register.json` 的 effective D-26 保留 `python3 tools/run_fast_tests.py --jobs 4` 与 fast/local 证据层级，并继续排除全仓/双解释器、隔离 repository/worktree 和长串行套件。金额 `budget_preflight_provider_calls_zero` 已从必测集合删除；仍保留 single-flight、HTTP 402 一次调用后停批、UNKNOWN_REMOTE_OUTCOME 不自动重试、frozen replay/rollback/restore 零网络与 structured-only 零模型调用的短小确定性测试。随后可运行 `python3 tools/run_acceptance.py --scope recorded` 封存 `PASSED_FAST_LOCAL_ONLY`；该状态仍不是 CI、live、full acceptance 或 active Cutover。

## Issue #15 D-36/D-35 金额与资源安全边界

effective D-36 禁用仓库金额预算执法，花费权威是 `EXTERNAL_API_ACCOUNT_BALANCE`；仓库不定义 per-call、batch、owner 或 remaining monetary cap，也不在 provider egress 前以 estimated/actual cost 阻断调用。pricing、token、usage、cache 与 cost 只作非阻断审计。effective D-35 不含金额 `BUDGET_EXCEEDED`；`HTTP_402` 仍零自动重试并立即终止 execution 与 batch。payload/context/resource limit 仍是独立 terminal 安全类，不得重命名为金额门禁。
<!-- capability-anchor: BEHAVIOR.issue_15_repository_monetary_budget_disabled -->

## R5 live 与 review 边界

按 [Issue #12 R5 用户授权](https://github.com/wlvh/SEC_metrics/issues/12#issuecomment-5314176033)，live Reader 使用 `DEEPSEEK_API_KEY` 对应的官方 `deepseek-v4-flash` Chat Completions；HUMAN review 可选，缺失时 D-06 只允许明确标注的 SYSTEM approval。Hilton FY2024 是第二真实布局，freeze 后的 Hyatt FY2024 是独立 holdout；两者均已通过 qualification。首次 Cutover 不需要预先存在 active/previous pointer，而是导入 legacy A 后原子创建 B→A chain。

## Issue #15 Requirement authority 与后续开发

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 读取冻结 Contract 与 transfer/baseline | `requirements/issue_15_v1/CONTRACT.md`；`requirements/issue_15_v1/transfer_manifest.json`；`requirements/issue_15_v1/baseline_manifest.json` | Contract SHA-256 为 `9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec`；parent closure 与 foundation commit/tag/merge binding 一致 |
| 2 | 加载自包含 Decision 和 WB-1 receipts | `requirements/issue_15_v1/decision_register.json`；`requirements/issue_15_v1/legacy_semantic_producer_inventory.json`；`requirements/issue_15_v1/source_strategy_baseline_receipt.json`；`requirements/issue_15_v1/foundation_verification_receipt.json` | `load_requirement_snapshot(issue_15_v1)` 通过；D-01 与 post-freeze D-36/D-35/D-26 effective tips 精确；39 指标 producer/matrix exact set 闭合；最高 foundation 证据仅为 `FAST_LOCAL_ONLY` |
| 3 | 读取 inherited foundation | `requirements/ai_first_v3_3_1/` | 父目录 exact bytes 不变；其实现、evidence/publication/fail-closed invariants 被继承而不是重写 |
| 4 | 加载 WB-2 target routing 与 ratchet state | `config/source_strategy_registry.json`；`config/issue_15_release_plan.json`；`scripts/vnext/source_strategy.py` | 39 metric ID 恰好各有一条；source mode 只有四种；无 `ai_event_text` 与当前迁移状态；只由 `ReleasePlan.cumulative_metric_ids` 持有当前集合；family literal 不含通用词 |
| 5 | 验证 WB-2B deterministic source routing | `catalog/event_routes.json`；`scripts/vnext/deterministic_router.py` | 五个 adapter 只消费 exact SourceReference/raw bytes；每个 role 使用 `sources[]`、ID array 与 SourceSetManifest；submissions bytes 反向重算来源集；C01/E03 共用 claim；E02/E04 零值有完整全年 set；E01 matched key set 与 legacy exact parity；provider socket=0 |
| 6 | 验证 WB-3 invocation control | `scripts/vnext/invocation_control.py`；Issue #15 effective D-35/D-36 | exact response 复用；只有 reservation owner 调用 transport；402/其他 terminal 只一次并停批；429/timeout/recoverable 5xx 最多一次重试；UNKNOWN 不自动重试；cost 只观测；payload/context 仍 fail closed；structured-only 三种计数全为 0 |
| 7 | 只实施当前获准的 WB/ratchet | Issue #15 对应章节；`architecture.md`；`TESTING.md` | 不提前实现后续 WB；未获授权不得发起真实模型调用 |

## 快速入口：只读取现有结果

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 先读取 run manifest | `outputs/validation_run_manifest.json` | `result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时立即停止验收 |
| 2 | 独立验证 source 与 artifact binding | `python3 tools/check_validation_snapshot.py`；`docs/validation_snapshot_provenance.md` | provenance 存在；source-input tree clean/等价；关键 artifact SHA-256 与 size 全部匹配 |
| 3 | 阅读报告和具体结果 | `REPORT_十公司财务指标.md`；`outputs/metrics_matrix.csv`；`outputs/metric_evidence.csv` | verdict、value/status、期间、口径和 evidence 能闭合 |
| 4 | 复核限制和人工责任 | `interact.md`；`docs/business_user_guide.md` | 未把 light、caveat、NOT_EVALUATED 或历史快照写成 full PASS |

## SOP 1：SEC 阶段 00-12 完整批次运行

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认公司范围、CIK role、指标适用性和有效 SEC 请求身份 | `config/`；`01_SOP_SEC_10公司单年指标计算_直接SEC.md`；`02_指标定义_SEC_10公司单年指标.md`；`CIK变更应对方案.md` | 配置结构有效，范围、身份连续性和口径已由运行负责人确认；`01_SOP...` 的 M0–M7 仅作业务概念说明 |
| 2 | 以`sec_pipeline.py --workspace-dir <absolute-isolated-root> <stage>`在干净candidate数据根按需执行SEC采集与legacy非迁移阶段 | `README_RUN.md`；`TESTING.md` | 源码repository root与含active pointer的workspace不运行legacy Stage04/09/11；migrated写入全部fail closed；candidate evidence/outputs不冒充active |
| 3 | 通过vNext operator形成complete staging并准备formal publication；full live path在release planning前固定执行SEC Stage00/01/02/03/05 acquisition/inventory | 本文件“vNext operator与正式Cutover”；`README_RUN.md` | acquisition原样命令、ledger合法tail与inventory receipt已持久化；qualification、live有效 review、strict parity、old-path migration与publication gates全部满足 |
| 4 | commit后对new/rollback/restore分别执行一次公开terminal cycle | `python3 tools/run_acceptance.py --scope full --execute-live`；`tools/vnext_terminal_cycle.py`；`TESTING.md` | 每轮只启动一个进程并pin一次PublicationView transaction，依序完成Stage10 Golden、Stage11 report、Stage12 active validation、snapshot publish/verify；三轮均通过，最终恢复new publication并生成full receipt |
| 5 | 交付root mirrors、报告、证据和限制 | `interact.md`；`docs/business_user_guide.md` | reviewer能从active pointer/provenance追溯到bundle、report、metrics、evidence和request ledger；latest失败不覆盖active |

## 专项：vNext operator 与正式 Cutover

<!-- capability-anchor: BEHAVIOR.vnext_freeze_accepts_audit_validation_states -->
<!-- capability-anchor: BEHAVIOR.vnext_publication_requires_passed_validation -->
<!-- vnext-validation-state-contract:start -->
| Validation 状态 | OPEN Run 可 freeze | Candidate publication 状态门 |
|---|---|---|
| `PASSED` | 允许 | 满足本状态门 |
| `FAILED` | 允许 | 禁止 |
| `NOT_RUN` | 允许 | 禁止 |
<!-- vnext-validation-state-contract:end -->

Freeze 保存不可变审计与 replay 事实，不代表 validation 通过；publication 仍须同时满足 `PASSED` 和其他全部发布门。

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 对现有 inherited operator 读取父 FSD/R2/R3 与历史实现闭包；对任何后续开发先读取 Issue #15 authority | `requirements/issue_15_v1/`；`requirements/ai_first_v3_3_1/` | 新开发只以 Issue #15 / `issue_15_v1` 为入口；WB-1 未把新 D-01/D-26 语义提前接入现有 Reader/Cutover runtime |
| 2 | 用同一 operator 创建、查看并推进 Run；recorded 只替换 transport/source acquisition | `python3 tools/vnext_operator.py --help`；`interact.md` | recorded 时 socket=0、root/active 不变；live 必须显式 `--execute-live`，只读 `DEEPSEEK_API_KEY`，SEC organization 固定 `axaxl` 且 email 只读 `SEC_CONTACT_EMAIL` |
| 3 | HUMAN 可选地复核 `review.md` 和完整 ReviewUnit，并通过 `review list/show/decide` 追加单链决定 | `tools/vnext_operator.py review`；`tools/vnext_review.py` | 已有 HUMAN 决定优先；缺决定时 D-06 写入可审计 SYSTEM approval，SYSTEM 不得伪装为 HUMAN，Evidence/compatibility publication gates不放宽 |
| 4 | release input plan先绑定exact source的latest verified request attempt及locator class；finalize/freeze 后做无网络 replay，再由 complete BatchManifest 与 Projector 形成 strict-compatible staging | `architecture.md`；`TESTING.md` | recorded legacy locator必须逐path/hash/headers/size验证并在closure显式绑定tier/class；formal live只允许immutable attempt并拒绝legacy。所有 Run 都是 `PASSED/FROZEN`；十公司×四指标 exact set、N/A、期间、字段/evidence/reconciliation parity 全部通过；WITHHELD 阻止整批发布 |
| 5 | 先以受控capture录制第二真实布局并完成有效 HUMAN 或 SYSTEM `APPROVE`、全量`PUBLISHED` Result和`PASSED` Run validation receipt，再冻结production semantic tree和pre-holdout inventory，最后才capture并加入独立holdout | `tools/vnext_capture_qualification_fixture.py`；`tools/vnext_qualification.py` | Hilton FY2024 capture/second→`freeze`→新增 Hyatt FY2024 capture/holdout→`status`顺序成立；capture只接受仓库候选ID并经SEC/DeepSeek固定边界保存可回放bytes，两者 company/CIK/accession/source 均独立，`REJECT`/WITHHELD只保留审计而不能签发资格receipt，holdout在freeze前不存在且加入后semantic hash不漂移 |
| 6 | 只在全部资格和凭据满足后执行 live Cutover；同一命令先执行固定SEC acquisition/inventory，再依次验证 new→rollback→restore | `python3 tools/run_acceptance.py --scope full --execute-live` | 三次live attempt的portable audit closure、十公司staging、verified legacy A→formal B commit，以及每轮单次调用`tools/vnext_terminal_cycle.py`、共用同一pinned view完成五项gate均真实产生并返回0 |

### Cold-start recorded fixture 与 sandbox publication

运行负责人可先执行 `python3 tools/vnext_operator.py --json fixture list`，再用 `fixture show --fixture-id <id>` 核对 catalog/source/provenance binding。随后以同一组显式 UTC 值运行：

```bash
python3 tools/vnext_cutover.py --json --fixture-id <id> \
  --workspace-dir artifacts/vnext/recorded-<workspace> \
  --legacy-snapshot-dir outputs \
  --validated-at-utc <UTC> --committed-at-utc <UTC>
```

HUMAN review 是可选停点：若具名 HUMAN 在最终化前写入 decision，系统使用该决定；否则 D-06 写入固定身份的 SYSTEM approval 并继续 finalization/freeze/replay、complete Batch/Projector，随后在 `<workspace>/recorded-publication` 内 prepare、CAS commit 和 PublicationView read-back。recorded workspace第一层固定为`recorded-*`，默认`recorded-cutover`；live固定使用repository-owned `artifacts/vnext/cutover`，不得传`--workspace-dir`，否则在load/write前以`LIVE_WORKSPACE_OVERRIDE_FORBIDDEN`失败。live core同时exact固定module-owned repository、`outputs` legacy snapshot与publication root；每次有效live调用（包括 HUMAN 或 SYSTEM resume）都fresh执行SEC acquisition，再复用exact pinned semantic plan，本次receipt必须进入current audit/full binding。整个 recorded flow socket=0，正式 active pointer/root mirrors、formal namespace与SEC ledger前后 exact 不变。测试使用的 `TEST_ONLY_EXPLICIT_REVIEW` 不能作为正式 review 或 full evidence；generic `publish --commit` 仍是 fail-closed tombstone。

sandbox publication 的 request closure按证据层级验证：recorded 可接受历史ledger row明确声明、且body/headers的repository path、hash、size全部匹配的唯一`LEGACY_WORKING_LOCATOR`，portable closure必须保留locator tier/class；缺失、歧义或bytes漂移均失败。formal/live仍只允许`IMMUTABLE_ATTEMPT`，legacy class稳定返回`LIVE_SOURCE_ATTEMPT_INCOMPLETE`，不得因recorded可重放就升级为formal证据。

`python3 tools/run_acceptance.py --scope recorded` 的最高状态是 `PASSED_FAST_LOCAL_ONLY`，且不得修改正式 pointer、root mirrors、formal namespace或SEC ledger。generic operator `publish`只能准备inactive recorded bundle；public generic formal receipt/commit API会以`FORMAL_CUTOVER_AUTHORITY_REQUIRED`或`FORMAL_COMMIT_REQUIRES_CUTOVER`失败，不能绕过Cutover orchestrator。source plan后ledger binding漂移以`SOURCE_LEDGER_BINDING_AMBIGUOUS`失败，formal live遇`LEGACY_WORKING_LOCATOR`以`LIVE_SOURCE_ATTEMPT_INCOMPLETE`失败。首次formal Cutover把冻结legacy bytes只读导入为verified predecessor A，再原子建立A→formal B；rollback到A也不会调用旧parser。`--scope full` 未带 `--execute-live` 返回 `LIVE_EXECUTION_NOT_AUTHORIZED`。本轮Hilton/Hyatt qualification与SEC acquisition均已产生；三次live Reader因provider `Insufficient Balance`失败，因此没有staging、active/full、rollback或restore receipts。运行时凭据只可进程注入，active predecessor 不再是 preflight requirement，首次 A→B chain 会自动创建。R4快速本地证据不等于 active Cutover。

recorded acceptance 当前要求 macOS `/usr/bin/sandbox-exec` 对整个子进程树拒绝网络，以literal保护正式pointer/mirrors/sidecar/ledger、pointer lock与latest run status，以subpath保护live Cutover、qualification、request attempts、publication、publication switch intent/receipt、fault与live audit tree；缺失时稳定返回 `OFFLINE_PROCESS_SANDBOX_REQUIRED`，不得降级。runner 还会从 recorded 与 terminal-validation 子进程剥离 live secrets，绑定 clean source/Requirement、本次隔离 semantic/scalability exact artifacts，并在前后重验formal namespace exact tree与pointer lock/latest status bytes。持久receipt用`$REPO_ROOT`、`$ACCEPTANCE_OUTPUT`、`$PYTHON_CURRENT`、`$PYTHON39`、`$SANDBOX_EXEC`等portable token替换host路径，并对实际runtime binary保存SHA-256；本机绝对路径不落盘。每个new/rollback/restore terminal cycle只启动一次`tools/vnext_terminal_cycle.py`，在单进程、单次pin中完成Stage10→Stage11→Stage12→snapshot publish→verify。若 recorded 仍产生 root drift，会先恢复原 bytes 但本次 receipt 保持失败；namespace/ledger漂移fail closed且不删除可能的并发合法append。full Cutover 子进程若在非零、`HUMAN_REVIEW_REQUIRED` 或非法返回时意外 commit，会恢复调用前 predecessor（首次无 pointer 时恢复原 root bytes）并保留原 blocker。默认 7200 秒只是单 command timeout 上限，超时仍为 `FAILED`。

publication switch在修改mirror前于独占锁内写`outputs/publication_switch_intents/<sha256>.json`，绑定previous/proposed pointer、上一switch tip、模式及每个mirror的存在性/hash/size。共享锁reader遇pending、多份或tampered intent只会fail closed，不做恢复或清理；独占锁writer/recovery若pointer已是proposed则补齐switch receipt并从proposed bundle重建mirrors，若仍是previous则移除本事务receipt、恢复previous状态，再删除exact intent；其他pointer状态失败。hard crash恢复不运行旧parser，也不改变request ledger。

## SOP 2：分层验收与失败定位

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 按变更类型选择最小且充分的测试层级 | `TESTING.md` 的测试层级与变更决策表 | 每条适用命令、结果和未运行原因已记录 |
| 2 | 先读 validation run manifest，再运行 snapshot checker | `README_RUN.md` 的验收顺序；`docs/validation_snapshot_provenance.md` | stale run、dirty source、tree mismatch 与 artifact tamper 已先排除 |
| 3 | 再定位 unittest、Golden、repair、coverage 或请求失败 | `TESTING.md` 的失败定位 | 失败已对应到具体 test、check_id、company/metric、source path、artifact digest 或请求记录 |
| 4 | 修复真实原因并重跑受影响层及下游 gate | `TESTING.md`；`architecture.md` 的阶段依赖与错误模型 | 没有放宽断言、静默跳过、重签旧证据或以 light 结果冒充 full |
| 5 | 核对生成 artifact 与工作区范围 | `TESTING.md` 的写入副作用；`PR_Checklist.md` 的变更范围 | `git status` 只包含预期文件，失败证据与处置可复核 |

## SOP 3：PR 发布（仅用户明确要求时）

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认发布授权、feature branch、base 与 patch 范围 | `PR_Checklist.md` | 用户已要求发布，当前分支不是 `main`，base 为 `main` |
| 2 | 完成文档影响、测试证据、已知限制和 Review 记录 | `PR_Checklist.md`；`.github/pull_request_template.md` | PR body 与真实 diff、测试结果和未解决决策一致 |
| 3 | 按授权执行 commit、push 和 PR 创建 | `PR_Checklist.md` 的分支、提交与创建规则 | 命令成功并返回真实远端分支与 PR URL |
| 4 | 向用户交付发布结果 | `PR_Checklist.md` 的最终核对 | draft/ready 状态、URL、测试与限制均已明确报告 |
