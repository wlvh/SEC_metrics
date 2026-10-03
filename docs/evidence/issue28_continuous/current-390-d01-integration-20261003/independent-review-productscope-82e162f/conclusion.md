# 82e162f 新增产品范围限制的限定独审

结论：`PASS_LIMITED_NEW_PRODUCT_SCOPE_DIFF`。本次新增差异未发现需修复的 P1/P2。该结论只覆盖旧 C02/E01 Result 与已批准新产品目标的区分及其当前390读取视图；不授予新目标内容验收、真实调用、生产、Ready、合并或全390信用。同族子代理复核不冒充独立人工验收。

精确审阅提交：`82e162f818063938461c703985bbfe6b63c83c31`；父提交：`8dec94686fd4479228f7c262baa6eae782890e0b`。开头与结束均核对了工作区实际审阅文件等于该提交字节。开工已有的 `execution-state.json` 本地修改未纳入审阅，也未读取或修改。

实际覆盖：本目录 `current_view.py`、`test_current_view.py`、`README.md`、`product-scope-comparison.json` 的新增差异，以及 `known_result_defects.json` 的新增 `product_scope_acceptance_limits` 和与其有关的摘要。合同独立读取 `AGENTS.md` 的 `COLLAB-28-47-v1.1` 同文块、`catalog/ordinary_zero_ai/E01.md`、`catalog/r6/C02_board_disclosures_v1.md`。只将既有父390索引、有限delta与已绑定D01证明作为读取视图的必要输入；原94955acf限定D01独审按委托复用，未重新审原D01接线、财报标题或旧包内容。

先依据合同形成的判断：共同目标已明确为 C02 构成事实（规模、独立董事、委员会构成、成员、主席及相关独立性/资格）和 E01 经内容确认的并购公告。旧C02合同明确输出原文摘录且不推断董事会时点，旧E01是结构化旧路由计数、没有内容确认条件。这些旧结果即使标有 EXACT/PASS 或数值相同，也没有自动完成新目标验收的依据；这是一项版本范围待验收状态，不能单凭这点宣布原结果内容错误。

实证结果：

- 实际重新编译两个旧Spec，closure分别为 `sha256:fe99c55991a9f0d86cf31bcd8b009347dbe9b41ba7547a0fab1cc14ffb67cc41` 与 `sha256:7d5864cc3a591b5f0a3b903c4cadcaeb0782dcb60bfe2f75b744cef8f8364ccb`。20项限制逐项与冻结父索引的公司、指标、完整期间、Result及Spec一致；10家公司各含C02/E01两项。没有漏列、重复或额外旧身份。
- 通过父提交旧读取器与新读取器的正常入口比较，390坐标集合及分母相同；只有20个确切旧身份的行发生预期变化，其他370行逐字段相同。20项原始历史值与原实现身份完整保留，当前值为空且明确没有当前产品目标信用。
- 仍选中的已知缺陷为17坐标，原 `defects` 数组与父提交结构完全一致。12个缺陷坐标同时有产品范围限制，仍以 `WITHHELD_KNOWN_RESULT_DEFECT` 为主；另8个仅为新目标待验收，没有伪装成新确诊、披露不足或新调用结果。
- 另选Result身份的有限正例不继续按旧身份扣留，也没有获得当前产品目标信用；仍只有原有限delta范围标记。没有因为身份变化放宽新目标验收。
- `product-scope-comparison.json` 的20个身份、父索引SHA、两个Spec文件SHA和协作块SHA均复现。协作块哈希取 BEGIN 注释起点至 END 注释起点，包含 BEGIN 和末尾换行；初次采用仅内文哈希的审阅者假设已纠正，日志保留。

验证：指定短测19项通过（只作为回归）；指定正常入口成功写出 `/private/tmp/issue28-productscope-independent-82e162f.json`。自行选择15个有限反例/正例全部符合预期：错指标/Result/Spec路径/状态、期间的三个组成字段、重复/伪造/整组漏列、字符串false伪装权限、完整列表换序、选中旧身份的期间/Spec变更，以及不同Pfizer E01后继身份的范围边界。详细结果见 `short-tests.log`、`normal-view.log`、`independent-comparison-and-counterexamples.log`。

限制：没有验收20项新目标实际内容，没有重新审其旧原件/Run的业务正确性，没有扩大旧D01两份信用或宣称剩余370行本次已验收。目标提交差异与工作区检查没有显示本次修改旧Spec/Run/Result/原件、390父索引或生产矩阵。未跑长测试或全套，未spawn、commit、push、打包、发业务请求或操作#47/#54的现场。仅写本审阅目录的一个结论和日志，并按委托写出上述外部临时正常视图。

起始UTC：2026-10-03 02:01:28 UTC。
结束UTC：2026-10-03 02:07:43 UTC。
实际工具调用：18（8次外层exec + 9次exec_command + 1次clock；包含一次已纠正的审阅者哈希提取尝试）。
普通消息：1（最终报告；没有中途进度或问题）。
