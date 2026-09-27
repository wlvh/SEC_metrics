# Ford B06：保存原件的同范围权益核对

本次只读核对 #28 已认证的 Ford FY2025 年报主HTML与同申报原生XML（accession `0000037996-26-000015`，期末2025-12-31）。`probe.py`从既有普通B06输入重新准入两份原件，按当前期末、同一CIK与 `CompanyExcludingFordCreditMember` 维度遍历全部XBRL事实；`probe.json`保存原件引用、原字节SHA、各概念计数及普通B06当前状态。运行命令为 `PYTHONPATH=scripts python3 docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/probe.py > docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/probe.json`，本次完成约8秒，无网络和新增账本申领。

主HTML与XML各有同一工业维度的当前、非当前融资租赁负债事实，也有已报告债务表；**两份原件均没有在该维度下标记权益、归母权益或净资产事实**。相反，无维度的合并 `StockholdersEquity` 与 `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` 存在。这是范围区别的正反对照：不能把合并权益替代工业分母，也不能凭缺少同维度事实推算“Ford Credit权益应减多少”。当前固定实现重建工业债务报告小计21,919,000,000 USD，B06仍为`WITHHELD/null`、`B06_SOURCE_RELATIONSHIP_UNRESOLVED`。

这项核对**只覆盖已保存的FY2025主文件和同申报XML的当前期末XBRL事实**，不是对其他申报、未标记HTML全文或完整财报范围的无披露证明。即使以后找到同范围权益，当前工业债务小计也尚未被证明覆盖批准定义的全部债务，不能直接升级为比值。下一步需沿已批准来源范围找到可证明的工业归母权益及债务完整关系；若只能通过跨主体/合并减法得到数值，则需先作具体业务规则决定。此报告不是新Result/Run、独立审阅或生产信用；原账本仍143/143/52，#47未操作。

**后续可见原表核对（尚未随当前推送head归档）：**先前的“不见工业权益”只针对XBRL同维度事实；不是说HTML中没有分业务资产负债表。`visible-debt-balance-probe.py`从同一已认证FY2025主原件抽取相邻的“Company excluding Ford Credit / Ford Credit / Eliminations / Consolidated”资产和负债表、Note 18债务明细、融资租赁附注及合并权益表；`visible-debt-balance.json`保存原行、原字节SHA、来源ID和有限算术核对。2025期末工业列资产130,934百万美元、负债109,758百万美元，二者**算术残差**为21,176百万美元。它不是原件直接报告的“Ford Motor Company归母工业权益”：合并归母权益35,952百万美元、合并非控股权益28百万美元，但原表没有给出这28在工业/金融两列的归属，不能把净资产残差自动变成批准分母。

Note 18同一工业范围列当前债务5,550、长期债务16,369、账面总额21,919百万美元，并把融资租赁列入“Other debt (including finance leases)”；租赁附注单列当前136、非当前754、合计890百万美元。当前+长期及两项租赁各自对账成立，**不能再把890加到21,919上**。这比前述“报告小计”的来源关系更明确，但本次只确认已保存Note 18所报告债务集合的范围/包含关系，不为其它可能融资项目作全面无遗漏保证，也不生成B06 Result。是否把同范围资产减负债的残差用作要求“同范围归母权益”的分母，属于另一个业务口径决定；目前继续`WITHHELD/null`。第一次探针把合并表误并入工业表、第二次把Ford Credit债务同名行误并入工业行，失败日志逐份保留；最终脚本限定相邻工业资产/负债表及Note 18中Ford Credit小节前的行。无网络、无SEC/provider调用、无#47操作。
