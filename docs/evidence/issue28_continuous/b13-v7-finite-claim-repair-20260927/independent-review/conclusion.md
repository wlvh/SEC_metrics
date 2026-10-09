# B13 V7 有限回修的定向独立审阅

**对象：**`9d04d654af7649aa0ab90719d6c8f2ca7a94efaa`，父提交 `227182efe31b7ce6364c866753ae1332afb41ea2`。只审本补丁的 `capacity_two_stage.py`、定向测试、V14 字节绑定及 `b13-v7-finite-claim-repair-20260927/` 证据。承接前次 `b13-claim-context-v7-20260927/independent-review/conclusion.md` 的三个已知语义反例及暂停结论；未重审未变代码或历史业务结果。

**结论：V7 语义候选仍为 `NEEDS_FIX`；暂停门和当前绑定为 `PASS_WITH_BOUNDS`。** 已知反例在完整 `validate_interpretation()` 响应入口得到具体未决，有限正例也通过；但以下三个新组合/表述反例仍有错误拒绝或仅靠统一暂停掩盖错分类。它们没有取得原生 Evidence、Result 或 Run 信用，因为 V7 暂停仍有效。

## P2：两个 `and` 使单谓语部分被切成三个断言

完整合成原文：`Our contract manufacturers have production capacity and manufacturing capacity for current demand, and plan to add more production capacity next year.` 前半的两个产能名词共用 `have`，后半的 `plan` 是另一声明。合理的两个 finding 分别覆盖“当前产能”和“扩产计划”。现行 `_claim_segments()` 却切成 `(0,51)`、`(56,97)`、`(103,150)` 三段，其中中段 `manufacturing capacity for current demand` 没有自己的谓语；提交上述两个完整声明范围，在响应级抛出 `B13_CLAIM_NOT_COMPLETE_SEGMENT_OR_CONTEXT`。原因是 [capacity_two_stage.py](/Users/lyuhongwang/Developer/SEC_metrics/scripts/vnext/capacity_two_stage.py:644) 对第一个 `and` 检查整个右侧余句，误借用了第二个 `and` 后的 `plan`。单独的“双名词单谓语”和“双声明并列”测试虽分别通过，却没有覆盖其自然组合。应以相邻声明判断分割；不能证明时留下具体未决，避免让正确的两项判断无合法范围。

## P2：句尾明确条件未进入条件矛盾检查

完整合成原文：`Our contract manufacturers could provide production capacity for anticipated demand if demand rises.` 将其错误标为 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`，完整响应的 `unresolved` **只有** `B13_CLAIM_CONTEXT_VALIDATION_SUSPENDED`。`if demand rises` 明确限制了能力声明，[capacity_two_stage.py](/Users/lyuhongwang/Developer/SEC_metrics/scripts/vnext/capacity_two_stage.py:769) 却只识别句首 `If`，而 `could` 又被排除在“无条件当前”检查之外。已知句首 `If ... could` 现可留下 `B13_CLAIM_CONDITIONAL_MARKED_CURRENT`；同一条件放在句尾则漏检。这是离线语义诊断的错误接受风险，不是现时原生发布已错误接受。应在断言范围内核对明确的后置条件，并用完整响应正反例验证。

## P2：同属目标主体的两个词面标记导致清楚代词误拦

完整合成原文：`Our contract manufacturers, which we retained, operate plants; they now have production capacity for current demand.` 第二分句正确标为 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`，完整响应却额外留下 `B13_CLAIM_ANTECEDENT_AMBIGUOUS:B0`。这里 `they` 对应前面的复数 `contract manufacturers`；`we` 是关系从句中的申报主体，不能成为第三人称 `they` 的先行词。代码在 [capacity_two_stage.py](/Users/lyuhongwang/Developer/SEC_metrics/scripts/vnext/capacity_two_stage.py:748) 以不同表面词形计数，未检查词形所指的主体和基本代词关系。此前“本公司合同制造商；一个供应商；they”的真实歧义现已留下具体未决且不再强选最近的供应商；这条清楚先行词却被同一规则误拦。应保留真实歧义的未决，同时避免把同一主体的不同说法直接算作竞争先行词。

## 已核实的修复和边界

- 指定短测 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_capacity_reference_contract`：**32/32 通过**。新增测试走完整 `validate_interpretation()`，确认原审阅的混合主体、`and` 双声明、`can` 错标历史、`have` 错标条件、句首 `If ... could` 错标当前各得到具体代码；对应合法双声明、单谓语双名词、当前 `can` 和条件 `If ... could` 仅保留统一暂停。上述三个新反例由同一完整入口另行合成探测，不涉及真实模型或 SEC 请求。
- `verify_legacy_requests.py` 的固定样例证明 V5/V6 请求字节与 ID、V5 检查结果相同；`verify_v7_request_identity.py` 证明本补丁前后固定 V7 请求字节相同。默认 `interpretation_request()` 仍不启用 V7。`git diff --check` 对指定差异通过。这些是固定样例兼容，不是所有旧输入的穷举。
- `validate_interpretation()` 仍向 V7 结果加入 `B13_CLAIM_CONTEXT_VALIDATION_SUSPENDED`；录制解释、直接原生接受、登记接受和回读路由仍在读取扫描或构造结果前拒绝 V7（现有定向测试及未改的入口守卫）。上述漏检只说明具体语义诊断不足，不能据此说当前已产生原生信用。
- `capacity_two_stage.py` 当前 SHA-256 为 `c2974473471858628ee3614e8366f1401ad4fc63a8af1b4b6ab7ea1b5bd7275b`，同时匹配 V14 `new_rule_files` 与 `execution_authority.files`。指定 `verify_current.py` 在当前代码根成功：V14 closure `sha256:d5655149260a8a4dfc81372fe484f2c2c8a4d959c06d81eabf732e762d418ab9`，execution authority `sha256:4c88d8ef65b0b29c69e70c83ee6a604e18f99a050bf906a71dbf4b05b49d0a6b`，provider/SEC/普通刷新收据分别核对 95/50/50 项证据哈希。这证明本次新代码字节及当前接线收据相符，不证明语义正确、真实调用许可或完整原生链。

本次没有真实 provider/SEC 请求、commit、push、账本或生产操作，也未触碰 #47/PR52。进入审阅前工作树已有 `execution-state.json` 改动，本审阅未修改。完整保存与冷读、190 混合公司覆盖、真实模型表现和十公司 B13 结果均不在本次核验内；V7 应继续停用，按以上有限反例修复后再审新增差异。
