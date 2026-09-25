# D03 来源事实模块：限定独审发现与收窄修复

原 `6e5a85bf` 的 `regulatory_statement_facts.py` 和对应测试至本轮开始仍是原字节；`independent-review/conclusion.md` 是首次有效的**限定独审未通过**结论。审阅独立复现：政府调查短语后明确接“已完成”“未来才可能”“纯假设”或“与本公司无关”时，旧程序仍给 `SOURCE_REPORTED_FACT / CURRENT_AS_REPORTED`，并会拒绝更谨慎的模型分类。原JPM肯定总体涉入句的原文字节与别名证明仍有效，不因此升级为完整D03结果。

首轮修复将确定性来源事实规则限定为政府行动短语结束，或只接一段简单的法律事项**类型列举**。其他后置从句可能改变主体、时间、条件和行动状态，一律给 `ACTION_SCOPE_REQUIRES_INTERPRETATION`，由原语义路径处理；不按个别公司或案名特判，也不把它改成“未披露”。`463c91f`限定独审确认该同句修复，但又发现**同一可见文本块的下一句**若说“这些调查已结束”，旧相邻块检查读不到它，仍会错误证明当前事实。该原独审未通过结论在`independent-review-followup/`保留。

第二轮修复复用原有“关联结束”检查，把同块**后续句**也纳入它的语境；不改变原句定位，也不把无关联的其他争议结束或普通未来风险视为本行动结束。`verify_repair.py`以`repair-v2-boundary.json`记录同块与相邻块两种反例均转入未决，已保存JPM原肯定句的 `fact_id` 不变。原`repair-boundary.json`保留首轮修复时的历史检查，不倒填后续通过。

最终本地受影响验证：短测试8项通过（`repair-v2-directed.log`），真实保存JPM材料1项通过（`repair-v2-material.log`）。当前V15需求闭包 `sha256:7a0ea3732e9a99ec8241a573636a4af55b9613cd320718d4d0f7034407b6f952`，执行文件身份 `sha256:26096bc0f48cb562c990ccb16893088d1dc2c5ba4c3c227f2e1617ff5dab341d`；D03原请求工厂至受控传输的禁网接线6项通过（`repair-v2-wiring.log`）。SEC入口当前绑定禁网检查通过（`repair-v2-sec-check.log`），provider/SEC当前收据新增对应日志哈希后复验通过（`repair-v2-receipts.log`）。fast128个selector通过（`repair-v2-fast.json`）。当前绑定下原190成功只读重放通过，原账本143/143/49、没有新调用（`b13-190-post-binding-v2.json`）。前一轮`repair-*`结果作为当时闭包的历史记录保留；仅更新未冻结V15执行绑定及当前接线声明，不重签旧包。

这仍是局部来源事实规则修复，**第二轮新增差异待限定独审**。它不证明D03请求全文覆盖、模型输出、原生Candidate/Evidence/Run或十家公司完成；D03真实请求继续禁止，资源决定仍未作。原6e5和463c91f两份独审失败记录保留，不在文字上改判。#47/PR52未触碰。
