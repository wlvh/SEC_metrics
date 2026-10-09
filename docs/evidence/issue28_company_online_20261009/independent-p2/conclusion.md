# 仅 P2 增量的独立复核

结论：APPROVE_WITHIN_P2_INCREMENT。原独立复核指出的两个 P2 在本次精确提交的限定范围内已修复；没有发现新的阻断项。原 REQUEST_CHANGES、原失败和原非阻断观察保留历史含义。本结论不授予整 PR、实际财报数值、真实 SEC/provider 调用、生产、Ready 或合并信用。

- 精确 patch / 实际 HEAD：`f1c0088d3a2069ea3ef98272f22349f738e88ef0`
- 比较基线：`61adc0e7fb7e63b46d5ff84773ca58b8119f84fa`
- 开始 UTC：2026-10-09 02:57:57 UTC
- 完成 UTC：2026-10-09 03:04:27 UTC
- 实际工具调用：27 次，包含 10 次 functions.exec 外层及 17 次嵌套工具；没有其他工具。
- 普通消息：3 条，含本代理最终报告；问题 0；未委派代理。

## 复核范围与继承

仅复核 `scripts/vnext/company_online.py` 和 `tests/vnext/test_company_online.py` 相对上述基线的 P2 修复，必要时只读追踪既有选择年报、目录、历史元数据、账本申领及连续性规则。继承 `../independent-review/conclusion.md` 和 `../independent-review/counterexamples.log` 的已覆盖部分；没有重开全模块，也没有把其 31 项旧测试标为本次重跑。

两份受审源码和两份继承文件在结束时均与上述 Git HEAD 的 blob 完全相等。来源捕获的真实记录机制、既有 allowance、零自动重试、未完成申领阻断等未变部分复用原复核，不重建防伪或递归 Requirement 审阅。

## P2 一：申领后计划保存中断的 pending 与摘要

`company_online.py:83–86` 现在在成功 `ledger.claim()` 返回后立即设置 `self.pending`，随后才写 `sec-plan.json`。因此计划持久化抛异常时，已占用的 ordinal 不会从本次可观察摘要中消失。原有完成路径仍在账本终态写完、receipt 加入 captures 后清除 pending。

新增组件测试对 acquire-only 和 calculate 两分支均复现第一个计划保存中断，确认 `unknown_capture_ordinal=1`、`simulated_sec_claims=1`。本代理另在真实临时 recorded ledger 中先完成一次模拟 HTTP，再中断第二个计划保存，两分支实际落盘摘要均记录 `unknown_capture_ordinal=2`、`simulated_sec_claims=2`；账本仍为 `[0,0,2]` 且 SEC 停止，模拟 transport 仅调用 1 次。计算结果使用明确替身，仅检查编排及摘要保存，不证明业务计算。

LIVE 条件分支仍在 pending 非空时返回 `calls.sec=null`，代码检查确认不再选取零次数分支；本复核未创建、访问或执行 LIVE 账本。录制摘要的 `calls.sec=0` 仍指实际外部调用为零，不能与 simulated claims 混淆。

## P2 二：B02 前期缺口与 B01 当期来源隔离

`company_online.py:124–134` 先用原选择器证明本期年报，再获取 Company Facts、本期正文、目录和既有原生实例集合；`138–155` 单独准备连续主体 B02 所需的前期，并将该段失败具名登记到 B02 的 `metric_limitations`。缺口令来源及整体摘要保持 partial / limitations，不伪造完整前期或完整成功。继任主体沿原注册信息与既有 B02 连续性政策跳过无需比较的前期获取，不改变指标口径。

新增组件测试使用实际 Marriott / Paramount registry 及明确合成的唯一当期元数据：两者均先获取 4 项本期来源；Marriott 缺前期明确限制 B02，Paramount 继任路线不强求前期且不登记虚假的来源缺口。

本代理补查了前期同期间多份年报、历史 JSON 失败、历史 CIK 冲突、历史获取失败四种局部边界：均保留已经完成的本期来源，只限制 B02。另验证了从历史 shard 发现前期及其修订件的正向路径、本期 B01-only 不读取前期、继任主体存在历史目录也不读取前期。本期正文失败仍抛出本期失败，不能被局部捕获写成 SOURCES_READY。`run_online_company` 在 discovery 为 partial 时将整体状态设为 FLOW_COMPLETED_WITH_LIMITATIONS，调用原保存计算器的边界保留。

这证明本次获取控制流和摘要修复；没有重新运行真实原件链，也没有把仅获取来源或模拟 calculator 转为 B01/B02 数值接受。

## 实际验证

原样短测试命令：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_company_online -v
```

实际结果：8 项，1.071 秒，OK，退出 0，无 skip。`review.log` 保存完整测试输出、10 个增量边界的实际结构化结果，以及一次初始小反例脚本的失败原因。初始 SourceSpy 在目录处理时错误读取 CIK-only 夹具的 form，出现 KeyError；只修正临时夹具后重跑全部 10 例并通过，没有改产品源码或旧证据。一次只读 rg 查询使用了不存在的依赖文件名并返回 2，随后按实际依赖位置读取；未将该查询当测试结果。

额外边界使用明确合成 metadata/目录、临时 recorded ledger 和 transport / calculator 替身，并明确禁止 socket connect 与 DNS。所有临时目录由 TemporaryDirectory 清理。真实 provider/paid/SEC 调用均为 0；没有联网、访问 #47 工作树/账本/许可、重跑长原件链、改源码、改旧证据、commit、push 或 tar。

本代理仅新增本目录的 `conclusion.md` 与 `review.log`。原报告中整体在线摘要与保存计算阶段报告的不同语义仍是原非阻断观察，未被本 P2 修复升级为已解决，也未据此重开全模块。
