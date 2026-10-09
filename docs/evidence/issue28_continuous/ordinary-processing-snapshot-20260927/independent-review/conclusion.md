# 40bff457 限定独立审阅

结论：**NEEDS_FIX（恢复路径一项 P2）**。相对父提交 `5466d45d`，当前规则私有副本的原账本身份、独立复制、默认入口和有限正向处理有相应实现与证据；但混合 C04 刷新的 `resume_from` 校验仍按补丁前“其它指标一律阻断”的结果形状检查，因而不能接续补丁自身生成的含 B01 成功候选的报告。修复和相应的实际续跑测试完成前，不应把本补丁认定为“失败后可恢复”的完整实现。

## 具体发现

**P2：新混合报告不能作为同一路线的续跑前驱。** `scripts/vnext/ordinary_refresh_cycle.py:395-405,447-464` 在 `mixed_stale` 下创建当前处理副本，并让 B01 等普通指标实际进入 `run_company`。现成的 `mixed-refresh.log` 和 `mixed-refresh-repeat.log` 分别记录 B01 `CANDIDATE_READY` 和 `NO_SOURCE_CONTENT_CHANGE`，两次整体仍为 `UPDATES_INCOMPLETE`。但同文件 `:234-245,261` 的 `_resume_one_c04_source` 仍要求前驱报告的 `acquisition_errors` 精确等于旧 `SOURCE_SCOPE` 阻断记录，并要求每个非 C04 指标为 `UPDATE_BLOCKED`（或未实现）。新报告的错误列表与 B01 状态均不符合；在一次成功 SEC 捕获后仍有待获取 URL、用户以该报告调用允许的 `resume_from` 路径时，会报 `ORDINARY_REFRESH_RESUME_C04_HISTORY_CHANGED`，无法进入下一次受限获取。这里是从代码条件和已保存的新报告形状得出的确定性结论；本审阅没有发 SEC 请求，也没有构造完整的捕获续跑实验。建议按新旧两类前驱分别验证实际 C04 尝试、其它指标尝试及来源快照身份，保留旧报告的只读兼容，并新增一次有限录制捕获后的正反续跑测试。

## 已核对的边界

- `ordinary_processing_source.py` 从原请求日志哈希、已安装来源 checkpoint、当前 requirement 闭包和基线 manifest 构造副本 ID；创建和复用均重验账本、checkpoint、当前配置/目录规则与财年政策。`continuous_sec_acquisition.py` 的新 `clone_baseline` 默认值为 `False`，旧调用保持普通独立复制；显式副本在 macOS 使用 `clonefile`，失败时回退独立写入，没有硬链接原证据。`cow-test.log` 记录私有规则篡改被拒且原规则字节不变。这些检查不能扩大为防御拥有安装代码和信任目录的操作者。
- `ordinary_update_cycle.py` 的显式 `source_identity_root` 用原来源路径保持更新配置身份，在处理前后验证私有副本与原账本匹配；默认参数缺省时保留原路径。前一成功候选仍从自身已安装的 `work/data` 重放，`source-version-rehearsal.log` 记录录制账本从版本 0 到 1 时副本 ID 改变、B01 返回 `NO_SOURCE_CONTENT_CHANGE` 且原成功尝试不变。这是录制材料，不是旧版本所有 Run 或真实新财年更新的验收。
- 已保存本机原账本探针记录 Salesforce B01 数值准备为 `41525000000`、C04 为 `0`；混合刷新记录二者候选及重复运行不增候选、总状态仍不完整，调用计数 `0/0/0`。`material-test.log` 的一项录制完整来源测试通过；最终写时复制版本的 `cow-test.log` 是来源准备和篡改边界验证，不能代称完整混合 Run 冷读。`refresh-boundary-tests.log` 以及本审阅独立执行的 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_refresh_cycle` 均为 11/11 通过，但没有覆盖上述混合续跑状态。
- V13/V14 当前执行绑定中的 `ordinary_update_cycle.py`、`ordinary_refresh_cycle.py`、`continuous_sec_acquisition.py` 和新 `ordinary_processing_source.py` 摘要与工作树对应；`binding-delta-after.json` 是本补丁最后一次增量绑定记录，较早的 `binding-after.json` 属于写时复制前的中间状态。未重跑长套件、真实 HTTP/provider、全部 390 坐标、正式生产采纳或 #47/PR52。

审阅输入仅为指定差异、相邻身份/重放实现和 `ordinary-processing-snapshot-20260927/` 已保存日志。审阅没有修改产品代码、提交、推送、外部调用或打包。工具使用：`functions.exec` 14 次（其中一次 JavaScript 语法错误，其余包含 21 次本地 `exec_command` 和 2 次 `apply_patch`）；普通消息 2 条进度更新和 1 份最终报告；耗时低于 90 分钟。当前独立测试新增项目调用数 `provider/paid/SEC = 0/0/0`。
