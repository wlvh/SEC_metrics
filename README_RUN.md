# README_RUN

<!-- validation-reading-routes:start -->
## 只读取现有结果

1. 先读 `outputs/validation_run_manifest.json`；`result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时停止验收。
2. 运行 `python3 tools/check_validation_snapshot.py`；缺少 provenance、源输入树不一致、关键 artifact hash 失配或 source input 有未提交改动时停止验收。
3. 再读 `REPORT_十公司财务指标.md`，随后按需查看 `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
4. `source_commit` 与当前 HEAD 不同不自动等于失败；只有独立 checker 证明 source-input tree 等价时，merge commit 等 SHA 变化才可接受。

## 执行新批次

1. 使用干净 checkout，并配置有效 SEC organization/contact email。
2. 正式刷新只运行 `python3 tools/run_acceptance.py --scope full --execute-live`；它负责 Cutover、new/rollback/restore 三轮 terminal validation 与最终 full receipt。
3. 内部 legacy 非迁移 candidate 按下文把阶段 `00`–`11` 统一指向一个源码 checkout 外的绝对隔离数据根；它不更新 active pointer 或 root mirrors。
4. 只有 formal full 命令真实返回 0 才是正式完整批次成功；candidate stage 11、recorded receipt、NOT_RUN 或单独 checker 都不能冒充 full。

## Validation snapshot provenance

- legacy candidate stage 11 在修改候选报告前删除可安全识别的旧 regular `outputs/validation_snapshot_provenance.json`；alias/非 regular 目标提前失败。active stage 11 只读 pinned view，不碰 sidecar 或 mirrors。
- `config/validation_source_policy.json` 分类 runtime source、acceptance source、
  full artifact directory、generated artifact、发布治理和解释性文档；SOP
  权威引用必须有明确角色，解释性非权威文档不能作为运行权威。
- stage 12 只在 policy-defined source closure 无未提交改动时继续；成功后绑定
  当前 Git commit、完整 source-input tree SHA-256，以及 manifest、报告、README、
  metrics/evidence/coverage/Golden、request ledger、full request-attempt
  recursive exact set 与 refreshed validation artifact 的 SHA-256/size。
- 提交或 merge 导致 commit SHA 改变时，checker 只有在完整 source-input tree 仍等价时才给 warning 并允许继续；任一 source byte 或 artifact byte 漂移都失败。
- light package 可以生成显式 `LIGHT_PACKAGE_NO_GIT` 的受限 provenance，但不能升级为 full validation。
<!-- validation-reading-routes:end -->

## 配置

- 运行时支持 POSIX 本地文件系统上的 Python 3.9+。
- SEC HTTP 配置：`config/sec_config.json`。
- 所有时间戳使用 UTC；文本编码 UTF-8。
- 单个 `SecHttpClient` 实例执行进程内请求节流，默认 5 requests/sec；
  不同 client 或进程之间不协调限速；同一 repository 的 request log
  publication 会在 cooperating threads / POSIX processes 间串行化，不承诺网络文件系统锁语义。
- immutable response 防预存和最终文件名 symlink/hardlink 别名，但假设单次写入期间父目录 namespace 稳定；它不是 WORM 存储。
- `SecHttpClient` 不自动跟随 HTTP redirect；首跳 3xx body、headers、Location 与日志会保留，目标 URL 只能作为下一次显式、重新校验的请求。

## vNext 正式 operator 与证据等级

- 正式 active 状态只由 `outputs/active_publication.json` 指向的 immutable PublicationView 决定；pointer 存在时业务用户读取的 root CSV、README 与报告才是该 active bundle 的 compatibility mirrors，没有 pointer 时它们仍是既有 snapshot。
- `artifacts/vnext/latest_run_status.json` 表示最近一次更新尝试，可能失败或仍待 HUMAN review；它不能替代 active pointer。失败尝试不得覆盖上一 active。
- OpenAI Reader 只是公开 SEC filing table-grid 的受限处理器，不是 SEC evidence source；数字 authority 仍由 RawAsset/Evidence/Review/Trace 链提供。
- ReviewDecision 必须由 HUMAN 使用正式 CLI 显式写入；operator、模型、fixture 和 acceptance runner 都不会自动 APPROVE。
- root mirrors 对通过 PublicationView 打开的 reader 提供固定视图；不向任意逐文件读取器承诺跨文件组原子。
- Requirement authority 同时绑定 exact FSD、immutable R2、exact R3 Addendum、Decision Register、frozen baseline、release plan 与 semantic runtime versions；任一 bytes 变化都会使旧 approval、Run、Batch 与 publication 失效。
- 当前交付仍是仓库 CLI/文件，没有 UI、API、scheduler、生产数据库或自动 HUMAN approval 服务；recorded sandbox 也不会改变这一产品边界。

### R4 并发快速验收

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_fast_tests.py --jobs 4
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_acceptance.py --scope recorded
```

R4只并发运行六个直接、非隔离、非 freeze/replay 的本地边界用例；recorded runner 的最高状态是 `PASSED_FAST_LOCAL_ONLY`，receipt 写入 `outputs/acceptance_receipts/`。它不是 CI、live stage、formal Cutover 或 full acceptance。测试策略以 `TESTING.md` 为准。
recorded/full acceptance 的持久命令证据使用 `runtime_bindings`：`$PYTHON_CURRENT` 与可用时的 `$SANDBOX_EXEC` 绑定 executable name 和 runtime binary SHA-256；argv、interpreter、output locator 与诊断中的本地路径递归替换为 portable token，剩余 host path 只保留 SHA-256，不持久化本机绝对路径。
acceptance `--output-dir` 不能等于、包含或位于任何正式 pointer、mirror、SEC ledger、publication/qualification/audit namespace 下；命中时在首次写入前返回 `ACCEPTANCE_OUTPUT_DIR_OVERLAPS_FORMAL_AUTHORITY`。R4不再启动 Python 3.9 全量测试或任何隔离 repository/worktree；formal authority 前后仍会 exact read-back。

### Cold-start recorded fixture 与 sandbox PublicationView

```bash
python3 tools/vnext_operator.py --json fixture list
python3 tools/vnext_operator.py --json fixture show --fixture-id FIXTURE_ID
python3 tools/vnext_cutover.py --json --fixture-id FIXTURE_ID --workspace-dir artifacts/vnext/recorded-cold-start --legacy-snapshot-dir outputs --validated-at-utc UTC_VALIDATED --committed-at-utc UTC_COMMITTED
```

fixture catalog 会先逐 byte 验证 source、excerpt、recorded response、Spec 与 provenance，调用方不能覆盖 company、期间或 SEC identity。首次 Cutover 命令预期返回非零 `HUMAN_REVIEW_REQUIRED`：同一 release plan 中无需 HUMAN 审核的 structured Runs 已 FROZEN，需要审核的 lodging Run 仍为 OPEN；JSON 中的每个 `pending_reviews` 项都包含 `review_path`、`review_unit_hash` 与可复制的 `review_command`。此时没有生成 recorded publication。

```bash
python3 tools/vnext_operator.py --json review show --run-dir RUN_DIR --review-unit-hash REVIEW_UNIT_HASH
# 阅读 review.md 后，逐字复制 HUMAN_REVIEW_REQUIRED 返回的命令
python3 tools/vnext_review.py decide --run-dir RUN_DIR --review-unit-hash REVIEW_UNIT_HASH --decision APPROVE --reviewer-id HUMAN_ID --decided-at-utc UTC_DECIDED --reason 'reviewed exact rendered context'
python3 tools/vnext_cutover.py --json --fixture-id FIXTURE_ID --workspace-dir artifacts/vnext/recorded-cold-start --legacy-snapshot-dir outputs --validated-at-utc UTC_VALIDATED --committed-at-utc UTC_COMMITTED
python3 tools/vnext_operator.py --json status --publication-root artifacts/vnext/recorded-cold-start/recorded-publication
```

第二次必须重跑同一 Cutover 命令；它从原 OPEN history resume，完成 reviewed Run finalization、validation、freeze 与无网络 replay，再生成 complete BatchManifest、Projector candidate、recorded validation bundle，并通过 CAS 把 sandbox pointer 提交到 `<workspace>/recorded-publication`。最后的 `status` 会用 pinned PublicationView read-back publication 与 root-mirror hashes。整条 recorded 路径 socket=0，且正式 `outputs/active_publication.json` 与 repository root mirrors 前后必须相同。
自动测试中的 `TEST_ONLY_EXPLICIT_REVIEW` 只证明显式 review UX 和 sandbox transaction；它不是正式 HUMAN Decision、live Cutover 或 full acceptance 证据。真实 operator 不得复制该 reviewer identity，也不得让模型、fixture 或 runner 自动批准。recorded Cutover workspace 的第一层必须使用 `artifacts/vnext/recorded-*` 专用 namespace；live 固定使用 repository-owned `artifacts/vnext/cutover`，任何 live `--workspace-dir` 都以 `LIVE_WORKSPACE_OVERRIDE_FORBIDDEN` 在读取或写入前失败。formal core 还 exact 固定 module-owned repository、`outputs` legacy snapshot 与 publication root；每次有效 live 调用（包括 HUMAN resume）都会先执行 fresh SEC acquisition，再复用 source-exact pinned semantic plan，并把本次 acquisition receipt 单独回绑 audit/full closure。
sandbox publication 仍须闭合 Batch 实际消费的 request-ledger 来源。recorded tier 可以验证历史 row 明确声明的 `LEGACY_WORKING_LOCATOR`，但必须逐项匹配 body/headers 的 repository path、SHA-256 与 size，并把 locator tier/class 写入 portable closure；缺失、歧义或 bytes 漂移都失败。formal/live tier 只接受 `IMMUTABLE_ATTEMPT`，任何 legacy locator 都必须以 `LIVE_SOURCE_ATTEMPT_INCOMPLETE` 停止。

### Granular recorded OPEN Run 与 HUMAN review

`fixture show` 返回的 `prepare_command` 是唯一受支持的 recorded prepare 命令；operator 只从仓库 catalog 解析并逐 byte 验证 source/response/Spec/期间身份，不接受调用方展开或覆盖这些字段。它创建真正的 OPEN Run，但不会联网或修改 active/root outputs。任何 caller-selected response 都以 `RECORDED_FIXTURE_OVERRIDE_FORBIDDEN` 停止：

```bash
python3 tools/vnext_operator.py --json status --publication-root .
python3 tools/vnext_operator.py --json prepare --fixture-id FIXTURE_ID
python3 tools/vnext_operator.py --json status --run-dir RUN_DIR
python3 tools/vnext_operator.py --json review list --run-dir RUN_DIR
python3 tools/vnext_operator.py --json review show --run-dir RUN_DIR --review-unit-hash REVIEW_UNIT_HASH
python3 tools/vnext_operator.py --json review decide --run-dir RUN_DIR --review-unit-hash REVIEW_UNIT_HASH --decision APPROVE --reviewer-id HUMAN_ID --decided-at-utc UTC_TIME --reason 'reviewed exact rendered context'
python3 tools/vnext_operator.py --json resume --run-dir RUN_DIR
python3 tools/vnext_operator.py --json replay --run-dir RUN_DIR
```

`resume` 会在 HUMAN Decision 通过后完成 finalization、Run validation 和 freeze；不要再对已经 FROZEN 的 Run 顺序执行一次 `freeze`。若外部流程已自行完成 finalization，才单独使用 `freeze`。
wrong supersedes、stale context 或 parallel effective tip 会 fail closed；恢复命令以 CLI 返回的 exact Run/ReviewUnit 身份为准。默认不打印 traceback，只有 `--debug` 才打印。

### Granular Complete Batch 与 inactive recorded bundle

```bash
python3 tools/vnext_operator.py --json project --batch-manifest artifacts/vnext/staging/batch_manifest.json --run-dir RUN_DIR_1 --run-dir RUN_DIR_2 --legacy-snapshot-dir . --staging-dir artifacts/vnext/staging/candidate
python3 tools/vnext_operator.py --json publish --publication-root artifacts/vnext/recorded-publication --batch-manifest artifacts/vnext/staging/batch_manifest.json --legacy-snapshot-dir . --staging-dir artifacts/vnext/staging/candidate --validated-at-utc UTC_TIME
python3 tools/vnext_operator.py --json status --publication-root artifacts/vnext/recorded-publication
```

`--run-dir` 必须为 current production registry × B01/B03/B10/B11 的完整同财年 FROZEN Run exact set，可重复任意次；示例中的两个 locator 只是占位。generic `publish` 只准备 inactive recorded bundle，`--commit` 与所有 public generic formal commit API 都以 `FORMAL_CUTOVER_AUTHORITY_REQUIRED`/`FORMAL_COMMIT_REQUIRES_CUTOVER` 失败。正式 forward commit 只由 Cutover orchestrator 在全部 live evidence 到齐后执行。上节受控 fixture shortcut 的 CAS 只提交其固定 `<workspace>/recorded-publication` sandbox，不能借此写正式 active pointer 或 repository root mirrors。

### 正式 qualification、Cutover 与 full acceptance

```bash
test -n "$OPENAI_API_KEY" && test -n "$SEC_CONTACT_EMAIL"
python3 tools/vnext_qualification.py prepare --fixture-id SECOND_LAYOUT_FIXTURE
python3 tools/vnext_qualification.py freeze --frozen-at-utc UTC_TIME
python3 tools/vnext_qualification.py prepare --fixture-id POST_FREEZE_HOLDOUT_FIXTURE
python3 tools/vnext_qualification.py status
python3 tools/run_acceptance.py --scope full --execute-live
```

qualification 的固定顺序是：第二真实布局首次 `prepare` 停在 HUMAN Review，只有有效 HUMAN `APPROVE`、全量 `PUBLISHED` Result 与 `PASSED` Run validation后重跑同一命令才能形成 receipt；`REJECT`/WITHHELD 只保留审计；然后 `freeze` 同时绑定 production semantic tree 与 pre-holdout fixture/Run inventory；最后才加入并 `prepare` 独立 holdout。若 holdout bytes/Run 在 freeze 前已存在，或 holdout 后 semantic tree 漂移，`status` 必须失败。
release input plan 会先验证 request-ledger manifest，再按 exact SEC URL/body hash/accession/document 选择有序 ledger 中最后一个验证通过的 attempt，并绑定 attempt ID、body/header locator 与 locator class。recorded 可保留唯一且逐 path/hash/headers/size 验证的 `LEGACY_WORKING_LOCATOR`，portable closure 必须记录其 tier/class；formal live 只允许 `IMMUTABLE_ATTEMPT`，以 `LIVE_SOURCE_ATTEMPT_INCOMPLETE` 拒绝 legacy class。plan 后 ledger binding 漂移则以 `SOURCE_LEDGER_BINDING_AMBIGUOUS` 失败。
live 只在显式 `--execute-live` 下执行；缺凭据、qualification、HUMAN Decision、三轮稳定、strict parity、fault matrix、rollback/restore 或 terminal checker 任一证据时都不得产生 full PASS。Rollback 只切 committed predecessor pointer，不会重新启用旧 parser。
首次 formal Cutover 会把冻结 legacy root bytes 导入为immutable predecessor A（不运行旧 parser），再把 formal vNext bundle B 绑定 A 并原子建立 initial chain。三次 live attempt 的 request/schema/assistant-output/provider-envelope/model/TransportObservation/Candidate/Evidence/Review/compatibility 会复制进 content-addressed portable audit closure；原 Run workspace 清理后，acceptance 仍须逐 byte 重验该 closure。new、rollback A、restore B 的report/Stage 12/checker 各自共用同一 pinned publication transaction。

```bash
python3 tools/vnext_terminal_cycle.py --json --publication-root . --expected-publication-id ACTIVE_ID --output outputs/terminal_cycle_result.json
python3 tools/vnext_operator.py --json rollback --publication-root . --target-publication-id PREVIOUS_ID --expected-active-publication-id NEW_ID --committed-at-utc UTC_TIME
python3 tools/vnext_operator.py --json restore --publication-root . --target-publication-id NEW_ID --expected-active-publication-id PREVIOUS_ID --committed-at-utc UTC_TIME
```

full acceptance 在每个 new/rollback/restore cycle 只启动一次 `tools/vnext_terminal_cycle.py`；该公开入口以单进程、单次 pinned transaction 顺序执行 Stage 10 Golden→Stage 11 report→Stage 12 active validation→snapshot publish→verify，并在每一步重验同一 pointer/PublicationView。结构化 result 与文件 SHA-256 共同进入 full receipt；任何 gate 缺失、重复、换序或 pointer 切换都使该轮失败。
publication switch 会在 root mirror mutation 前、同一个 exclusive lock 内写 `outputs/publication_switch_intents/` 下的 content-addressed switch intent，绑定 previous/proposed pointer、previous switch tip、mode 与全部 mirror 的存在性/hash/size。共享锁 reader fail closed：pending、多份或 tampered intent 只返回失败，不清理 authority。独占锁 writer/recovery 按 exact pointer 恢复：pointer 已是 proposed 时补齐 connected switch edge 并重建 proposed mirrors；pointer 仍是 previous 时移除本事务 edge、恢复 previous state；其他状态失败。initial A→B 失败还会清理本次 A 孤儿 edge、pointer 与 intent，重试不继承伪历史。

## 内部阶段 00-11（非业务用户产品接口）

以下内部 baseline 命令统一把数据根显式指向一个已存在的干净隔离 candidate checkout；该绝对路径必须不同于本源码checkout 且不能含 active pointer。Stage04/09/11 只生成非迁移候选，迁移指标只能由 vNext Projector/PublicationView 提供。

```bash
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 00_smoke_test_sec_access
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 01_resolve_companies
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 02_inventory_filings
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 03_companyfacts_inventory
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 04_compute_standard_metrics
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 05_fetch_accession_materials
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 06_parse_xbrl_instances
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 07_extract_8k_events
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 08_extract_def14a
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 09_extract_mda_and_risk_text
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 10_run_golden_assertions
python3 scripts/sec_pipeline.py --workspace-dir /ABSOLUTE/CANDIDATE_WORKSPACE 11_build_report
```

阶段 11 的 bounded repair primarily uses local artifacts, but C04 AuditorName repair only fetches the next official SEC candidate while all ordered local facts remain unavailable.
随后阶段 11 生成 coverage、exceptions、validation run manifest、repair validation、最终报告和本 README。

## 验收顺序

### 正式完整验收

```bash
python3 tools/run_acceptance.py --scope full --execute-live
```

只有该命令真实返回 0 且产生 full receipt 才是 formal Cutover 完成。内部 candidate、recorded acceptance、单独 Stage 10/11/12 或 snapshot checker 都不能替代它。

### 第一层：内部 candidate 十家公司功能 gate

下列判断由上节隔离 candidate 的 Stage 10/11 生成，仅证明非迁移输入与局部 gate；它不写 active/root mirrors。

- `outputs/golden_results.csv` 必须与配置/generator/fixture 推导的 assertion exact set 一致、唯一且全 PASS。
- `outputs/stratified_audit.csv` 必须与当前 metrics 推导的五层 deterministic sample exact set 一致且唯一。
- 完整工作区 `outputs/repair_validation_results.csv` 必须全 PASS；轻量审核包中依赖 raw evidence / concept inventory 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`；full gate 本身也不能写成 PASS。
- validation status 只使用 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。缺材料不能写成 PASS。
- 轻量审核包必须在根目录包含 `LIGHT_REVIEW_PACKAGE.marker`；未声明的缺 evidence / concept inventory 工作区必须 `WORKSPACE_INCOMPLETE`。
- full 模式中的关键 `NOT_EVALUATED_MISSING_EVIDENCE` 阻止 GO；light 模式只能把它作为显式 caveat。
- 先读 `outputs/validation_run_manifest.json` 判断本次真正刷新的 validation artifact；旧文件存在不代表本次已评估。
- candidate 阶段 11 的报告写入成功后才发布其 terminal manifest；写入失败必须保持 `IN_PROGRESS`，且成功也不代表 active/full。
- formal terminal cycle 的 stage 12 在成功返回前还必须发布并自验 `outputs/validation_snapshot_provenance.json`；缺失 sidecar、source-input dirty/tree mismatch 或关键 artifact hash mismatch 都使完整批次失败。
- manifest 的 `source_commit` 带 `+dirty` 只说明整个工作树含未提交改动；最终 source 判断以 provenance checker 的 source-input closure 为准。
- `metrics/evidence/coverage/report` 必须能互相追溯一致。

### 第二层：去公司特例验收

```bash
python3 tools/check_no_company_literals.py
python3 tools/check_capability_contract_alignment.py
```

- 生产 extractor 不得出现公司名业务分支。
- `config/`、`tests/fixtures/`、报告模板可以出现公司名。
- 自动审计使用 AST 扫描 Python literal，明细写入 `outputs/scalability_audit.csv`。
- capability checker 只验证 anchor/path/symbol 等结构事实；symbol 存在不等于 claim 已被证明，证据强度仍由 reviewer 判断为 direct / partial / structural / none。

### 第三层：第 11 家公司测试

- 新增同行业公司只允许改 `config/company_registry.csv` 和 `tests/fixtures/`。
- 不允许为新增同行业公司改 `scripts/sec_pipeline.py`。
- `repair_validation_results.csv` 的 `eleventh_company_behavior_*` 必须 PASS。

失败时脚本 exit nonzero，并把逐项原因写入对应 outputs CSV。

## 本轮修复的请求边界

- B01/B03/B10/B11 的正式结果只来自 vNext Run/Evidence/Review/Projector；legacy lodging/B03 resolver、repair 与通用 upsert 对这些指标均已退出，任何重新写入尝试以 `LEGACY_PATH_STILL_ACTIVE` 失败。
- 非迁移能力继续保留：例如 B12 RPO/cRPO 优先 instance fact、C03 PeoTotalCompAmt、FI A01/A02 ratio facts，以及 coverage、exceptions 与 report consumer。
- C04 先检查 target 10-K/A，再在 AuditorName 不可用时回退同 CIK、同期间原始 10-K；空白/冲突事实必须降级；仍缺失时才按候选顺序最小补抓 SEC 官方 XBRL instance；期间起点只允许由同 CIK prior 10-K 推导；所有请求仍通过 `SecHttpClient.fetch(...)` 写入 `evidence/requests_log.csv` 及其 exact-set manifest。
- full validation 从 submissions 推导 FY 8-K inventory，重放 raw hdr/primary item 并与 `events.csv` exact-set 比对；正向 count 逐 event component 保留 evidence，零值只在完整扫描确无匹配项时成立。
- `metrics_matrix.csv` 必须恰好包含 registry/profile/applicability contract 推导的 unique `(company, metric_id)` set；`coverage_matrix.csv` 必须与该 matrix exact key set 完全一致。
- `outputs/stratified_audit.csv` 固化验收分层抽样：STD_XBRL/DERIVED、DIM_XBRL、DEF14A、MDA/TEXT、8K_ITEM；缺行、重复或多余样本均失败。

## P0 validation 失败定位

- 先打开 `outputs/repair_validation_results.csv`，按 `check_id` 查看 FAIL 行。
- snapshot checker 失败时，先区分 source-input dirty/tree mismatch、manifest/provenance identity mismatch 与具体 artifact SHA-256/size mismatch。
- 对证据缺失类失败，按 `(company, metric_id)` join `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
- 对 matrix/coverage 完整性失败，先看 details 中的 missing、unexpected 与 duplicate keys；禁止用固定行数或复制现有行凑齐集合。
- 对 8-K 失败，按 submissions→FY inventory→raw filing→events→metric/component evidence 顺序核对 missing、unexpected 与 duplicate identity。
- 对 C03 失败，检查 `outputs/concept_inventory/*_ecd.csv` 中目标 `period_end` 的 `PeoTotalCompAmt`。
- 对 FI Basel ratio 失败，检查对应 `outputs/concept_inventory/*_instance.csv` 的 ratio facts。
- 对请求边界失败，先检查 `evidence/requests_log_manifest.json` 的 row count/hash、Git HEAD/base 有序前缀与下游/sidecar 反向覆盖，再检查 `evidence/requests_log.csv` 的 URL、User-Agent、retry_attempt、body/header locator 和 content_sha256。
- 对 `NOT_EVALUATED_MISSING_EVIDENCE`，不要把空 failure list 解释为通过；按 details 补齐所需材料后重跑。

## 主要输出

- `outputs/metrics_matrix.csv`
- `outputs/metric_evidence.csv`
- `outputs/basel_ratio_candidates.csv`
- `outputs/governance_signals.csv`
- `outputs/coverage_matrix.csv`
- `outputs/exceptions_and_review_items.md`
- `outputs/repair_validation_results.csv`
- `outputs/validation_run_manifest.json`
- `outputs/validation_snapshot_provenance.json`
- `outputs/stratified_audit.csv`
- `outputs/events.csv`
- `outputs/golden_results.csv`
- `outputs/implementation_map.csv`
- `evidence/requests_log_manifest.json`
- `REPORT_十公司财务指标.md`

## 轻量审核包

- 审核包只纳入代码、配置、fixture、关键 outputs 和报告；不纳入 `evidence/`、大体量 `outputs/concept_inventory/`、`__pycache__/` 或 `.DS_Store`。
- 轻量包中 `python3 scripts/12_validate_repair.py` 运行 `LIGHT_REVIEW_MODE`：可重跑代码级、矩阵级和随包 audit gate；缺 raw evidence 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`。
- 轻量包可发布 `LIGHT_PACKAGE_NO_GIT` provenance，用于证明随包 source/artifact bytes 未漂移；它仍不能替代 full Git history 或 raw evidence validation。
- 轻量包中 `python3 scripts/10_run_golden_assertions.py` 重算随包 `outputs/golden_results.csv` snapshot integrity，通过时输出 `PASS: LIGHT_REVIEW_MODE`；完整数值 golden rerun 需要本地完整 `evidence/`。
- reviewer 必须以 manifest 的 `refreshed_artifacts` / `not_refreshed_artifacts` 和 snapshot checker 共同判断新鲜度，不能只检查 CSV 是否存在。
- 新写入的证据 locator 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`；历史绝对路径只作 relocation hint。
- `evidence/requests_log.csv` 的 response body 也使用上述 portable 字段，headers 使用 `headers_repo_relative_path`；`requests_log_manifest.json` 以严格 JSON key/type 与 CSV 行 schema 绑定整表 row count/hash；working ledger 必须保留 HEAD 有序前缀；PR checker 先要求 base/HEAD 的每条 current/legacy row 与声明 schema 精确同宽，再对 legacy base 独立规范化 portable 完整字段、对 current base 逐字段保留有序前缀，之后只允许合法尾部追加；下游/sidecar 反向覆盖完整集合；新 attempt 指向 content-addressed immutable copy；旧 `url/local_path/sha256` 只作为显式 legacy bootstrap 输入，常规阶段不会为缺 manifest 的日志重签。mutable submissions 重放必须匹配 ledger 中最新成功 200；filing-bound archive 文档若存在冲突成功 bodies 则失败。无 Git history baseline 或历史 hash 对应原 bytes 时，full gate 必须 NOT_EVALUATED。
- `outputs/implementation_map.csv` 映射 I1-I8 的实现位置、validation id 和当前状态，供审计方逐项复核。
- `GO WITH CAVEATS` 是 pipeline self-verdict；`ACCEPT WITH CAVEATS` 仅保留给外部审计验收结论。
- 包清单写入 `outputs/review_package_manifest.md`；压缩包写入 `outputs/review_package/`。
- 若审核官需要追溯 raw SEC source，回到本地完整工作区读取 `evidence/` 和 `outputs/concept_inventory/`。
