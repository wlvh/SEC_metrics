指定增量限定独审结论：PASS（仅两行括号限定修复）；继承旧 P2 在本次指定范围内已修复，无新增发现。

精确对象：base `7a2ffdd20b95888dbf0b518e6b3096f2dc67b056` → patch `e98a26c1828e3a794e2a931c5541e2c0d6ae79b9`。开始及结束检查的 HEAD 均为 patch，开始工作树干净。仅审 `scripts/vnext/selected_reported_revenue_v2.py` 第59、74行的 operating revenue/expense 原始标签检查及 `tests/vnext/test_selected_reported_revenue_v2.py` 新 `test_operating_label_parenthetical_scope_cannot_be_discarded` 方法。源码实际只有两行改变；测试新增12行。读取并继承旧 `independent-review/conclusion.md` 与 `counterexamples-and-compatibility.log`，没有重做旧完整模块独审。

**发现与修复判断。** 旧 P2 是原标签清理函数会删掉单词型括号，使 `(domestic)`、`(subtotal)` 等范围限定消失，再授予完整公司总额信用。两处新检查只统一大小写与空白，不删除括号文本；收入和费用各自保留原文限定进行精确匹配，没有改写共用 `_label_key` 或添加公司特例。新回归方法为三个继承反例传入同步变更的原生 XML，并要求 `complete_scope_proven=False`；其变更确实命中构造原件的可见标签。

本次额外小样例逐例运行指定 base 原字节与 patch。旧 P2 的收入 `(domestic)`、收入 `(subtotal)`、费用 `(domestic)` 三例均从 base `REPORTED_CONSOLIDATED_TOTAL / True` 改为 patch `NO_REPORTED_TOTAL_PROVEN / False`；额外费用 `(subtotal)` 同样修复。四例都确认变更目标在原件只出现一次、变更后原件字节不同。它们没有获得候选信用或数值，也没有将限定解释为全公司范围。

**本次执行证据。** 定向命令 `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_selected_reported_revenue_v2.ReportedOperatingRevenueTest` 实际执行：3 tests，0 failures/errors/skips，exit 0；runner 0.229秒，subprocess 约0.554秒。三个方法覆盖完整 operating 正例、组件/单位/主体/费用概念负例及新三种括号限定。完整输出保存在同目录 `review.log`。

另执行8个有限 base/patch 控制：普通 operating 正例、大小写/空白变体、四种括号反例、普通 V2 默认正例及显式单收入行正例。两个 operating 正例都保留原生已报告金额 `58496000000`，XML=`MATCH`，完整返回字典（含 scope_id）与 base 完全相等；这证明没有为了堵住限定而拒绝普通合法总额。普通 V2 与显式单收入行同样完整返回字典完全相等。`selected_revenue_scope_v1.py` 的 base、patch、工作树字节完全相同，SHA256=`4fe90d3d291c5bdf8bf225027b0c9a0c17a4d0854533dd35aaa6ab9ed6122bfc`；基线 V2 在内存执行指定 base 字节并使用该未变共用实现。patch 源码 SHA256=`aa72d649d2261593c55c135a82514213fa6eb3df955e64c520e795a4ab1e1e74`。旧默认未改的结论限定于这些样例及未变字节，不外推到所有历史输出。

**边界。** 以上正例是带原生数据及 XML 的小构造原件，属于本次现场执行；历史 Southwest FY2025 真实正例仅继承旧独审记录，本次没有重新执行公司链或大原件，没有把读旧日志写作本次真实重验。未知括号包括尚未证明的脚注也不会进入新增 operating 准入；此次没有添加脚注剥离规则。未重跑全 CI、完整公司或39/390指标；未新审其余模块、默认分支的历史标签策略或生产消费者安装。此 PASS 不授生产、业务全验收、合并、正式采纳、active 或真实调用权限。

未开发或修改源码/测试/旧证据，未 commit/push/spawn/network/真实调用/访问#47工作区/归档打包；新增输出只有本目录的一份 conclusion.md 与一份 review.log。初期一次只读 rg 查询包含不存在的测试路径，产生路径警告；没有执行该路径、重试或扩大测试范围，随后上述命令与8个控制均成功。

**执行计数。** UTC 开始 2026-10-10T07:39:06+00:00，工作完成 2026-10-10T07:41:51.578109+00:00，耗时 165.578秒；工具节点10（5 wrapper + 5 nested，含本次写报告/核对调用），普通消息2（初始进度1 + final1，问题0）。上限20节点/10分钟/普通消息2条。provider/paid/SEC=0/0/0。
