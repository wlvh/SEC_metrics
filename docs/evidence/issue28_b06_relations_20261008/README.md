# B06工业融资租赁的已报告包含关系

从main8588ccbbb1独立开发，不修改PR67，不增加其指标/模型/在线范围。复用原[Ford完整财报有限阅读](https://github.com/wlvh/SEC_metrics/blob/1f6272512d96e8bd0ea617bca010a4977791f80d/docs/evidence/issue28_continuous/b06-ford-full-scope-audit-20261003/conclusion.md)，本次只核必要Note18原表/脚注和实际来源准备，不重读全部财报。

已有 `prepare_special_debt_case` / `inspect_special_scope`增加显式 `reported_relations=True`，默认False保留原行为。程序复用既有原件准入、主体/期间/USD/工业维度、同一可见列及两原件精度检查。在相应当前/非当前债务段，绑定“Other debt (including finance leases)”行、所属债务附注与实际租赁事实；其他段的标签或其他附注事实不能替代。记录890m已包含，追加额0，不用表外人工数值或公司名特例。

实际Ford FY2025、0000037996-26-000015来源准备入口通过：报告债务21,919m，租赁136m/754m、共890m已在内。两项独立限制同时保留：工业归母权益未建立、完整B06债务集合未建立；B06仍WITHHELD/null。没有制造净资产残差分母、选择合并应计利息或使用未来利息标签，没有创建新Run/公司结果。新处理文件摘要进入显式来源输入用于普通排错，不作权限证明。

首次六项小测试通过，但追加的两个反例暴露：当前段标签误用于非当前段，以及要求重复披露全在一个附注导致误拒。日志保留；限定修复只绑定对应债务段，并允许已同值核对的事实在别处重复。最终8项通过0.001s，覆盖排除标签、遗漏/金额冲突、错主体/期间、附注错位及两项新反例。不扩展通用语言判断。

实际默认来源case与main8588原实现整个对象相同（hash见default-and-persistence.json）；新显式case保存/读取也相同，三次准备＋读写合计8.943s。初始显式case3.044s是修段关系前的版本，不冒称最终版本计时。保存的是2,366,738字节源case，不称轻量日常结果或完整运行。原探针两次引用不存在的事实字段在打印阶段失败，随后使用既有 `_source_value` 完成；不是原件或业务失败。

本批限来源准备与机械处理能力。普通公司入口仍未选择这一后继，原生Run/CSV完整接入及独立内容验收未完成；不得以源case保存一致或标签匹配提升完整B06信用。旧默认、旧Run/Result/原件及账本不变，新增provider/paid/SEC为0。

复现：

```bash
PYTHONPATH=scripts python -m unittest tests.vnext.test_industrial_lease_relation -v
python docs/evidence/issue28_b06_relations_20261008/verify_saved_case.py --source-root /saved/SEC_metrics
python docs/evidence/issue28_b06_relations_20261008/verify_default_and_persistence.py --source-root /saved/SEC_metrics
```

共享范围：ordinary_special_debt_scope.inspect_special_scope、prepare_special_debt_case，新选项默认False；旧返回对象通过实际原件比较完全相同，未修改任何 `_binding()`、旧Requirement、Spec或冻结快照。#47如要消费须明确选择和本方验证，不复制本方验收信用。新B06来源case未接收进当前公司候选；不合并/Ready/采纳/部署/active。


## 508c限定独审及包含行金额修复

[原独审](independent-review/conclusion.md)为NEEDS_FIX：原表结构反例把当前租赁改为1,000m、包含行仍226m，总债务5,550m，初版错误确认包含。旧结论不改，原代理25工具/3消息/7分35秒已结束，不再续发。

修复只读取对应当期工业列的包含行金额。倍率来自同列原生总债务事实，并先将其可见数与已确认原生数核对；包含行不能用附加单位后缀放大，缺倍率/错列/数值矛盾均未决。关系证据保留包含行单元格、USD金额和倍率。实际当前包含行226m、长期1,210m；原136m/754m继续通过，1,000m反例改为UNRESOLVED/追加额null。

10项小测试通过0.001s；实际默认完整case仍与main完全相同，原件正例及保存重读通过（三次准备＋读写合计9.001s），B06仍WITHHELD/null。修复后的原结构反例只是内存派生测试，无原件写回或获取信用。反例探针先因XML标签大小写筛选失败，错误保留；后改用既有metadata概念的casefold处理。这是探针设置修复，不改业务事实。

修后差异尚待限定复核，不据父方测试改写为独审通过；普通公司入口／原生Run尚未接入，不计新增完整公司结果。
