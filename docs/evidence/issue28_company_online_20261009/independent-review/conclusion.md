# 限定独立复核结论

结论：REQUEST_CHANGES，两个 P2 需要修复。限定 31 项测试通过，但未覆盖下面两个已复现边界；不将组件测试、保存的录制日志或本报告转换为真实 SEC 调用、业务数值接受、合并或生产权限。

- Patch / 实际 HEAD：`61adc0e7fb7e63b46d5ff84773ca58b8119f84fa`
- 比较基线：`29c9c9e2080a1de8c809660ac8fbdfc49072ef12`
- 开始 UTC：2026-10-09 02:43:33 UTC
- 完成 UTC：2026-10-09 02:52:00 UTC
- 实际工具调用：45 次，包括 17 次 functions.exec 外层和 28 次嵌套工具；无其他工具。普通消息 3 条，含最终报告；问题 0，未委派子代理。

实际审阅范围：`company_online.py`、`sec_rate.py`、`ordinary_projection.py`、`tools/vnext_company.py`、`test_company_online.py`、`run_fast_tests_v2.py`，以及本候选 README、录制脚本和现存日志；只读追踪 CallLedger、SecHttpClient、选年报/历史目录、普通来源和公司保存/读取依赖。其他补丁文件（包括 `docs/company_local_run.md`）不在本次限定范围。

## P2：申领成功后，计划写入失败会遗漏已计数的 pending 槽

位置：`scripts/vnext/company_online.py:83-86`；摘要使用处为 182-185、192-194。

`ledger.claim()` 已持久化 intent、占用一次 SEC 数量，但 `self.pending` 在 `sec-plan.json` 写入之后才设置。该写入遇到磁盘错误时，上层捕获异常并返回摘要；账本准确保持 `[0,0,1]`、停止 SEC，摘要却记录 `simulated_sec_claims=0`、`unknown_capture_ordinal=null`。同一路径在 LIVE 模式计算摘要时也会选取 `calls.sec=0` 分支，而不是标出未完成申领。账本本身没有释放数量，也不会自动重发；问题是可观察摘要丢掉账本仍未完成的动作。

`counterexamples.log` 的 `A_PENDING_AFTER_CLAIM` 直接调用 `run_online_company(calculate=False)`，仅在 `sec-plan.json` 的实际写入点注入 RuntimeError，真实 recorded ledger 验证上述差异，transport 实际为 0。这比现有测试只断言通道停止更完整。建议把 pending 标记紧邻成功 claim、移到本地计划写入之前，并在摘要中保留该 ordinal；加覆盖 acquire/run 两种摘要的回归。本复核未建立或访问 LIVE 账本。

## P2：B02 前期元数据失败会提前阻断独立的 B01 来源

位置：`scripts/vnext/company_online.py:138-144`。

默认同时选择 B01/B02。若元数据存在唯一有效的本期 10-K，却没有前期 10-K，141 行先抛 `PRIOR_ANNUAL_MISSING_OR_AMBIGUOUS`；程序尚未获取 Company Facts、本期正文及目录。于是本期 B01 本来可以准备的来源也未获取，首次空任务无法完成 B01。这与后继普通公司计算器已经具备的指标局部失败隔离冲突；已有“前期原件 404”演练是发生在本期原件已取完之后，不能覆盖此边界。

`counterexamples.log` 的 `B_PRIOR_FAILURE_BLOCKS_CURRENT` 使用同一明确合成元数据，只选择 B01 时获取 4 项来源并返回 SOURCES_READY_FOR_SELECTED_METRICS；同时选择 B01/B02 时只读取 submissions 便抛错。`B2_ACTUAL_REGISTRY_SUCCESSOR_SYNTHETIC_METADATA` 用实际 Paramount successor registry 和明确合成 metadata 复现同样控制流；不是声称真实 SEC 当前仅含这份年报。实际 B02 catalog 使用 REQUIRE_CONTINUOUS，普通计算器已有 successor 的 NOT_MEANINGFUL 路径；获取层不应强迫此类结果拥有前期来源，也不应因其局部缺口阻断 B01。

建议先完成本期的独立来源，再单独准备 B02 前期来源；前期未证明时保留具体局部限制，并让已获取完整来源的 B01 进入现有计算链。若目录/历史 shard 内容局部失败，采用同样的依赖范围处理，不改指标定义，也不伪造缺失数据。

## 非阻断观察：整体在线摘要和保存计算报告有不同语义

`company_online.py:193-196` 只改写 run_summary；`company-results.json` 和 company-state/latest-execution.json 仍为保存计算阶段的 SAVED_ONLY_NO_ONLINE_DISCOVERY、calls 0。`C_PERSISTED_REPORT_DIVERGENCE` 在真实保存/CSV 编排中、仅对计算结果使用明确替身，复现 run_summary 有 discovery 失败且 FLOW_COMPLETED_WITH_LIMITATIONS，而另外两份为 FLOW_COMPLETED。因为后者明确写明 SAVED_ONLY 且日常 reader 标 NOT_CHECKED_BY_SAVED_READER，本复核不将它作为数值误接受或单独阻断项。应在接口文档明确整体在线运行状态只能从 run_summary 读取，或给计算报告增加关联整体运行摘要，避免调用者把两个阶段当成同一报告。

## 验证与边界

实际执行原命令：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_company_online tests.vnext.test_company_current_records -v
```

`tests.log`：31 项，8.088 秒，OK，没有 skip。另做四个小型控制流反例，结果见 `counterexamples.log`；A/C 使用临时 recorded ledger，B/B2 是获取元数据的明确合成夹具。A/B/B2 不接受财报数值，C 使用计算结果替身，仅检验实际报告保存位置。socket/DNS 在 transport 反例中明确拒绝。首次把临时工作根放在证据目录触发 WORK_ROOT_OVERLAP，保留于 `counterexamples-initial.log`；随后临时工作根使用系统临时目录的 resolve 路径并自动删除，没有放宽生产路径检查。

计数与停止的已验证/检查部分：每 HTTP attempt 一 claim；max_retries=0；未知 transport outcome 和未完成 intent 仍保守计数并阻断下次 claim；原 allowance/anchor/历史 receipt 检查仍来自原 CallLedger；403/429 本地 stop 保留在来源日志并在下一 Capture 恢复；元数据显式刷新、成功原件复用、普通保存读取及旧 CLI 默认分支保留。没有发现这份 diff 释放原预算或自动重发的路径。最大数量与公司/指标范围在接入前核对。

没有网络/真实 SEC/provider 调用；没有接触 #47 的工作树、账本、快照或许可；没有重跑完整原件链、大测试或 retained-local 大套件；没有改源码、commit、push、tar 或签发权限。原日志中的大原件链只作为已保存开发证据检查，不标为本次 exact-SHA 重跑通过。受审七个文件在结束时与该 SHA 完全一致，Git 工作区仅新增本 independent-review 目录。
