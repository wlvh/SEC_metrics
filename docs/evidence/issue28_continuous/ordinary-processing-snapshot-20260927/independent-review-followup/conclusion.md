# 134dcf4f 混合刷新续跑限定独立审阅

结论：**NEEDS_FIX（两项恢复边界 P2）**。相对 `40bff4570776f04d2ee9b562d23ee33c05f8a429`，`134dcf4fc1630ef6e45fae012909eb7e6410e5e0` 修掉了前次指出的正常路径阻断：含当前处理副本 ID 的首份报告可核对 B01 本地尝试、C04 终态及剩余 URL 后续跑。已保存的录制材料测试确实断言首轮 B01/C04 均为 `CANDIDATE_READY`、第二轮取另一 URL、两项均为 `NO_SOURCE_CONTENT_CHANGE`，并在第二次捕获前拒绝被改写的 B01 尝试编号。它尚未完整证明前驱报告不能被篡改，且处理副本创建失败时不能按同一捕获身份恢复。

## 发现

**P2：把已执行普通指标改写成 `UPDATE_BLOCKED` 可绕过尝试绑定。** `scripts/vnext/ordinary_refresh_cycle.py:256-261` 对该状态只要求 `attempt_id=None`、无 `terminal`、无上次候选、`production_authorized=False`，随即跳过 `:263-286` 对 B01 配置、当前指针、真实终态和候选的核对。用有效首份报告作底稿，将 B01 的 `CANDIDATE_READY` 行换成满足上述四项的阻断行，保留真实来源副本 ID、SEC receipt、C04 行及待办 URL，`_resume_one_c04_source()` 接受被改写的报告并返回下一 URL；其余续跑代码 `:426-440` 可据此进入第二次受限捕获。新增材料测试只把成功行的 `attempt_id` 改为零，没有覆盖这种状态降级。独立短桩复现得到 `valid ACCEPTED` 与 `downgraded ACCEPTED`，没有发请求。即使下一次 Run 会重新计算 B01，续跑前驱本身已可谎报成功尝试；应使每行的实际处理状态可与持久记录绑定，不能仅凭报告自称 `UPDATE_BLOCKED` 绕过校验。

**P2：副本创建失败后的首份报告不能恢复已成功的 SEC 捕获。** 一次 SEC 捕获成功后，`current_processing_source()` 可在 `:455-469` 失败；这时报告保留 `PROCESSING_SOURCE` 错误、普通指标 `UPDATE_BLOCKED`，且 `:561-562` 不写副本 ID。若还有待办 URL，`resume_from` 会把这个新报告按“无 ID 的旧报告”处理，`_resume_one_c04_source():287-303` 强制要求旧 `SOURCE_SCOPE` 错误，因而报 `ORDINARY_REFRESH_RESUME_C04_HISTORY_CHANGED`。独立短桩复现得到该拒绝；这是代码分支验证，未独立执行磁盘故障端到端测试。应按明确的报告版本区分旧阻断报告和新报告的副本失败态，并在副本修复后重验原 SEC 捕获、C04 终态、待办 URL，再允许接续；不能以“没有副本 ID”直接推定旧报告。

## 已核对和未覆盖

- 正常路径的来源副本验证、B01 当前尝试、C04 终态、原 SEC receipt、下一 URL 及申领前账本身份均有对应检查；旧 `SOURCE_SCOPE` 报告读取分支仍在，未独立重跑真实旧混合报告。再次使用第一份报告时，账本计数/末行检查会拒绝；已保存 C04 单指标材料测试也断言重复续跑拒绝。
- 本提交的产品代码增量只在 `ordinary_refresh_cycle._resume_one_c04_source()`；共享获取/更新接口默认值未改。V14 模块字节为 SHA-256 `2976dddd44079f65cc14921ed49d3adbb1e254f3e48fd11ebd23c2a7a805cfe8`，与 manifest 相同；本审阅现场执行 `validate_execution_authority` 和 `validate_wiring_receipt` 均通过。来源材料测试已被加入 `run_fast_tests_v2.py` 的材料选择器。
- 本审阅亲自运行指定短测，11/11 通过（2.720 秒）；读取已保存的 `resume-material-first.log`（末尾旧预期失败）、`resume-material.log`（修正预期后 1/1 通过，195.651 秒）、`resume-fast.log`（132/132 PASS，118.048 秒）及 `binding-resume-after.json`。未重跑材料或快测，也未做真实 HTTP/provider、完整公司运行、390 坐标、正式采纳、#47/PR52 验证。短桩只复现前驱判定分支，不证明实际网络或真实账本终态。

本审阅仅新增本文件，未改产品代码、提交或推送。工具使用：`functions.exec` 12 次，其中 24 次本地 `exec_command`、2 次 `apply_patch`；普通消息 2 条进度更新与 1 份最终报告；耗时低于 90 分钟。新增项目调用 `provider/paid/SEC = 0/0/0`。
