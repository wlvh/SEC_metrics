# SEC_metrics 标准操作流程导航

## 使用原则

每一步只包含动作、权威引用和验收。SOP 不复制会变化的脚本清单、测试命令或指标规范；发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。`config/validation_source_policy.json` 必须把每个权威引用分类为运行/验收 source、snapshot artifact 或非批次治理角色；解释性非权威文档不能作为本表的运行权威。

## R4 测试执行边界

按 [Issue #12 R4 用户授权](https://github.com/wlvh/SEC_metrics/issues/12#issuecomment-5313207170)，开发、PR 与 final acceptance 的唯一必跑测试是 `python3 tools/run_fast_tests.py --jobs 4`，随后可运行 `python3 tools/run_acceptance.py --scope recorded` 封存 `PASSED_FAST_LOCAL_ONLY` 本地证据。不得把全仓/双解释器套件、隔离 repository/worktree、freeze/replay 或长串行场景列为必跑测试。下文的 qualification、live、staging、rollback/restore 是实际运营发布流程，不由 R4 测试替代，也不得凭快速测试声称完成。

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
| 3 | 通过vNext operator形成complete staging并准备formal publication；full live path在release planning前固定执行SEC Stage00/01/02/03/05 acquisition/inventory | 本文件“vNext operator与正式Cutover”；`README_RUN.md` | acquisition原样命令、ledger合法tail与inventory receipt已持久化；qualification、live/HUMAN、strict parity、old-path migration与publication gates全部满足 |
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
| 1 | 按顺序读取 FSD、immutable R2、exact R3 Addendum、Decision Register、baseline 与 SU 状态 | `requirements/ai_first_v3_3_1/` | R2 仍提供 SU/AC 与详细契约；R3 只逐项 supersede。历史 D-01 pending 可追溯，唯一 effective D-01 为 `APPROVED` |
| 2 | 用同一 operator 创建、查看并推进 Run；recorded 只替换 transport/source acquisition | `python3 tools/vnext_operator.py --help`；`interact.md` | recorded 时 socket=0、root/active 不变；live 必须显式 `--execute-live`，只读 `OPENAI_API_KEY`，SEC organization 固定 `axaxl` 且 email 只读 `SEC_CONTACT_EMAIL` |
| 3 | 让具名 HUMAN 复核 `review.md` 和完整 ReviewUnit，并通过 `review list/show/decide` 追加单链决定 | `tools/vnext_operator.py review`；`tools/vnext_review.py` | 程序、模型、fixture 和 acceptance runner 均不得自动批准；缺决定返回 `HUMAN_REVIEW_REQUIRED`、保留 OPEN Run 并给出恢复命令 |
| 4 | release input plan先绑定exact source的latest verified request attempt及locator class；finalize/freeze 后做无网络 replay，再由 complete BatchManifest 与 Projector 形成 strict-compatible staging | `architecture.md`；`TESTING.md` | recorded legacy locator必须逐path/hash/headers/size验证并在closure显式绑定tier/class；formal live只允许immutable attempt并拒绝legacy。所有 Run 都是 `PASSED/FROZEN`；十公司×四指标 exact set、N/A、期间、字段/evidence/reconciliation parity 全部通过；WITHHELD 阻止整批发布 |
| 5 | 先完成第二真实布局的有效 HUMAN `APPROVE`、全量`PUBLISHED` Result和`PASSED` Run validation receipt，再冻结production semantic tree和pre-holdout inventory，最后才加入独立holdout | `tools/vnext_qualification.py` | `prepare SECOND`→HUMAN→重跑prepare→`freeze`→新增`HOLDOUT`→HUMAN→重跑prepare→`status`顺序成立；`REJECT`/WITHHELD只保留审计而不能签发资格receipt；至少两项materially different，holdout在freeze前不存在且加入后semantic hash不漂移 |
| 6 | 只在全部资格和凭据满足后执行 live Cutover；同一命令先执行固定SEC acquisition/inventory，再依次验证 new→rollback→restore | `python3 tools/run_acceptance.py --scope full --execute-live` | 三次live attempt的portable audit closure、十公司staging、verified legacy A→formal B commit，以及每轮单次调用`tools/vnext_terminal_cycle.py`、共用同一pinned view完成五项gate均真实产生并返回0 |

### Cold-start recorded fixture 与 sandbox publication

运行负责人可先执行 `python3 tools/vnext_operator.py --json fixture list`，再用 `fixture show --fixture-id <id>` 核对 catalog/source/provenance binding。随后以同一组显式 UTC 值运行：

```bash
python3 tools/vnext_cutover.py --json --fixture-id <id> \
  --workspace-dir artifacts/vnext/recorded-<workspace> \
  --legacy-snapshot-dir outputs \
  --validated-at-utc <UTC> --committed-at-utc <UTC>
```

首次返回 `HUMAN_REVIEW_REQUIRED` 是预期停点：无需HUMAN审核的structured Runs已按release plan freeze，需要人工审核的lodging Run保持OPEN；逐项读取返回的 `review_path`/`review_unit_hash` 并复制 `review_command`，由具名 HUMAN 亲自决定。完成决定后必须重跑完全相同的 Cutover 命令；它才会 resume、finalize/freeze/replay、形成 complete Batch/Projector，并在 `<workspace>/recorded-publication` 内 prepare、CAS commit 和 PublicationView read-back。recorded workspace第一层固定为`recorded-*`，默认`recorded-cutover`；live固定使用repository-owned `artifacts/vnext/cutover`，不得传`--workspace-dir`，否则在load/write前以`LIVE_WORKSPACE_OVERRIDE_FORBIDDEN`失败。live core同时exact固定module-owned repository、`outputs` legacy snapshot与publication root；每次有效live调用（包括HUMAN resume）都fresh执行SEC acquisition，再复用exact pinned semantic plan，本次receipt必须进入current audit/full binding。整个 recorded flow socket=0，正式 active pointer/root mirrors、formal namespace与SEC ledger前后 exact 不变。测试使用的 `TEST_ONLY_EXPLICIT_REVIEW` 不能作为 formal HUMAN 或 full evidence；generic `publish --commit` 仍是 fail-closed tombstone。

sandbox publication 的 request closure按证据层级验证：recorded 可接受历史ledger row明确声明、且body/headers的repository path、hash、size全部匹配的唯一`LEGACY_WORKING_LOCATOR`，portable closure必须保留locator tier/class；缺失、歧义或bytes漂移均失败。formal/live仍只允许`IMMUTABLE_ATTEMPT`，legacy class稳定返回`LIVE_SOURCE_ATTEMPT_INCOMPLETE`，不得因recorded可重放就升级为formal证据。

`python3 tools/run_acceptance.py --scope recorded` 的最高状态是 `PASSED_FAST_LOCAL_ONLY`，且不得修改正式 pointer、root mirrors、formal namespace或SEC ledger。generic operator `publish`只能准备inactive recorded bundle；public generic formal receipt/commit API会以`FORMAL_CUTOVER_AUTHORITY_REQUIRED`或`FORMAL_COMMIT_REQUIRES_CUTOVER`失败，不能绕过Cutover orchestrator。source plan后ledger binding漂移以`SOURCE_LEDGER_BINDING_AMBIGUOUS`失败，formal live遇`LEGACY_WORKING_LOCATOR`以`LIVE_SOURCE_ATTEMPT_INCOMPLETE`失败。首次formal Cutover把冻结legacy bytes只读导入为verified predecessor A，再原子建立A→formal B；rollback到A也不会调用旧parser。`--scope full` 未带 `--execute-live` 返回 `LIVE_EXECUTION_NOT_AUTHORIZED`。本轮仓库尚无合格第二布局/holdout bytes、live/HUMAN/staging/active predecessor/full receipts，所需两个环境凭据也缺失，因此当前业务入口仍是 root CSV/报告；R4快速本地证据不等于 active Cutover。

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
