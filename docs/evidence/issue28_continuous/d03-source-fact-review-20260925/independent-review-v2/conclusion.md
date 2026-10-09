# D03 来源事实第二轮限定独立审阅

**结论：`452c828793a89fd84ca84860b770480b768ae99e` 相对 `463c91f19b04f20597268df0c767a6c1d92bdf22` 的限定差异仍未通过。** 同块后一关联句的原阻断已修复，但新扫描把后面明确属于其他主体或未来风险的结束句也归到首句，能撤销首句本应保留的确定性当前涉入保护。此结论仅限本模块的来源事实规则，不判定 JPM 原件存在该反例，也不判定完整 D03 或整个 PR。

## 已核实的修复及绑定

- `regulatory_statement_facts.py` 第 45–46、77–82 行现在把当前块后续句传入既有的关联结束检查。原先的“两句话同块”和“结束句在相邻块”均产生 `SEMANTIC_REVIEW_REQUIRED / UNRESOLVED`，带 `LINKED_RESOLUTION_REQUIRES_INTERPRETATION`；`check_aggregate_classification` 不再错误拒绝 `HISTORICAL_STATEMENT / UNRESOLVED`。直接写明无关的私人争议结束，以及普通未来调查风险，在同块和相邻块探针中均保持 `SOURCE_REPORTED_FACT`。句子正文及原块内位置仍按原句保存。
- 已保存的 JPM 肯定样本只做小文件回归重算，仍为 `SOURCE_REPORTED_FACT`，`fact_id` 仍是 `sha256:69b4af995d78bd8353a873c568d51d690ed477b28432c09196f46fa12a9ee972`。未重跑 JPM 大材料。规定的 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_regulatory_statement_facts.RegulatoryStatementFactsTest -q` 实跑 **8 项通过**；该测试新增同块/相邻块结束及直接无关句，但没有覆盖下述跨句指代反例。
- `git diff --check` 无报错。当前实现文件 SHA-256 为 `cd1104d811cef9f7292cc6dbcda1377b4eaedf2bd17eb5a130d86ec8ec0bc8cf`、8138 字节，与 V14 baseline 的 `new_rule_files` 和 `execution_authority.files` 两处相同。禁网加载 V14 快照重算所得当前 V15 闭包为 `sha256:7a0ea3732e9a99ec8241a573636a4af55b9613cd320718d4d0f7034407b6f952`；执行文件身份重算为 `sha256:26096bc0f48cb562c990ccb16893088d1dc2c5ba4c3c227f2e1617ff5dab341d`。
- 第二轮保存的 D03 禁网接线、SEC 入口、provider/SEC 收据及 B13 190 只读复用记录使用同一闭包。它们分别报告新增调用 `[0,0,0]`；SEC 与 B13 记录的累计为 `[143,143,49]`，收据检查报告 `network=DISABLED`。我独立核对了这些记录的闭包与当前快照，并未重新执行接线、收据扫描或检查目录外账本原件；保存的 fast 记录为 128 个 selector 通过，也未重跑。

## 剩余阻断：跨句指代属于其他主体仍误撤销首句保护

独立构造的一个**同块**反例为：

> We are involved in various legal matters, including investigations by governmental authorities. In a separate matter, Acme was investigated by governmental authorities. That investigation was closed.

首句明确指向 `We` 当前涉及的政府调查；后两句明确另起 Acme 的事项。当前程序仍将首句标为 `SEMANTIC_REVIEW_REQUIRED / UNRESOLVED`，原因码为 `LINKED_RESOLUTION_REQUIRES_INTERPRETATION`；随后 `check_aggregate_classification(..., kind='HISTORICAL_STATEMENT', reported_status='UNRESOLVED')` 返回空列表，故来源事实保护不再阻止把首句归为历史/未决。另一个同块反例把后两句换成 `Our vendor may face investigations in the future. Those investigations may be resolved.`，结果相同；这不应把首句的明确当前陈述视作已经结束。探针输出见 [probes.log](probes.log)。

原因是第 77 行把**全部**后续句并入 `linked_context`，第 78–81 行逐句检查“这些／那项调查已结束”，只在**结束句本身**查 `explicit_unrelated`，没有判断中间是否换到另一主体、事项或未来假设。旧提交不读取同块后续句，因此这个同块假阴性由本差异引入。若把后两句分别作为相邻块传入 `context`，现有逻辑也出现同样误判；这是本次复用的既有检查边界，须与同块修复一并守住。直接写明 `An explicitly unrelated private dispute was resolved.` 的测试不能证明跨句指代安全。

应在给首句降级前证明结束句仍指向它的调查；至少遇到中间明确转向其他主体/事项或未来风险时，不应沿用结束句。修补后需要同块及相邻块的正反例回归，并保留当前已通过的关联结束与 JPM 肯定样本身份。这里提出的是可复现的规则边界，不要求重跑大材料或新增模型/SEC 请求。

本轮只审指定代码、测试、V14 baseline 和本 D03 第二轮材料；没有审 D03 全文覆盖、模型响应、原生 Candidate/Evidence/Run、十家公司结果、生产采纳或整个 PR。没有发模型/SEC 请求，未操作账户、生产、#47/PR52，未 commit、push 或打包。工作树既有 `execution-state.json` 修改未触碰。工具统计：17 次 `functions.exec`（内含 31 次 `exec_command`）、1 次 `apply_patch`、1 次给主任务的消息；双层计数共 **50** 次，普通消息为开工说明、主任务发现通知和最终报告共 3 条，均在指定上限内。
