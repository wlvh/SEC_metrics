# 限定独立审阅：保存来源材料 CI 三分片

- 精确补丁：`1d458a4696c894ca809dbca9c53c39f8e5949fc2`，相对其父提交。
- 范围：`.github/workflows/vnext-fast.yml`、未改变的 `tools/run_fast_tests_v2.py`，以及本证据目录的分片说明与调度记录。未审整个 PR 或业务验收。
- 结论：**PASS（限定差异）**。没有发现遗漏或重复执行的 selector、matrix 与命令分片数不一致、汇总门放行失败分片、或暗改测试及限时的问题。能否消除远端取消，仍须以新 head 的三片 CI 终态判断。

实际核查：`tools/run_fast_tests_v2.py` 与父提交的字节差异为零；其 `_selected_tests()` 按位置模分片。短命令 `python3 docs/evidence/issue28_continuous/ci-source-material-three-shards-20260929/schedule.py` 通过，并用真实 CLI 的 `--list --suite source-material --shard-count 3` 分别核对三片，得到 30/29/29，合计 88 个互不重复 selector。工作流的 matrix 是 `[0,1,2]`，三片都传 `--shard-count 3`，`needs.source_material_parts.result` 仍须为 `success`。`--jobs 2`、单项 240 秒及既有特定覆盖值、35 分钟作业上限均未改动。

从成功运行 `36433946153` 的两个实际作业日志直接解析得到 41+41 个通过结果；82 个 selector 的逐项 `duration_seconds` 与 `previous-success-timings.json` **逐项完全相同**。按当前 88 项重排，三片已知耗时总和为 1668.386、1404.762、1614.901 秒，每片另有两个尚无该远端样本的 B03 selector。这些是各 selector 子进程耗时之和，**不是**两个 worker 的作业墙钟耗时，也不是新 CI 必过预测。

对 `ba7b5f88` 运行 `36466326739` 的取消作业 `109077198596`，GitHub 作业记录显示从 18:36:02 到 19:11:17 UTC，约 35 分钟；checkout 为 18:36:03–18:41:59，材料命令为 18:42:01–19:11:15，结论 `cancelled`。作业原始日志只有 `The operation was canceled.`，没有最终测试 JSON 或业务断言错误。因源码仅在所有子进程结束后打印总 JSON，不能从这份日志推断单项测试均通过；“作业碰到 35 分钟限制”有时间与配置支持，但不是已测出的每个 selector 根因。此前运行 `36454551078` 的 shard 0 完整 JSON 确实列出两项 B03 selector 各在 240 秒返回 124，与本次取消是不同故障形态。

本审阅只运行短调度/只读 CLI 核验并核读既有远端日志；未重跑任何保存来源长材料、未触发 CI、未修改测试与生产入口。唯一轻微文字精度问题：README 将成功样本 checkout 概括为“约 25 秒”，实际两作业约 30 秒和 25 秒，不影响分片结论。
