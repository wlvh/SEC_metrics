# 限定独立审阅结论

结论：**有限 PASS，所委托增量内未发现需修复问题。** 本结论针对下面确切提交，不授予财报内容接受、公司完整接入、全仓库/历史框架通过、CI通过、合并或生产信用。

- 基线：`6e51f416b12d2e284be1662482ca7a46a37d1e43`
- 审阅补丁与实际 HEAD：`80ca9883cd0c444fae883d5dd5e5ffbaf95e1f87`
- 目录：`/Users/lyuhongwang/.codex/worktrees/issue28-average-risk-dei/SEC_metrics`
- 审阅开始 UTC：`2026-10-09T16:39:11+00:00`
- 审阅结束 UTC：`2026-10-09T16:46:28.091610+00:00`；经过 `437.092` 秒。
- 工具用量：34 次，计数包含 14 次 functions.exec 外层调用及 20 次嵌套调用（其中 1 次 clock、19 次 exec_command）。普通消息总量：3（开始告知、进度告知、最终报告）；问题 0；未委派。

## 实际核验

1. `ordinary_projection.py:28` 的新 `_reported_average_period` 只对有数值的 A03 检查原批准 Spec 的 `source_disclosed_average_ending_at_filing_end`，并绑定来源事实摘要、年度申报窗口、实际测量窗口、原引用/SHA/accession、主体、数值/单位/语义角色及 Trace 所用唯一 observation。年度标签不能单独改写 Q4 起点；其他指标不能使用该放行。`render_ordinary_records:237` 实际调用它，后续 CSV 仍取 result 的期间；现有 `_period_label` 把 10月1日—12月31日标为 QUARTER，年度财年用于分组。

2. 这次检查不是把新 helper 当成全部保存验证。已读实际调用链 `save_calculated_case → _save_case → render_ordinary_records → read_saved_result`；原 writer 仍校验记录、Result 坐标、Spec/安装文件、实际来源证明、Result/target_period 日期、Trace 的 metric/Spec/主体/期间/scope_key。读回仍核验字节、记录、Spec、单位及保存期间。新 helper 不重新解释财报，业务来源解析的正确性仍由 case producer 的独立内容验证负责。

3. `normal_annual_input.py:130/142` 使用两个固定选项，没有接受调用方任意正则。默认 YEAR_ONLY 保留；允许较早的季度/日期后缀时，原 DEI 唯一性、上下文主体/维度、10-K/FY/非修订、财年与实际年度长度检查仍运行。`financial_relationships.py:45` 保留默认 issuer 的原 `[0-9]` 匹配；A03 两处 annual/issuer 和 A12 `_prepare`/issuer 都贯通同一个显式选项。`financial_structured.py` 的新增 keyword 仅贯通 annual 读取，未复核 A13 的旧业务含义。

4. `historical_dei.py:635` 的 10行新增/1行删除显式 annual adapter 把既有 `_frozen_annual.annual_period` 调用固定到 YEAR_QUARTER_OR_DATE，并在既有 view 登记中复用该 adapter。所委托的历史 statement 原失败类现在实际通过；小例同时检查 adapter 身份、真实合成 DEI 解析、错主体拒绝与 fiscal-label 原件字节改变拒绝。未扩展为整个历史动态 view 框架独审。

5. `EXPLICIT_CASE_METRICS={A03,A12,A13}` 与原 `SAVED_METRIC_IDS` 分开。公司入口只有选年且提供该指标自己的 `case_factories` 才派发这三项；default 和单一通用 `case_factory` 仍不给它们默认生产能力。`ordinary_current_update.run_once` 仍要求显式年和 callable，缺失时在创建 state 前拒绝；保存 reader 允许已核验的显式记录正常读出。基线与当前的 METRIC_IDS/LODGING_METRIC_IDS/SAVED_METRIC_IDS/CURRENT_METRICS 赋值 AST 完全一致。

## 实跑测试与控制

实际执行命令（`PYTHONDONTWRITEBYTECODE=1`）：

```text
/private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_dei_release_selection tests.vnext.test_financial_dei_release tests.vnext.test_reported_average_period tests.vnext.test_historical_statement_cases.HistoricalStatementScopeTest tests.vnext.test_ordinary_current_update tests.vnext.test_company_current_records
```

结果：**80 tests / failures 0 / errors 0 / skipped 0**；unittest 计时 7.354秒，命令实耗7.759秒。见 `required-tests.log`，包含原命令、逐项输出、runner汇总和UTC。

额外 **5个有限 probe 方法 / failures 0 / errors 0 / skipped 0 / 0.093秒**，见 `finite-controls.log`：

- 12种平均期间元数据反例：observation 数值/单位/指标/语义角色/公司、引用公司/SHA、fact hash、actual/filing期间、Trace输入缺失、重复Trace，全部拒绝。
- A03/A12 两个实际 public inspector 使用真实合成 DEI 解析：默认拒绝较早后缀，显式选项能走到各自返回 UNRESOLVED，调用计数仍零；没有财报测量内容可以被这些合成原件接受。
- A03/A12/A13 各检查default、通用单factory和明确 per-metric factory，共9个派发控制；只有最后一种传原factory和2021年。
- A03/A12/A13 各检查无年/无factory/仅factory，共9个 run_once 入口拒绝控制，state未创建。
- 4个原默认集合赋值与基线的 AST 比较。

这些构造控制和模拟派发只证明程序边界，不是财报内容接受。未运行公司长链、完整 source-material 套件、全CI或真实Q4原件的独立保存/读取链。

## 证据边界与完整性

审阅读取了 README、完整相关源码差异、实际保存/投影/读取调用和相应测试；也读取了适用的 architecture/capability/interact/TESTING 保存来源边界。任务禁止真实网络，因此未实时读取 Issue #28，权限以本次明确委托为准。

README 中 JPM21 A03/A12 的实际原件诊断、JPM25 Q4数值1.11和现有VaR实际披露测试日志仅作**继承证据**阅读，未独立重跑，未把 UNRESOLVED 升格为成功。`tested-tree.json` 的已列文件与当前字节相比，仅 `test_dei_release_selection.py` 不同（此次历史 adapter 增添测试）；该文件及新 adapter 已包含本次80测试。没有以旧日志覆盖新增代码。

`tree-verification.log` 独立验证15个改动的源码/测试/CI文件逐字节等于审阅SHA；实际HEAD一致。源码/tests只读，测试禁写pyc，构造状态只在自动清理的临时目录。持久新增文件仅本 independent-review 目录：本结论及4份日志。没有SEC/provider/付费/账户调用，没有修改账本、原件、peer树或Issue47状态，没有commit/push、打包或新agent。

本轮限定工作已完成；完整实际公司接入/内容验收仍由原接收执行承担，不能由这个有限 PASS 推定。

## 补充的已提交消费者证据

执行方在审阅结束前提供对象 `616fe531ab17cc979be839015d5ab751d3df4fec`。本审阅仅从本仓库 Git 对象读取 `company-summary.json` 与 `historical_average_risk_cases.py`，没有访问该记录指向的 peer 工作树、来源根、输出或 state。

已读摘要记录了实际 JPM FY2021 公司保存/重复/独立读：A03为2021-10-01—12-31、QUARTER、1.11 ratio；A12为2021-01-01—12-31、ANNUAL、55000000 USD。重复状态均为 NO_SOURCE_CONTENT_CHANGE，factory调用0，摘要登记保护文件未变且新增调用0。消费者源代码保留同一 observation/source_fact/原引用、filing_period与actual_measurement_period，使用明确DEI选项和上述保存接口。

这些是已读的已提交接入证据，不是本审阅独立重跑或内容接受。摘要明确运行基线为b0ead0e且有未提交修改；不能只凭摘要把运行时字节等同80ca988。另从对象比较了10个共享源码文件与审阅SHA，具体相等项见 `receiving-object-read.log`；该比较证明提交对象当前保存字节，不重建执行时dirty树。CI全部SUCCESS来自执行方告知，本审阅未浏览CI、不把告知作为独立CI核验。
