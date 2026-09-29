# 45bcce3 限定独立审阅

受审差异：`186a0c3a66b3ff7fd68ff12c223d1d1f79d447a6` → `45bcce3d99083736277728223c48b43e98205733`。结论：**PASS_WITH_BOUNDS**。在本次指定范围内未发现需要回修的错误接受；这项修补只撤回 Marriott FY2025 B03 的当前信用，尚未给出新的正确 B03 数值或改变指标定义。

## 已核实

- 独立重读 #28 已保存的 Marriott 主 HTML 和 XBRL XML，两个文件 SHA-256 与 `audit.json` 所列原请求文件一致。FY2025 同主体、同期间原生事实为折旧 145、无形资产摊销 313、合同投资摊销 135 百万美元；原文把最后一项另列为收入减项，并说明资本化合同取得成本的摊销列在该行。现金流量表的 599 百万美元行还包括“其他”，减去上述三项仍有 6 百万美元。因此 135 是必须核对的来源关系，599 不能直接替换成纯折旧摊销，更不能自动把 135 加回旧 B03。
- 新函数只对已发表、由 `Depreciation + AmortizationOfIntangibleAssets` 两项组成的 B03 检查原 HTML 中同主体、同期间、USD 的正数 `CapitalizedContractCostAmortization`。它核对原文件哈希、原生事实顺序和单位，然后返回 `COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED`；返回记录明确 `amount_added_or_result_recomputed: false`。新代码未改 Calculator、MetricSpec、历史 Result 或原 390 索引。
- 新检查接在 B03 私有正常更新的输入检查、安装后检查及旧成功候选复验处；私有完整版本准备的 B03 `PUBLISHED` 选择也调用它。执行材料显示 Marriott 同次 B01 为 `CANDIDATE_READY`，B03 为 `EXECUTION_FAILED`，其 `successful_attempt` 为空；另一进程回读仍看见原 B03 `PUBLISHED` Result，但当前范围检查继续拒绝。该旧 Result 的磁盘存在不等于当前成功信用。
- 我亲自重跑指定短测：`PYTHONPATH=scripts /private/tmp/issue28_py314_venv/bin/python -m unittest -q tests.vnext.test_b03_contract_amortization_scope`，2 项通过。测试覆盖 Marriott 拒绝、来源哈希及期间篡改、Pfizer/Southwest 既有合法正例，以及 Salesforce/Ford 既有拒绝的结果一致性。执行材料另记录 Pfizer 私有正常入口 `CANDIDATE_READY`；我只核对了该脚本与日志，没有重跑这个长材料。
- 我独立调用只读 V14 Requirement、执行字节、语义绑定和接线验证器，均通过。新增模块及三份改动执行文件的哈希与 V14 manifest 一致；三份接线收据绑定同一执行哈希 `sha256:843b9b150d7461cf38aab93077f496c6c035d958132aaa2c050d90a0924004b6`。原 `b03_depreciation_scope.py`、共享 `ordinary_update_cycle.py`、`normal_run_v3.py` 和 V13 manifest 与父提交逐字节一致。私有发布实现清单也纳入新模块。

## 证据边界

这是一项基于已保存 Marriott 来源的有限护栏。实现只发现主 HTML 内该 US-GAAP 概念的正数事实；它没有证明其他标签、负号表达或仅在独立 XML 出现的同类披露均能被发现，也没有证明 135 应计入或排除 B03。若改变 B03 的业务含义，仍需后继 Spec、算式、公开行和正常更新验收。

我没有重跑执行者的私有更新、异进程冷读、142 项 fast 或完整私有发布；其状态仅由提交的脚本、JSON 和日志支持。旧安装包在新 V14 闭包下的历史重放被拒，执行材料对此没有冒称通过。没有真实 provider/SEC 请求、正式采纳、active 切换或完整 39/390 验收。本地 fast 日志为 142/142，但它仍只是执行者的本地记录，不是本次独立复跑或该补丁远端 CI 终态。

审阅工具量和实际命令见 `review.log`。
