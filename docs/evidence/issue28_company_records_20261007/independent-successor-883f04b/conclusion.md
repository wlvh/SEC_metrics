# 883f04b 期间冲突修复增量复核

结论：**PASS_LIMITED**。原 c5487b7 审阅发现的 P2 在本次限定范围内已解决；原 NEEDS_FIX 报告保留原义，未修改。本结论不升级为完整 B03、整家公司或业务正式接受。

范围：883f04b2cd18619fdca7be9e1b320a6596dc1fa6 相对 c5487b73961b12fb336f7e59d59e6164ce32eb65 的 ordinary_income_input.py、normal_zero_ai_results.py、ordinary_saved_result.py、test_successor_income_projection.py。执行 HEAD=d3ae1738b10db14124a4774ddbdc24f5a51f888f；四文件字节与 883f04b 一致。

## 已核验的修复行为

事实所在单元格通过已有 inline/table 索引定位；日期范围与年份只从覆盖该列的表头取得。原生期间和可见期间不同即 CONFLICT，多种互相冲突的本列表头也不成为 MATCH；本列缺范围/年份保持 UNRESOLVED，不借相邻列补证。

真实 Paramount 的 7 日/8 日矛盾在输入准备阶段变成具名 WITHHELD：ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT。错误 details 经 selection.income_period 到 input-assessments 保存；原生日期、可见日期、原始表头文字、表格/网格/行列、年份表头及 SourceReference 均保留。既有 depreciation_scope assessment 通过合并保留，optional selection 为空时使用空 mapping。没有把任一日期改成另一个，也没有由 filing 年份推成已接受的实际期间。

我独立读取两份已有 B01/B03 修后保存结果，且把准备器设为抛错，均通过；确认 WITHHELD/null、同一具名原因、native 2025-08-08..12-31、visible 2025-08-07..12-31，以及正文 own-column/year 证据。CSV 为 WITHHELD/TARGET_PERIOD、空数值；日期是目标年度容器 2025-01-01..12-31，未把 7 日或 8 日标成已接受的测量起日。原父方 CLI 和其 dirty-tree program 归因仍是父方执行；这次实际完成的是独立 disk read，不是我重跑整家公司。

ordinary_projection、Calculator 及 B01/B03 年度 Spec 相对本次基线无差异；旧 [300,400] 年度守卫保留。没有年化或接受短期年度数值。

## 实际执行

指定短测 **4 tests / 15.901s / OK，无 skip**：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B -m unittest tests.vnext.test_successor_income_projection.VisibleIncomePeriodTest tests.vnext.test_successor_income_projection.SuccessorIncomeProjectionTest.test_actual_original_header_context_conflict_is_named_withheld -q
```

其中实际原件冲突测试未 mock 日期判断；类准备中的一致-header projection 控制明确是构造控制，不把 Paramount 原件说成一致。

另实际执行 8 种小输入：本列冲突、一致短期、邻列不能证明本列、本列缺范围但邻列存在范围、邻列年份隔离、跨自然年短期、本列缺年份、本列多种日期范围，预期状态均得到验证；两份真实保存结果的独立读亦通过。跨自然年例只证明该小表的日期构造，未授予新的任意财年来源能力。

首次“多种本列范围”探针的 replace 字串没有命中，属于无效前置，未据此授该边界信用；修正后先断言源字节确有变化，再确认两套本列日期及两份 header proof 均被实际读到，结果 CONFLICT。两次输出都保存在 review.log，没有把最初无效探针当覆盖。

## 边界及累计额度

仅复核此 P2 的增量修复，复用既有原件冲突调查和年度守卫证据；未重读全部旧原件、未重跑默认投影或完整 B03/公司/继承链、未执行新请求或模型调用。没有 spawn、commit/push、#47 工作树/PR52 操作；只写本目录 conclusion.md 与 review.log。有限语法不等于任意自然语言日期范围支持；未识别的范围继续保留未决。

本次 **15 次保守工具调用**（外层 functions.exec 6，子工具 9），累计 **66 次**（外层 28，exec_command 28、write_stdin 7、web 1、apply_patch 2），包括报告写入后的核验。普通消息本次 1、累计 **2**，均为最终报告；无问题/过程消息。没有超过累计 80 工具/90 分钟上限或单检查 120 秒；本轮无需额外必检工作。

