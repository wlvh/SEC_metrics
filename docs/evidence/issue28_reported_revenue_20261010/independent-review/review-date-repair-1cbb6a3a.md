# 日期回修限定复核

结论：**REQUEST_CHANGES**。原两项直接 P2 的原始触发条件已修复，但回修开放完整日期表头后，引入同一当前列的较早完整日期冲突被略过这一直接回归。范围只涉及日期回修和当前列期末关系；未扩建一般时期或财报语义。

本次 SHA：`1cbb6a3af69cac66dcfe7ab8bd40550079b905ee`；差异基线：`331bffbb9baef1601b2b915f8b1518bb60b2a385`。三份目标文件的 HEAD blob/工作树字节一致。原 `review-reportedtotal-331bffb.md` 的 REQUEST_CHANGES 和原日志保留，未覆盖。

## 原两项 P2 的回修结果

`column_end.isoformat()` 使正确的 `December 31, 2025` 完整日期正向通过，错误的 `December 30, 2025` 仍拒绝。公用 `Year Ended December 30,` 月日描述与 native `2025-12-31` 冲突已拒绝。原含 December 31、但 native 结束于 February 3 的 53-week 矛盾 fixture 已改为拒绝反例；无矛盾的 year-only 正例保留。指定两个测试模块共 **30 项通过，0 failure/error/skip，0.249 秒**。

## [P2] 开放完整日期后，较早的同列日期可被较晚 year-only 表头盖掉

位置：`scripts/vnext/selected_revenue_scope_v1.py:122` 与 `scripts/vnext/selected_reported_revenue_v2.py:65–73`。

有限构造只把现有 `originals()` 第一表头行的空白金额列替换为 `December 30, 2025`，其下一表头行仍为 `2025`：

```text
Year Ended December 31,           | December 30, 2025
(MILLIONS, EXCEPT PER SHARE DATA) | 2025
... total revenues               | existing native fact
```

事实、金额、公司和 native 期间均保持原样，期末仍为 `2025-12-31`。错误完整日期位于当前金额列。

`_column_period` 只返回最后一行命中的年度列，因此早一行的完整日期被丢弃，`column_end=None`；新增循环只找 `years ended` 月日句，不检查该独立完整日期。与此同时 V2 的 `_statement_scope` 现在允许所有 `_DATE` 表头。这三个行为合起来，使这个矛盾输入返回 `REPORTED_CONSOLIDATED_TOTAL`、`complete_scope_proven=True`。

相同输入在原 331 字节上重放，会以 `SELECTED_REVENUE_STATEMENT_LOCAL_SCOPE_UNRESOLVED` 拒绝；在回修 1cbb 字节上则接受。故该发现是日期回修直接带来的错误接受，不是本轮扩大业务范围。应在 V2 开放完整日期的同时，核对当前金额列所覆盖的全部相关完整日期；不能让较晚 year-only 表头解除已出现的日期矛盾。只需这个有限正反例，不需要通用时期平台。

## 实际原件和兼容性

固定 Macy 原件 SHA256、直接报告总额 `23866000000` USD、native period `2023-01-29` 到 `2024-02-03`、主体、单位、total_cell、year_headers 和邻接标题表证据保持。driver 重读約 1.12 秒，新增 `end_headers=[]`，纯 source scope 仍没有公司/Calculator/Run 信用。

重新执行 driver 只在内存中将唯一父 receipt 写入 sink 改为 `/dev/null`；实现/测试/driver 未改。本轮父 receipt SHA256 前后同为 `dc69efdbf53587e016c7e517f8d80488526af9a9a0652a0fe4ced73d7b0bafa1`。实际 source scope 的关键字段另与 **git 中原 331 的 actual-source-final.json** 比较相等，未将新增 scope_id 当作原值。旧 V1 默认正例和无完整利润表反例与原 base 结果完全相等；已审 peer 财政标签依赖仍逐字节相同，只核接缝，不重审该修补。

追加日志：`review-date-repair-1cbb6a3a-tests.log`、`review-date-repair-1cbb6a3a-probes-actual.log`、`review-date-repair-1cbb6a3a-binding.log`。仅这些日志及本结论写入原 independent-review 目录，未写 #47 原件/状态、覆盖原独审或父 receipt、修改代码/测试、commit/push/spawn、访问网络或真实调用。

## 起止与累计资源核对

上一轮没有读取时钟，因此其精确开工/最后消息时刻 **UNKNOWN**，不能拿文件时间冒充完整回合边界。可核实的原轮工具产出窗口为：第一测试日志创建 `2026-10-10T08:43:53+08:00`，最后结论创建 `2026-10-10T08:46:05+08:00`。原轮实际开始早于或等于前者，最终消息晚于或等于后者；这是明确的观测边界，未补造时间。

本轮第一工具取时为 `2026-10-10T00:49:56Z`（`08:49:56+08:00`）；本轮最后工具结论写入取时为 2026-10-10T08:52:04+08:00。等待父代理的间隔没有重置原资源。

| 统计口径 | 原轮 | 本轮 | 累计 |
| --- | ---: | ---: | ---: |
| 模型可见工具调用 | 8（7 exec、1 send_message） | 4（4 exec） | 12 |
| exec 内实际工具方法 | 15 exec_command | 5 exec_command、1 curr_time | 21 |
| 将 wrapper 与内部方法都计入的保守合计 | 23 | 10 | 33 |
| 普通消息（按父代理指定口径） | 2（开工 commentary、原 final） | 1（本轮 final） | 3 |

原轮另有一次向父代理的发现传递 `collaboration.send_message`，已计入工具调用，不另当普通采样消息。计数来自本代理可见完整工具序列，包含失败/探针；未重置，未超过 80 次硬上限。本轮最后普通消息即最终报告，不继续追加工具或消息。
