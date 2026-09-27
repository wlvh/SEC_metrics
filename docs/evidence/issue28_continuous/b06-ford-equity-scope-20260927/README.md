# Ford B06：保存原件的同范围权益核对

本次只读核对 #28 已认证的 Ford FY2025 年报主HTML与同申报原生XML（accession `0000037996-26-000015`，期末2025-12-31）。`probe.py`从既有普通B06输入重新准入两份原件，按当前期末、同一CIK与 `CompanyExcludingFordCreditMember` 维度遍历全部XBRL事实；`probe.json`保存原件引用、原字节SHA、各概念计数及普通B06当前状态。运行命令为 `PYTHONPATH=scripts python3 docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/probe.py > docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/probe.json`，本次完成约8秒，无网络和新增账本申领。

主HTML与XML各有同一工业维度的当前、非当前融资租赁负债事实，也有已报告债务表；**两份原件均没有在该维度下标记权益、归母权益或净资产事实**。相反，无维度的合并 `StockholdersEquity` 与 `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` 存在。这是范围区别的正反对照：不能把合并权益替代工业分母，也不能凭缺少同维度事实推算“Ford Credit权益应减多少”。当前固定实现重建工业债务报告小计21,919,000,000 USD，B06仍为`WITHHELD/null`、`B06_SOURCE_RELATIONSHIP_UNRESOLVED`。

这项核对**只覆盖已保存的FY2025主文件和同申报XML的当前期末XBRL事实**，不是对其他申报、未标记HTML全文或完整财报范围的无披露证明。即使以后找到同范围权益，当前工业债务小计也尚未被证明覆盖批准定义的全部债务，不能直接升级为比值。下一步需沿已批准来源范围找到可证明的工业归母权益及债务完整关系；若只能通过跨主体/合并减法得到数值，则需先作具体业务规则决定。此报告不是新Result/Run、独立审阅或生产信用；原账本仍143/143/52，#47未操作。
