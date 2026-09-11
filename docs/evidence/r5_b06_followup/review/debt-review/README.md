# PR42 债务来源独立增量核对

审阅者：Codex 独立模型子任务 `/root/debt_reconciliation_review`。本次亲自读取七份保存的原始 XBRL instance、有关完整附注、JPM 原始 HTML 和当前 B06 定义；逐文件 SHA 与原保存 headers 核对；按实际 context、单位、时点和实体提取 79 个事实及 14 个附注块；用 Decimal 独立重算。未执行新原生 Run 或完整候选验证，没有任何 provider/paid/SEC 请求，不构成人工批准。

`raw-fact-index.json` 保留原 XML 路径/字节哈希、精确 concept/fact ID/context/unit/decimals、附注文本哈希和表格行。原文各一份可支持核验；此目录的派生文本不是新计算数据源。

## 可以依据本轮已批准账面口径解决

### Lumen：是计量差异，仍有负权益

同一 c-8、CIK 0000018926、2025-12-31、USD：

- 到期表 `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` = 17,815m。
- `DebtInstrumentUnamortizedDiscountPremiumNet` = 223m；`DeferredFinanceCostsNet` = 151m。XML 两项均正值；同一 debt note 表格用括号明确扣减。
- `DebtAndCapitalLeaseObligations` 账面总额 = 17,441m；current 88m + noncurrent 17,353m 与其相等。
- 到期表正文明确排除折价与发行成本；因此 17,815 − 223 − 151 = 17,441 可直接对账，不能继续声称同计量总额冲突。
- 表中 finance lease and other obligations 220m 已包含在债务集合内，不再加融资租赁202m。
- 权益 −1,117m；新账面债务已核清与比值 NOT_MEANINGFUL 同时成立。

### Southwest：原比值须随新计量原则改变，不仅解除修订阻断

同一 c-4、CIK 0000092380、2025-12-31、USD：

- f-627 `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` = 4,919m，是融资表扣除折价与发行成本前的小计。
- f-629 current = 324m；f-631 `DeferredFinanceCostsGross` = 18m；f-633 noncurrent = 4,577m。
- f-591 `ScheduleOfDebtInstrumentsTextBlock` 的连续表行明确为小计4,919、Less current maturities324、Less debt discount and issuance costs18、期末非流动4,577。
- 新账面债务 = 4,919 − 18 = 324 + 4,577 = 4,901m；权益7,981m；比值4901/7981 = 0.6140834481894499436160882095
- 小计已包括finance leases78m；无另加。融资表披露 revolving facility 年末未借款。
- 别把4,919直接称为纯本金：另一个到期表 f-683 / f-690 `LongTermDebt` 报告本金4,929m。该表不能套用前表18m调整，也不能优先覆盖账面余额。

两家公司证明需要验证的是“哪张原始表、哪个时点/范围、哪个调整项符号、哪个计量端点”的关系。通用代码可验证来源绑定、签名数值关系、same-context 和账面端点闭合；不能仅凭tag名称、公司名、大小关系或两个金额恰好相减就接受。生产配置不应录入这些金额作为答案；独立内容记录应绑定确切来源和适用规则，原生 Observation 仍从 source facts 读取。

## 五家组成关系与最小剩余决定

| 公司 | 原文已经解决的关系（USD million） | 尚未裁定的最小命题 |
|---|---|---|
| Ford | 公司剔除FordCredit债务21,919 = current5,550 + noncurrent16,369；current已含独立短债1,355，Other debt已含融资租赁136+754=890。FordCredit另141,417；不能把集团/金融子额重复加。债务政策已说明par经折价、成本、hedge调整为账面。 | 工业债务已有，不是缺债务。现有原instance未找到CompanyExcludingFordCredit同范围权益；35,952是集团权益，不能代用。应取得工业分母或明确允许的统一范围；本轮不擅自改口径。 |
| Pfizer | current LT本金3,000 + OtherShortTermBorrowings157 −3调整 = short carrying3,154。long noncurrent61,641明确排除current carrying2,997；157确在原pair64,638之外，非重复。脚注称157主要为现金抵押。 | 这笔主要现金抵押的短期借款是否属于B06融资债务集合？若纳入，需明确其完整性质而不是据借款tag自动相加；若排除，保存排除规则。原pair+157会扩大目标集合，计量澄清本身不授权。 |
| JPM | 合并BS短债64,776与长期435,206分列；长期表已含under-one-year42,589、unamortized/valuation/fair-value adjustments。不得再加current42,589。短债内32,460以公允价值计入账面，长期内134,559亦如此；这是报告的账面计量，不应剥掉FVO后拼本金。 | 银行B06债务集合是否包括short borrowings，以及repo/federal funds、VIE融资负债等边界？435,206+64,776不是由现有“直接总额不加adder”规则自动授权，也不能据难度标N/A。 |
| Salesforce | notes/credit agreements融资表总carrying14,439 = 4,000current+10,439noncurrent；principal14,500不替代carrying。融资租赁535在accrued expenses/other noncurrent liabilities，原文明确不在该债务表；其余信用额度未用。 | 融资租赁535是否进入B06目标集合？已证明不包含，不能继续说关系未知；但原规则同族pair不加adder，新增可比范围需明确规则。不能将operating leases混入。 |
| Macy's | 融资表principal2,441 − debt discount/costs19 + acquired premium10 = carrying2,432；short debt为0，ABL未借款，完整债券集合有证据。finance leases13=2current+11noncurrent，列在AP/accrued及Long-term lease liabilities，未含在债券表。 | 目标债务是否加入单列融资租赁13？其中noncurrent含1m非租赁组分，需明确是否按报告finance lease liability整体纳入或排除非租赁部分。短债为0不能单独证明完整；此处已有完整融资表支持债券集合，余缺口已缩为具体租赁范围。 |

Pfizer 附注还有同concept/context的非流动债务62bn粗精度披露，与精确61.641bn共存（原XML的decimals不同），不能把该粗披露当第二个精确金额。原子数据导入应继续保留精度及来源位置，不只按concept/context去重后任取一个。

## 结论与边界

Lumen 计量冲突可解除；Southwest 在新账面原则下应以4,901m重新计算，新旧Run/比值必须分别保留。剩余五家已经可以把“需要复核”缩成以上具体组成和决策，不需AI才能读出关系，也不应在未裁定目标集合时强行求比值。

本审阅不评价尚未实现的代码是否真正完成 source→Observation→Review→Calculator 重放，也不将这些读取结论作为生产授权。新的原生结果/候选仍需要实施端验收及独立增量复核。
