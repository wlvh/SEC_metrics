# Validation snapshot provenance

## 1. 解决的问题

`outputs/validation_run_manifest.json` 回答“哪一次 validation 刷新了哪些 tracked audit artifact”，但它原先不能回答两个更强的问题：

1. 这次运行使用的代码、配置、测试 fixture 与验收文档，是否仍等同于当前 checkout？
2. manifest、报告、矩阵、证据、Golden、request ledger 与 validation CSV 在运行后是否被修改？

只比较 `manifest.source_commit` 与当前 `git rev-parse HEAD` 也不够。完整批次通常会在验证后提交生成 artifact，PR merge 又可能产生新的 merge commit；commit SHA 可以变化，而真正影响行为的 source tree 未变。相反，整个工作树的 `+dirty` 也可能只来自预期生成的 `outputs/`，不能据此判断源代码被修改。

因此当前模型把 provenance 分成两层：

```text
source-input closure
    Requirement、MetricSpec、代码、工具、配置、测试、指标定义、
    能力契约和核心验收文档

acceptance artifact closure
    manifest、报告、README、metrics/evidence/coverage/Golden、events、
    request log/manifest、full request-attempt recursive exact set，
    以及本轮 refreshed validation artifacts
```

第一层用 deterministic tree digest 绑定；第二层逐文件记录 SHA-256 与 size。

## 2. 核心文件

- `config/validation_source_policy.json`：runtime/acceptance source 与非 source 文档角色的机器可读真相源。
- `scripts/validation_provenance.py`：读取 policy、校验 SOP 权威引用、捕获、发布、验证和 fail-closed helper。
- `scripts/11_build_report.py`：无参数时只分派active stage 11；legacy candidate使用`sec_pipeline.py --workspace-dir <absolute-isolated-root> 11_build_report`显式选择数据根。wrapper不做pre/post authoritative write；隔离candidate一旦生成新artifact，旧sidecar会因byte mismatch失效，正式active路径只读一次pinned `PublicationView`。
- `scripts/12_validate_repair.py`：stage 12 返回零之前，发布并重新验证 provenance。
- `tools/check_validation_snapshot.py`：读取当前 checkout 与 artifact bytes 的独立验收入口。
- `outputs/validation_snapshot_provenance.json`：成功 full/light terminal run 的 sidecar。

## 3. Source-input closure

`config/validation_source_policy.json` 是 source/document 角色的机器可读真相源。Git checkout 中，closure 由 `git ls-files` 对 policy 中的 `runtime_source_directories`、`acceptance_source_files` 以及 policy 文件自身求精确集合，不再由 Python tuple 手工维护。

当前 runtime source directories：

```text
catalog/
scripts/
tools/
config/
tests/
requirements/
```

当前 acceptance source files：

```text
01_SOP_SEC_10公司单年指标计算_直接SEC.md
02_指标定义_SEC_10公司单年指标.md
AGENTS.md
CIK变更应对方案.md
SOP.md
TESTING.md
architecture.md
capability_contract.json
docs/business_user_guide.md
docs/validation_snapshot_provenance.md
interact.md
```

policy 同时明确不进入 source tree 的角色：`README_RUN.md` / `REPORT_十公司财务指标.md` 是另行做 byte binding 的 generated artifacts；`PR_Checklist.md` / `.github/pull_request_template.md` 是发布治理；`.gitignore` 是仓库卫生；`SEC_metrics_Project_Overview_and_Expert_Guide.md` 是解释性非权威文档。`CIK变更应对方案.md` 会影响身份连续性和跨 CIK 口径，因此属于 acceptance source，而不是解释性背景。

loader 会解析 `SOP.md` 每个表格的“权威引用”列。引用必须由 runtime source、acceptance source、snapshot artifact 或非批次发布治理角色明确覆盖；未分类引用立即失败。被标记为 `explanatory_non_authoritative` 的文件不能继续留在权威引用列，否则也立即失败。policy 文件路径由代码作为 bootstrap source 单独加入 closure，因此 policy 即使把 `config/` 从 runtime directories 移除，也不能把自身未提交修改隐藏掉。

每个文件以如下 record 进入整树 SHA-256：

```text
repo_relative_path NUL byte_length NUL content_sha256 LF
```

路径按字典序排序。任何 tracked modification、staged modification、删除或 closure 内 untracked 文件，都会使 stage 12 在运行主 gate 前失败。symlink 或非 regular file 也失败。

无 Git 的显式 light package 不能通过删掉某个 acceptance source 文件来缩小 closure。policy、自身声明的全部 acceptance source files 和 runtime source directories 都必须存在，并且必须是非 symlink regular file/real directory；缺失任一项即失败。light package 仍可按随包实际内容枚举 runtime source directories，但不能省略 `01_SOP...md`、CIK identity rules、能力契约、指标定义或核心治理/验收文档。

生成的 `evidence/`、`outputs/`、报告和 README 不进入 source tree。full 模式下，policy 声明的 `evidence/request_attempts/` 由 artifact closure 按 recursive exact file set 单独绑定；其他文件只在进入核心或 refreshed artifact 清单时绑定。这样 stage 00–11 的合法生成副作用不会被误判为 source dirty，也不能在 stage 12 后静默删除、新增或篡改已绑定的 immutable attempt。

## 4. Commit 与 tree 的关系

provenance 同时记录：

```text
source_commit
source_input_tree_sha256
source_file_count
source_dirty_paths
```

验收规则：

- stage 12 同一次运行内要求 Git HEAD 不变、source tree digest 不变、source dirty paths 为空；
- 当前 checkout 与记录 commit 完全相同，是最直接匹配；
- artifact commit 或 merge commit 造成 SHA 不同时，独立 checker 只有在完整 source-input tree digest 和文件数仍一致、当前 source closure 仍 clean 时，才给出 warning 并继续；
- tree digest、文件数或任何 source byte 不一致时失败，不能以“commit 看起来相关”替代内容证明。

这比简单的 `source_commit == HEAD` 更严格地约束真实行为输入，同时不会把内容等价的 merge commit 错判为不同实现。

## 5. Artifact closure

full snapshot 至少绑定：

```text
outputs/validation_run_manifest.json
outputs/golden_results.csv
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
outputs/coverage_matrix.csv
outputs/events.csv
outputs/<manifest.refreshed_artifacts>
evidence/requests_log.csv
evidence/requests_log_manifest.json
evidence/request_attempts/**（仅 full；policy 声明目录的 recursive exact file set）
REPORT_十公司财务指标.md
README_RUN.md
```

每个 key 的值严格只有：

```json
{
  "sha256": "<64 lowercase hex>",
  "size_bytes": 123
}
```

sidecar 的 key set 必须和当前 manifest、mode 与 policy 推导的 expected set 完全一致；full artifact directory 中删除、新增、symlink、hardlink、size 变化或 SHA-256 变化都失败。light package 不要求被明确省略的 raw evidence，也不要求 full-only artifact directory，但仍绑定随包 source 与 artifact bytes，并标记 `LIGHT_PACKAGE_NO_GIT`。

## 6. Terminal publication 顺序

没有 active pointer 的 legacy/light 或隔离 candidate 沿用原有终态链：

```text
stage 11 start
→ bounded repair / report / README
→ 旧 provenance 因 artifact bytes 改变而不再可验收

stage 12 start
→ 删除旧 provenance
→ 捕获 clean source snapshot
→ 运行既有 repair validation 与 report terminal publication
→ 仅在 manifest 为 FULL/PASSED 或 LIGHT/PASSED_WITH_CAVEATS 时计算 artifact digests
→ 原子写 provenance sidecar
→ 从磁盘重新读取并验证
→ 成功后 stage 12 才 exit 0
```

正式 vNext active 路径使用不同但同样 fail-closed 的顺序：

```text
publisher 验证 complete candidate bundle
→ 独占锁内写 content-addressed publication switch intent
→ 原子写 root mirrors
→ predecessor CAS 提交 outputs/active_publication.json
→ 完成 committed switch receipt、重建/校验 mirrors 并删除 exact intent
→ 启动一次 tools/vnext_terminal_cycle.py
→ 单进程 pin 一次 PublicationView transaction
→ stage 10 校验 bundle 内 Golden
→ stage 11 复用该 transaction，只读并校验 bundle 内 report
→ stage 12 复用该 transaction，校验完整 bundle、receipt 与 root mirrors
→ 发布并回读 validation snapshot provenance
→ snapshot verifier 复用同一transaction完成终态只读确认
```

active Stage 11 不调用 AI/SEC、不运行 repair，也不写 authoritative artifact。active Stage 12 允许写终态 provenance sidecar，但不得重新生成或改写 active bundle/root mirrors；报告 provenance notice 已是 prepared bundle 的受哈希内容。rollback/restore 只切 committed pointer 并从所选 bundle 恢复 mirrors，随后重新执行同一 Stage 11/12/checker 链，不会重新启用 legacy producer。

switch intent位于`outputs/publication_switch_intents/<sha256>.json`，并以`PUBLICATION_SWITCH_INTENT`绑定previous/proposed pointer、previous switch receipt tip、switch mode及全部root mirror的present-or-null/hash/size。PublicationView在shared lock内先确认没有pending intent；pending、多份或tamper只读失败且不清理。writer/recovery仍持exclusive lock：pointer==proposed时补齐或幂等验证switch edge并从proposed bundle重建mirrors；pointer==previous时移除本事务edge、验证previous tip并恢复previous state；其他pointer状态fail closed。initial A→B失败会移除A孤儿edge、pointer与intent，避免下一次重试继承伪history。

若legacy/light stage 12已生成成功manifest/report，但provenance postflight写入或自验失败，wrapper会：

1. 删除可安全识别的未完成或旧 regular sidecar；unsafe alias 保留为 checker 必然拒绝的状态；
2. 把 manifest `result` 降为 `FAILED`；
3. 把报告 verdict 改为 `NO-GO` 并写入失败原因；
4. 非零退出。

因此不会留下“stage 12 exit 0 但没有 source/artifact binding”的成功态。

active stage 12不执行上述legacy FAILED/NO-GO重写。active postflight失败时只移除未完成sidecar、依据当时official pointer恢复root mirrors并非零退出；committed bundle及其manifest/report bytes保持不变。

## 7. 人工验收命令

```bash
git rev-parse HEAD

python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(
    Path("outputs/validation_run_manifest.json").read_text(encoding="utf-8")
)
print(manifest["source_commit"])
PY

python3 tools/check_validation_snapshot.py
```

前两条命令用于观察 commit 关系；第三条才是最终内容验收。checker 输出：

- `PASS`：source closure 与 artifact closure 均匹配；
- `WARNING`：commit SHA 改变，但完整 source-input tree 内容等价；
- `FAIL`：缺 sidecar、schema/identity 失配、dirty source、tree mismatch、artifact hash/size mismatch 或路径边界错误。

## 8. 边界

- sidecar 是仓库内自证明，不替代外部时间戳、签名或不可篡改存储；能同时改写全部文件并重签的人仍在本地信任边界内。
- Git workspace guard 与后续 Git 命令不是一个原子系统调用，不宣称抵御恶意同 UID 进程的主动 namespace TOCTOU。
- recorded acceptance 的 socket=0 证明依赖 macOS `/usr/bin/sandbox-exec` 对整个子进程树施加 `(deny network*)`；Python audit hook 只是第二道保护。该 executable 缺失时以 `OFFLINE_PROCESS_SANDBOX_REQUIRED` fail closed，不把较弱的同进程保护描述成等价证据。
- source closure 是显式 policy。新增会影响运行或验收的路径时，必须在 `config/validation_source_policy.json` 分类，并同步文档和负例测试；新增 SOP 权威引用若未分类会被 checker 拒绝。
- provenance 证明 bytes 一致，不证明业务方法本身正确；Golden、repair validation、外部审计和人工判断仍各自负责自己的结论。

## 9. vNext formal publication 与当前 provenance 的关系

Issue #12 的 exact FSD、immutable R2、exact R3 Addendum、Decision Register、baseline、release plan、旧路径 inventory、semantic runtime、`catalog/`、`fixtures/` 与 vNext code/tests/tools 都进入 source-input closure。Candidate binding使canonicalizer semantic version 2→3，source-plan latest verified immutable request-attempt binding使其3→4，旧路径 inventory冻结Git blob binding使projector semantic version 2→3，D-06 SYSTEM review渲染使review renderer semantic version 2→3；当前semantic runtime versions hash为`sha256:f724d52688b92935d5de6e2e8000fb3c65a3ee66b316dc8c646c8bef11b551a9`。任一 R2/R3/FSD/Decision 或 semantic byte/path 变化都会使旧 Requirement、approval、Run、Batch、publication 与 snapshot失效；GitHub 当前可变 Issue body不是运行时唯一 authority。

机器可读policy还把以下目录定义为full artifact closure：`artifacts/vnext/qualification`、`evidence/request_attempts`、`outputs/failure_first_receipts`、`outputs/publication_fault_receipts`与`outputs/vnext_cutover_audits`。full snapshot要求这些目录存在、regular且递归bytes闭合；不能把failure-first、qualification、fault或portable live audit receipt留在临时目录后口头声明完成。

qualification freeze不仅绑定production semantic tree hash，也绑定freeze时已存在的fixture/Run namespace exact inventory。第二真实布局必须先形成有效 HUMAN 或D-06 SYSTEM `APPROVE`、全量`PUBLISHED` Result和`PASSED` Run validation的receipt；`REJECT`/WITHHELD只保留Run审计。holdout fixture与Run必须在该inventory中不存在，且只能在freeze后加入并与second layout使用不同company/CIK。这样“post-freeze”由bytes与namespace证明，而不是时间口述。

artifact closure 是动态的：没有 `outputs/active_publication.json` 时，沿用第 5 节的既有 root closure；pointer存在时，provenance verifier 通过一个 pinned `PublicationView` 读取 official pointer，验证唯一 selected immutable bundle、`publication_manifest.json`、bundle exact namespace与全部 root mirrors，并把这些 exact bytes纳入 sidecar。任意未被 pointer选择的 sibling publication、OPEN/FAILED workspace与 `latest_run_status` 不进入 active closure，避免把开发/失败尝试误写成业务 snapshot。

每个 prepared bundle 自身还有一层 exact binding；release input plan先从通过manifest验证的ledger按exact source identity选择最后一个验证通过的immutable request attempt，并将attempt/body/header/class纳入plan identity；recorded可显式保留唯一legacy working locator，formal live拒绝该class。publisher再从verified Batch实际消费路径派生SourceReference/`request_attempt_id` exact set，验证整表manifest、声明locator与immutable body/header，并只绑定最小合法ledger prefix：

```text
Requirement hashes
+ FROZEN Run content/audit hash
+ ReviewUnit / Trace / DerivedAsset identities
+ request-ledger used prefix/source identities
+ complete legacy-compatible artifact file set
+ PASSED publication validation receipt
→ immutable PublicationManifest
→ lock + predecessor CAS
→ active pointer（唯一正式 commit point）
```

recorded publication writer最高生成`PASSED_RECORDED_ONLY`且不能移动正式pointer；R4 acceptance runner则只封存并发快速本地证据并最高返回`PASSED_FAST_LOCAL_ONLY`。两者都不等于 formal live。formal writer要求clean committed source并生成`FULL_VALIDATION/PASSED` candidate。bundle 的 `publication_validation_receipt.json` 在 preparation 前产生并被 manifest hash；最终 acceptance receipt 位于 bundle 自哈希之外，避免循环证明。`latest_run_status` 独立于 active bundle，最近失败/withheld尝试不得改写上一成功 active。

acceptance receipt 还有一层独立的运行 authority binding：在 recorded/full gate 前记录 clean source commit/tree/file count，并绑定 baseline、Decision Register、FSD、immutable R2、legacy inventory、exact R3 Addendum、release plan 与 semantic runtime 的完整 Requirement hash map；recorded gate 后重读并要求 exact 相等，full final evidence还必须回绑同一值。R4 recorded gate只运行六个并发直接用例与两个静态 audit，不启动全仓、隔离 repository/worktree 或 freeze/replay 测试。live acquisition只从固定repository-owned `artifacts/vnext/cutover`恢复，caller不能覆盖workspace authority；pinned receipt在Cutover resume与full封口时都按当前`sys.executable` name/binary SHA-256、五条固定命令、ledger prefix/tail、attempt exact set和inventory current bytes机械重验。持久化前，runner递归把repo/output/current Python/sandbox executable替换为`$REPO_ROOT`、`$ACCEPTANCE_OUTPUT`、`$PYTHON_CURRENT`、`$SANDBOX_EXEC`等portable token；`runtime_bindings`保存executable name、availability与binary SHA-256，残余host path只保存path hash。本机绝对路径不会进入receipt，但logical/executed argv、return code、duration、stdout/stderr digest及NOT_RUN原因仍保留。acceptance 自己生成的 semantic/scalability receipts 位于本次 `outputs/acceptance_receipts/recorded_gate_runs/<run-id>/`，只能包含两个声明的 regular files；full 按 repo-owned path 重新打开并重算 SHA-256。root scanner outputs、caller 自报 hash、旧 receipt、absolute/`..`/symlink escape 或 dirty/drift source 均不能闭合该证据。这一层不替代 stage 12 sidecar，也不会把快速本地证据提升为 full。

正式core还exact固定module-owned repository、上述workspace、`outputs` legacy snapshot与publication root，fault-matrix public/core沿用相同authority。每次有效live调用（包括HUMAN或SYSTEM/committed resume）都fresh运行固定SEC阶段；历史disk receipt只允许重验source-exact pinned semantic plan，不能作为本次执行证明，本次receipt以`invocation_sec_acquisition`单独进入audit/full closure。

recorded runner 在启动子进程前逐 byte 备份 active pointer、root mirrors 与 provenance sidecar，OS sandbox同时禁止这些路径写入。若仍观测到漂移，runner先恢复 exact bytes，但 receipt 仍以 `RECORDED_ACTIVE_STATE_CHANGED` 失败；若结束状态不可读，则恢复后以 `RECORDED_GATE_EXECUTION_FAILED` 失败，不能因补偿成功而声称本次运行无漂移。full runner 在每次 Cutover child 返回后重新读取 official state；非零、review blocker或非法结果若意外提交，必须回到调用前 predecessor，首次无 pointer 时恢复调用前 root bytes，并持久化 recovery receipt。该补偿不回滚独立 append-only request ledger，不构成任何review Decision，也不改变原 blocker。

active closure与checker集成已有动态测试，但本轮仓库没有 committed active pointer，因此现有 sidecar仍不能证明vNext active Run/Review/Trace。第二布局/holdout qualification与SEC acquisition receipts已产生；真实 Cutover仍须成功完成live三轮、有效review、十公司staging与active publication evidence。三次live Run不能只引用可清理workspace：Cutover会把exact request/schema/assistant-output/provider-envelope/model/TransportObservation/Candidate/Evidence/Review/compatibility复制到`outputs/vnext_cutover_audits/<content-id>/`；Candidate绑定assistant-output hash，provider-envelope hash保持独立审计。acceptance删除或离开原workspace后仍按manifest逐byte重验。首次Cutover把冻结legacy root bytes只读导入为verified predecessor A，再提交formal B；public generic formal receipt/commit API不能执行该写入。随后执行new B→一次单进程terminal cycle→rollback A→同一终态入口→restore B→同一终态入口，每个cycle复用一个pinned transaction，并绑定五项gate exact set与结构化result文件SHA-256。rollback只切pointer并重建mirrors，不回滚request ledger，也不重新启用旧parser。本轮live Reader三次因provider `Insufficient Balance`失败，故无这些后续运行receipts，不能由实现测试替代。
