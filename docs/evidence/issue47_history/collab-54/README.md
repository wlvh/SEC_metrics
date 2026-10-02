# 与 #54 的接口（#47 历史侧）

[#54](https://github.com/wlvh/SEC_metrics/issues/54)（获取与计算分离、按公司独立运行）由新执行者集中集成；#47 保留五年历史能力与验收责任，维护历史期间、来源依赖与运行读取接口，并验证自己的消费者。本页回答 #54 第 4 节与 [#47 评论 5953701392](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5953701392) 要的四件事。接口变化以 `[shared-with-#54]` 标记回链。

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
