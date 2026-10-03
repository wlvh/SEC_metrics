# 7bb17621 B03 合同摊销限定独立审阅

受审提交：`7bb17621c45545449f9dce390a41f39ec4bd0208`，仅限本证据目录及 B03 合同摊销新增差异。结论：**NEEDS_FIX（P2，来源概念身份校验）**。已保存的 Marriott FY2025 原件本身支持把 1.35 亿美元合同取得成本摊销视为收入减项；但新增的所选折旧／无形资产摊销原文核对，能被错误的命名空间冒充。这个反例尚未出现在已认证的 Marriott 原件中，不能据此把已执行的私有候选说成实际错值。

## 需修复的问题

`scripts/vnext/b03_contract_amortization_scope.py:33-49` 的 `_selected_original_facts()` 只比较原生事实的文本名称 `qualified_name`、期间、主体、单位和数值，没有像同文件 `:195-200` 核对该名称在原文中绑定的真实概念 URI。函数返回的 `selected_original_facts` 因而可能宣称“所选 Company Facts 分量已在原文核实”，实际原文该事实属于非 US-GAAP 命名空间。

最小隔离反例：在真实主 HTML 的当前折旧事实（ordinal 973）起始标签局部加入 `xmlns:us-gaap="https://example.invalid/not-us-gaap"`，保持 `name="us-gaap:Depreciation"`、145,000,000 数值、其他事实及表格不变，并为隔离案例更新来源证明哈希。`_ReportedFactMetadata` 正确识别 ordinal 973 为 `('https://example.invalid/not-us-gaap', 'Depreciation')`，但 `assess_current_b03_scope()` 仍返回 `COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED`、`blocked=False`，且将 973 列为已核实折旧事实。原认证 HTML 的 ordinal 925/973 则都绑定 `http://fasb.org/us-gaap/2025`。这证明的是新核对器的潜在误接受，不是原 SEC 来源已经被篡改；实际入口还须通过原来源获取与哈希认证。

最小修复是对两项所选原文事实逐项核对 `_ReportedFactMetadata.facts[ordinal]['concept']` 的官方 FASB URI 和对应本地名称，并增加上述局部命名空间变更的拒绝例。保留现有原件正例及旧 V13 默认行为；修补后只复验受影响的 B03 路径、绑定与私有候选，不重跑无关长链。

## 已核实且可保留的范围

- 我独立读取已保存、哈希为 `c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547` 的 Marriott FY2025 主 HTML，并运行指定短测，3 项通过。原件中合并行 `5,438−135=5,303` 百万美元，四个分部行 `3,004−83=2,921`、`640−19=621`、`261−1=260`、`376−6=370`。该 135 百万美元及分部展示属于 `Contract investment amortization` 的收入减项；代码没有把分部数另加到合并额。原件折旧 145 和无形资产摊销 313 百万美元，真实 URI、期间、主体及单位相符。
- 原件另外说明一类合同**履约**成本摊销列于 `Owned, leased, and other expense`，但这句话没有年度金额，也没有证明其含于 313 百万美元。这与用户决定不加回的 135 百万美元合同**取得**成本收入减项不同。本次只能按现行 B03 Spec 与用户选择的 458 百万美元两分量范围解释；不能推断“所有摊销费用都已包括”或把私有候选说成正式 EBITDA 采纳。
- 本提交的 V13 manifest、`normal_run_v3.py` 和旧默认绑定未改。V14 仅更新此执行模块的字节记录；我独立调用 V14 执行权限、语义绑定和接线收据校验，均通过，闭包为 `sha256:f0c25fbfcb8558ec4f0667906b6148f66b9a9421e771a85fccb857e590a6fa51`。
- 我核对执行方保存的禁网私有正常更新与异进程冷读脚本、JSON 和日志：两者记录同一 Result ID 与值 `0.1756281982738868097456656229`，新 Run ID 与旧 390 索引不同，当前选择依据为 `NATIVE_PUBLISHED_RESULT`，未增加真实请求、未改正式 active。我没有亲自重跑该完整私有更新、异进程冷读或 142 项 fast；它们仍是执行方证据，不能升级为我独立复现或正式采纳。

命令、原始输出摘要和隔离反例见 `review.log`。没有触碰 #47/PR52、发真实模型／SEC 请求、修改业务代码、提交或推送。
