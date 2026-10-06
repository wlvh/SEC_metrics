# 与 #54 的接口（#47 历史侧）

[#54](https://github.com/wlvh/SEC_metrics/issues/54)已完成，其公司入口通过PR57进入main（`8588ccbbb1c91d81e0fb1a89dff3575214282549`）。按COLLAB-28-47-v1.3，#47负责历史能力在该入口中的接入与验证；不等待原执行者，不另建公司pipeline。后续期间、来源依赖、运行版本与读取变化同时完成必要入口适配，验证当前财年与旧任务/旧Run兼容。以下各节保留原实验、失败及固定版本证据；它们不代替新增接线或完整五年业务验收。

已读：#54 正文（2026-10-02 13:47 UTC 版本）、上述评论、COLLAB-28-47-v1.1。本方固定提交：`815c7820`（`task/sec-history-five-year`）。

## 1. 历史入口（固定 `815c7820`）

| 接口 | 入口 | 说明 |
|---|---|---|
| 期间选择 | `scripts/vnext/normal_period_selection.py::resolve_period_selection(repo_root, company_id, report_end=… 或 fiscal_year=…)` | 返回经验证的 `period_selection`：目标期间、本期与上期申报、选报/选值政策、来源身份。财年请求读候选申报自己的 DEI，不按日历推断。调用方回传的 selection 不被信任：`restore_period_selection` 在数据根上重推并要求逐字段相等。 |
| 逻辑公司与 CIK 角色 | `config/company_registry.csv`；`normal_history_catalog.py` | 后继注册人的完整目录里没有更早年报时，读前身自己的目录（Paramount 813828），选择记录点名 `period_registrant`，主体政策用该注册人自己的，不跨主体拼前期。登记表没点名的 CIK 不读。 |
| 前期与窗口外依赖 | `normal_history_plan.plan_historical_sources(repo_root, company_id, count=5)`；`historical_source_acquisition.declared_frame(repo_root, company_id, years=5)` | 前者声明年报链（含第一年的上一期）、accession 索引、submissions 索引与历史分片、Company Facts；后者再并上事件窗口 8-K 正文与头文件（按已登记主/前身 CIK）、代理材料、年报 XBRL 实例（`historical_event_sources.py`、`historical_governance_sources.py`、`historical_instance_sources.py`）。每行带 URL、角色、消费者、期间和保存状态（`VERIFIED_SAVED_SOURCE`、需新取、`SNAPSHOT_REFRESH`）。目标年正文未保存时，事件窗口与代理不可声明，按名记为限制而不是零份。 |
| 安装与 Run | `historical_run.install_historical_run_inputs(data_root, company_id, metric_id, period_selection, source_root=…)` → binding；`historical_run.create_historical_run(data_root, run_dir, company_id, metric_id, binding_id, freeze=True)` | 一期间一个数据根即可（同一来源状态下各指标共用）；安装与建 Run 都从数据根重建输入并要求与安装时的绑定逐字节相同。 |
| 结果读取 | `historical_projection.render_historical_run(data_root, run_dir, frozen=True, persist=True)`；`historical_run_receipts.read_run_receipt(run_dir)` / `collect_run_receipts(runs_root)` | 公共行与收据写在 Run 目录旁（`<run名>.row_receipt.json`），收据自带行/证据哈希；读取只核对 manifest 的三个文件哈希，不重放、不重算。冷读用另一进程的 `load_frozen_run`。 |
| 批量与覆盖 | `docs/evidence/issue47_history/period-batch/frame_batch.py <plan.tsv> <out> --workers N`；`tools/vnext_history_coverage.py --source-root … --runs-root …` | 计划每行是“标签、公司、期末、指标列表”；每个期间一个工作进程、一个数据根，冷读抽检。 |

运行历史 Run 的代码树必须打上本方的注册补丁 `docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch`：`issue_47_v1` 世代没有在 #28 被绑定的 `requirement_profile.py`、`run_store.py` 等六个文件里注册，补丁改的正是这些文件，所以同一棵代码树一次只满足一个世代（#28 的普通 Run 或 #47 的历史 Run）。这是 ratchet 的既有形状，不是为 #54 新增的限制；#54 若要在同一环境同时跑两种 Run，需要两棵运行树或另行设计，不能把补丁打进 #28 的执行路径。

## 2. 获取会话的导出/恢复不是公司交接物

`scripts/vnext/historical_source_export.py` 解决的是“把在获取机器上做的那次 SEC 获取带回一个 checkout”，不是按公司交接：

- **按账本行分组，不按公司。** `export_acquisition` 把本次会话追加的全部账本行、这些行引用的响应与头文件、槽位记录，按行号分组写成确定性 gzip 归档，加一份封印索引；导出前要求账本已登记且冻结重放接受。
- **恢复依赖整份受信基线。** `restore_acquisition` 要求导出索引里的基线清单摘要等于读取方的 `config/normal_candidate_sources_v1.json`，先用 `install_historical_source_inputs` 把读取方 checkout 的整份受信基线（全部公司的已存原件与 #28 的基线账本）装进新数据根，再叠加导出的全部行，然后用冻结的 `validate_acquisition_checkpoint` 校验整条账本前缀，最后把检查点写进读取方 checkout 的 `.git` 日志。
- **不能按公司裁剪。** 冻结重放校验的是“账本延伸受信基线、每行绑定一个槽位、每个成功的字节就是它那行点名的不可变尝试”，槽位还串成一条认领链；删掉别的公司的行，前缀、槽位链和检查点都不再成立。
- **不能自证来源。** 导入记录写明它证明了什么（上面三点）和没证明什么（这些行确实来自 sec.gov——那靠会话记录、GitHub 上的批准与开跑标记，以及发请求的主机）。不能让一个包凭自己的 JSON 和哈希把自己登记成 LIVE。

可以复用的：归档与封印索引的格式和逐成员核对；冻结重放作为准入检查；导入记录“证明了什么/没证明什么”的写法；`declared_frame` 作为“某公司某期间需要哪些 URL”的权威清单（公司交接物该携带哪些原件，应由它回答，而不是按 CIK 子串匹配 URL）。

不能当成公司交接物的：导出件本身（全部公司混在一起，且只有叠在整份基线上才可校验）；恢复出的数据根（含全部公司与 #28 基线）。

同一受信基线的前提目前成立：`config/normal_candidate_sources_v1.json` 在 #28 的 `0bc24734` 与本方 `815c7820` 上是同一个 blob（`9ec97694`）。但恢复代码、`issue_47_v1` 与上节的注册补丁都在本方分支上，从 #28 提交起步的树里没有。

## 3. 分工建议

- **公司交接物由 #54 实现**（携带完整账本元数据、只裁剪公司原件，按 #54 第 3 节；它与上节的整包导出是两件事）。#47 不另写公司包，也不改自己的导出格式去迁就它。
- **#47 维护**：期间选择、来源依赖声明（`declared_frame`）、历史安装/Run/读取入口、注册补丁。这些改变时以 `[shared-with-#54]` 通知，并给固定提交。
- **兼容验证**：#54 给出固定提交的公司交接物后，本方在已支持的历史入口上验证：用它装出的数据根解析同一期间选择、安装、建 Run、冷读，与本方现有结果比较业务值、期间、主体与状态。只验证本方实际支持的入口，不替 #54 做全部五年业务验收。
- **不同获取历史的账本不能拼接**：本方的历史获取账本（`issue_47_v1`，两份批准；导出件索引记受信基线 984 行之后追加的 1547 行）与 #28 的账本是不同的追加历史，不互为前缀；交接时保留各自来源历史身份，遇到混合应明确拒绝。

## 4. 执行端原件

本方已取得的原件都在分支上的导出件里（`evidence/issue47_acquired/`，含两份批准下的全部行），用 `tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <新目录>` 可在一个有本方代码树（及上述同一受信基线）的 clone 里恢复成可校验的数据根；不需要复制任何私有日志，也不动用任何调用额度。录制夹具（`RECORDED_TEST_ONLY`）与真实获取的记录分开标明。

## 5. 必要适配点与读写位置（COMPANY-SEPARATION-v2.1，2026-10-02 实测）

#54 下一步的单公司实验依次是：在现有录制机制下新增捕获、导出、在新环境恢复并准入、计算。本节按这个顺序写本方入口，列出实测到的、必须由交接设计回答的问题。实测在一份代码副本上进行：副本只读，计算时用 `env -i HOME=/nonexistent`，来源根是由 `evidence/issue47_acquired/` 恢复出的数据根。材料见 `compute-side-probe/`。

### 5.1 实验经过的本方入口

- **捕获**：`historical_sec_session.recorded_historical_session(root=…, response=…)` 只做录制测试（`RECORDED_TEST_ONLY`），不开网络，不给真实获取信用，配置了预算根就拒绝。`capture_pending(company_id=…)` 只取 `declared_frame(repo_root, company_id, years=5)` 声明的行，所以账本实际引用的历史原件、前期和窗口外依赖、前身 CIK 的申报、历史分片都在其中。`register_checkpoint()` 先用冻结的 `validate_acquisition_checkpoint` 重放；通过后，才把检查点写进本检出的 `.git/ordinary-source-authority/acquired/<账本 sha256>.json`。
- **导出**：`historical_source_export.export_acquisition(ledger_root=…)` 按账本行号分组，只导出受信基线 984 行之后追加的行。导出前要求账本已登记，且冻结重放接受。
- **恢复**：`restore_acquisition(export_dir, out_root)` 要求 `out_root` 不存在，并要求读取方 `config/normal_candidate_sources_v1.json` 的摘要与导出记录一致（现为 `6bdb4835…`）。它先装入整份受信基线，再叠加导出的行，然后做冻结重放；检出有 `.git` 目录时才写登记。
- **准入与计算**：先 `historical_run.install_historical_run_inputs(…, source_root=<恢复出的 source-inputs>)`，它调用与 #28 共用的冻结安装 `normal_run_v3._install_case_inputs`；再依次 `create_historical_run`、`render_historical_run(persist=True)`，最后在另一进程 `load_frozen_run`。

### 5.2 必要适配点

1. **同一账本里的获取原件不能按公司裁剪。** 冻结的 `validate_acquisition_checkpoint` 对账本里每个成功行调用 `_proof`，要求该行点名的不可变尝试（正文与头文件）在被校验的数据根里。`checkpoint_installation` 把这些路径全部列为依赖，冻结安装再把它们拷进每个 Run 的数据根。共有 44 个模块经已绑定的名字调用 `verify_ordinary_source_proofs`，包括 #28 的普通路线和本方的历史路线。因此，交接物若只带本公司在该账本里的获取原件，会在第一条别家公司的成功行处被拒。受信基线里别家公司的原件不受此限：基线行只在被某条证明用到时才检查。实测体量：导出件 52 MB（gzip）；Marriott FY2023 一个期间的数据根 684 MB，其中 `evidence/request_attempts` 占 650 MB、3098 个文件，就是 1547 个获取行的正文和头文件，加上该期间用到的少量基线原件。可选做法有两种：
   - **A**：交接物带上同一账本全部成功行的获取原件，只按公司裁剪基线原件和计算输入。冻结校验不用改，代价是每个数据根都带约 650 MB 的别家公司原件。
   - **B**：给共用的校验和安装写后继版本，允许“账本行在、原件不在”。这是对冻结共用核心的改动，按 v2.1 要先确定实现者和接入版本，本方再在自己的入口验证。
   “最终计算端不能被要求先安装全部公司”是否排除 A，由 #54 按接口判断；若排除，B 是唯一路线。
2. **计算端目前必须在 git 工作区里运行。** 冻结共用安装 `_install_case_inputs` 经 `annual_runtime._authority_files` 在代码根执行 `git ls-files catalog config`，列出要装进数据根的规则文件。实测：在去掉 `.git` 的副本上，三个指标（B01、B04、D01）都停在安装阶段，错误是 `git ls-files … exit status 128`。普通路线共用这个函数，所以普通和历史路线都受影响。给副本补一个只有索引的 `.git` 后（`git init`，对象用 alternates 指向原仓库，`git read-tree <提交>`，共 9.3 MB，不含历史），安装、建 Run、公共行、另一进程冷读全部通过。所以 OpenShift 镜像有两种做法：带一个与代码同一提交的 git 索引，并且 `.git` 必须是目录（读取信任日志时也要求目录，`git worktree` 那种文件形式的 `.git` 不行）；或者给共用安装写一个不依赖 git 的后继，这同样是共用核心改动，处理方式同第 1 条。
3. **信任锚在哪里。** `ordinary_source_authority._trusted_checkpoint`：代码根有 `.git` 时，读 `.git/ordinary-source-authority/{recorded|acquired}/<账本 sha256>.json`；没有 `.git` 时，读代码根下的单个文件 `config/ordinary_source_checkpoint.json`。因为第 2 条，实际只剩前一种。日志按账本 sha256 分文件存放，所以不同的获取历史（本方 1547 行的账本、#54 单公司录制产生的账本）可以各登记一条、互不干扰；每个数据根只带一本账本，不拼接。**本次实测为图省事，把来源准备端登记出的那一条检查点直接复制进了计算端副本的信任日志。这只是实测捷径，不能当作交接方式**，等于复制私有日志冒充授权。正式做法要在两者中选一：计算端对交接物自己做一遍冻结重放，再登记（需要交接物带够校验所需的全部材料，见第 1 条；且计算端的 `.git/ordinary-source-authority/acquired/` 要可写）；或者由经过审查的构建步骤写入这条登记，并按摘要钉住。
4. **HOME 与可写的代码目录。** 本方的恢复和计算路径不读 HOME（实测 `HOME=/nonexistent`）。计算运行前后，代码树（含 `.git`）的 14213 个文件逐个比对路径、大小和修改时间，全部未变。字节码缓存用 `PYTHONPYCACHEPREFIX` 指到可写目录；不设时，Python 遇到只读目录会静默不写。唯一涉及 HOME 的路径是 SEC 真实获取的账本根 `/root/.local/state/sec_metrics/issue47-historical-sec-cloud-v1`。它写在已批准的许可 `config/issue47_historical_calls_v1.json` 里，批准正文按摘要钉住，只用于真实获取，不用于恢复或计算。在 OpenShift 上换到别的位置就等于新许可，需要所有者另行批准；#54 本期的录制实验不涉及它。

### 5.3 读写位置

| 阶段 | 读 | 写 |
|---|---|---|
| 来源准备（捕获、登记、导出、恢复） | 固定提交的代码树；受信基线 `config/normal_candidate_sources_v1.json` 与检出里的 `evidence/`；导出件 `evidence/issue47_acquired/` | 捕获：调用方给的账本根和数据根。登记与恢复：代码树的 `.git/ordinary-source-authority/acquired/`（不可变写入：相同字节可重写，不同字节拒绝）。恢复：新的 `out_root`（`source-inputs/`、`ledger/`、`import-record.json`） |
| 计算（安装、建 Run、公共行、冷读） | 固定提交的代码树及其 git 索引；信任日志里该账本那一条；来源根（只读，可以是挂载的稳定路径；安装只从它拷出，不改它） | 每个期间一个数据根（不得与代码树或来源根重叠，`HISTORICAL_RUN_SOURCE_AND_OUTPUT_OVERLAP`）；Run 目录及其父目录（行收据写在 Run 目录旁边）；`TMPDIR`；字节码缓存目录 |

容器里的 source_root 只要求是稳定路径，不要求覆盖物理来源：安装从它拷贝到数据根，并按账本和证明核对字节。

### 5.4 重启、重复执行与固定输入

- **恢复**：`out_root` 必须不存在。被打断时留下的半成品要删除或换个名字再恢复。登记是不可变写入，同一检查点重复登记没有副作用。
- **获取**：每个槽位按“意图 → 请求 → 终态”的顺序写。会话重启时如有槽位没有终态，会话停下；结果未知（UNKNOWN）不自动重试，交给人决定。录制实验也是这样。
- **计算**：数据根按期间新建；`period_runs.py` 会跳过已完成的期间。固定输入重跑得到同样的 run_id 和 result_id，见 5.5 的对照。每个 Run 绑定 Requirement closure、账本 sha256 和检查点；换代码版本不改旧 Run，旧 Run 用它自己绑定的运行时冷读。

### 5.5 收据检查与原生冷重放分开报告

- **收据哈希检查**：`historical_run_receipts.read_run_receipt` / `collect_run_receipts` 只核对 Run 清单里三个文件的哈希，不重放、不重算。
- **原生冷重放**：`historical_run.load_frozen_run` 在另一进程从数据根重建输入，校验来源证明，再重放记录。
- **本次实测**：Marriott FY2023 的 B01（23,713,000,000）、B04（3,083,000,000）、D01 在副本里出了公共行；另一进程冷读三个 Run 都是 FROZEN，run 和 result 与创建时一致；B04 在关闭推导缓存时又冷读一次，结果相同。与完整检出的对照见 `compute-side-probe/README.md`。

## 6. #54 固定实现 `2a642e56` 的历史消费者核对

在本方 `9efceced` 加 #54 的公司模块上，按 #54 的命令导出 Paramount、Salesforce 的历史公司包、装历史运行树、导入、计算，与本方原入口在同一份代码上建的 Run 逐个比对。材料与命令见 `verify-2a642e56/`。

- **阻塞 1**：历史运行树的 Requirement 编号 `issue_54_history_v1` 不合 `records.py` 的格式 `issue_<数字>_v<数字>`，每个历史指标都在写 Run 清单时被拒；期间选择、输入准备、数据根安装在此之前都通过。
- **阻塞 2**：事件指标（C01、E01–E05）在 #28 冻结的事件遍历里把数据根的已取得头文件清单与程序检出的原件清单比对，而 #54 运行树不装原件，`FileNotFoundError`。锚点要另定，需要一个实现方。
- **通过的部分**：只把编号改成合格式的探针运行树上，8 个指标（Paramount FY2024 B01、C02、D02；Salesforce FY2023 B01、B02、B12、C04、D01）的结果编号、期间选择、公共行哈希与本方原入口逐个相同；另一进程的收据哈希检查与原生冷重放都 8/8。

## 7. #54 固定实现 `e536cdca` 的历史消费者核对

第 6 节核对的是 `2a642e56`；#54 在 #47 的评论于 18:49 被编辑为 `e536cdca`，核对时没有注意到，这次在 `e536cdca` 上重跑同样的位置。材料见 `verify-e536cdca/`。

- **阻塞 1 已解决**：历史运行树编号改为 `issue_54_v3`，Run 直接建成，不再需要改编号探针。
- **阻塞 2 仍在**（该版本早于报告）：冻结的事件遍历要求数据根与程序根里旧式 `evidence/accession_materials` 目录列出的窗口内 8-K 完全相同。取数会话新取的文件不在这些目录里，所以本方数据根与检出在这里都只有同一份基线目录，比对相等；#54 运行树不装原件，目录不存在。比对的程序根一侧应换成已安装的公司来源。
- **通过的部分**：8 个指标的结果编号、期间选择、公共行哈希与本方原入口逐个相同，收据哈希检查与原生冷重放都 8/8。计算比上次快约三倍（`compute_historical` 外加了本方的 `checkpoint_replayed_once`）。

## 8. #54 固定实现 `8a521e32` 的事件接缝核对

#54 在安装出的运行树里，把冻结事件遍历与程序根旧式原件目录的比对，换成由外部信任记录认证的公司头文件清单，阻塞 2 解除。Paramount 前身 FY2024 与继任 FY2025 各六个事件指标，结果编号、期间选择、行哈希与本方入口逐个相同；另一进程的收据哈希检查与原生冷重放 12/12 通过。材料见 `verify-8a521e32/`。

## 9. #54 固定实现 `191d1487` 的缓存与准入接法核对

这一版只改公司文件：历史计算复用本方三个缓存块，公司准入进本方的重放缓存，历史运行树的派生缓存把外部信任树加进键与允许读取集合。代码审阅：每条读取路径在进缓存前都先做一次不经缓存的信任比对，检查没有被跳过；重放缓存的键不含信任树，靠的是这个调用顺序（低风险记录，不是缺陷）。端到端只跑 Paramount 前身 FY2024 的 C01：结果编号、期间选择、行哈希与本方入口相同；收据哈希检查通过；不开缓存块的原生冷重放 FROZEN，行与证据字节相同；计算 143 秒（上一版每个指标约 14 分钟）。材料见 `verify-191d1487/`。
