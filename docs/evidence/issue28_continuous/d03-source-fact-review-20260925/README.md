# D03 来源事实模块：限定独审发现与收窄修复

原 `6e5a85bf` 的 `regulatory_statement_facts.py` 和对应测试至本轮开始仍是原字节；`independent-review/conclusion.md` 是首次有效的**限定独审未通过**结论。审阅独立复现：政府调查短语后明确接“已完成”“未来才可能”“纯假设”或“与本公司无关”时，旧程序仍给 `SOURCE_REPORTED_FACT / CURRENT_AS_REPORTED`，并会拒绝更谨慎的模型分类。原JPM肯定总体涉入句的原文字节与别名证明仍有效，不因此升级为完整D03结果。

本轮将确定性来源事实规则限定为政府行动短语结束，或只接一段简单的法律事项**类型列举**。其他后置从句可能改变主体、时间、条件和行动状态，一律给 `ACTION_SCOPE_REQUIRES_INTERPRETATION`，由原语义路径处理；不按个别公司或案名特判，也不把它改成“未披露”。直接测试新增已完成/未来/假设/否定/其他主体反例，原JPM和无后置限定的肯定例保留。`verify_repair.py`从已保存JPM原事实重算，原正例 `fact_id` 完全相同，五个边界反例均不再产生确定性当前事实，见`repair-boundary.json`。

受影响验证：短测试7项通过（`repair-directed.log`），真实保存JPM材料1项通过（`repair-material.log`）。新V15需求闭包 `sha256:fb36222f3f7645b1d8ed76d9b7c83f8284646816011f6d2f6aaf3129158d373e`，当前执行文件身份 `sha256:4aa798280b8e1e431587a5cd49ed759751a1323b566c950582d4483a8bd3db3c`；D03原请求工厂至受控传输的禁网接线连同6个相关测试通过（`repair-wiring.log`）。SEC入口当前绑定禁网检查通过（`repair-sec-check.log`），provider/SEC当前收据新增对应日志哈希后再验通过。fast128个selector通过（`repair-fast.json`）。当前绑定下原190成功只读重放通过，原账本143/143/49、没有新调用（`b13-190-post-binding.json`）。历史包、旧失败与旧收据证据不改写；仅更新未冻结V15执行绑定及当前接线声明。

这仍是局部来源事实规则修复，**修后新增差异待限定独审**。它不证明D03请求全文覆盖、模型输出、原生Candidate/Evidence/Run或十家公司完成；D03真实请求继续禁止，资源决定仍未作。原6e5独审失败记录保留，不在文字上改判。#47/PR52未触碰。
