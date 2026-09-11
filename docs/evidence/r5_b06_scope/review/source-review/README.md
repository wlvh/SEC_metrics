# B06 新统一债务集合：独立来源核对

独立 Codex 模型子任务 `/root/debt_reconciliation_review`，非人工批准。亲自解析十份保存 XML；本记录对八个无待决银行/工业分母范围的坐标完成完整相关附注、报表计量和组成关系核对。Ford/JPM XML 初步材料一并保存，最终专门判断交由另一独立审阅任务。

本轮依据新委托采用：报表账面的借款、债券及融资租赁，允许明确在总额之外且不重叠的短借/融资租赁相加；排除经营租赁；报表融资租赁内合并非租赁组分不剥离。Pfizer该份157m短借虽主要为现金抵押，用户已明确纳入；不是所有现金抵押均可纳入。

| 公司 | 新集合债务（USD） | 股东权益（USD） | 独立按原件计算 | 组成结论 |
|---|---:|---:|---|---|
| Pfizer | 64,795,000,000 | 86,476,000,000 | 0.7492830380683657893519589250 | Short carrying3,154m已包含current LT2,997m和other短借157m；加明确排除current的noncurrent61,641m。不能再加current LT。 |
| Salesforce | 14,974,000,000 | 59,142,000,000 | 0.2531872442595786412363464205 | Borrowing carrying14,439m +另列finance lease535m；二者报表负债位置和完整附注证明不重叠。 |
| Macy’s | 2,445,000,000 | 4,860,000,000 | 0.5030864197530864197530864198 | 债券账面2,432m +另列finance lease13m；其中1m非租赁不剥离；短债及ABL无余额。 |
| Enphase | 1,204,377,000 | 1,087,023,000 | 1.107959077222837051285943352 | 完整notes carrying current+noncurrent；原文明示无finance leases。 |
| Southwest | 4,901,000,000 | 7,981,000,000 | 0.6140834481894499436160882095 | 新账面总额已含finance lease78m，无新增短借；原4919小计减18费用。 |
| Lumen | 17,441,000,000 | −1,117,000,000 | NOT_MEANINGFUL | 账面总额已含finance/other220m，内含finance lease202m，不能再加；负权益保留。 |
| Marriott | 16,204,000,000 | −3,771,000,000 | NOT_MEANINGFUL | 总额已含短期限但归长期的commercial paper1,177m及finance lease120m。 |
| Paramount | 13,658,000,000 | 11,693,000,000 | 1.168049260241169930727785855 | Successor carrying总额已含finance lease3m；CP/credit facility/Miramax期末均无借款。 |

以上八份均为原件读取及数学核对，不是新实现原生接受或新完整候选通过。数字只作审核结果/测试期望，生产必须重新从各自来源事实解析。完整来源SHA、相关完整附注文本SHA、exact fact id/context/单位/精度和纳入排除关系均在 `scope-relationships.json`。

## 必须保留的精度及概念边界

- Pfizer 同一context的 `LongTermDebtNoncurrent` 精确61,641m（decimals=-6）与文字62bn（decimals=-9）并存；前者处于后者的舍入范围内，不是真冲突。必须留两者和精度，只采用有明确表格身份的更精确原数；不相容区间应拒绝。
- Salesforce XML `DebtInstrumentCarryingAmount` 给14,500m，但该格在表中属于Outstanding Principal；真正carrying为 `LongTermDebt`14,439m。不能仅凭tag名称接受。
- Paramount1.32bn未摊销公允价值调整是较粗披露，不应用face14.98bn减粗调整来重造精确13,658m。并保留successor主体、期末账面与原股东权益，不换NCI-inclusive权益。
- Pfizer完整lease note只披露operating leases，原instance未找到另列finance-lease金额；不是以“本地没有某tag”伪造一个零financelease事实。现有报表已披露债务集合由两段borrowing表闭合；如未来新增financelease披露，来源身份和新判断必须重新验证。

## 执行边界

本轮亲自核对来源/headers哈希、原始XML和完整相关note、数值/精度/context/单位，Decimal重新求和及相除。未执行provider、paid或SEC请求，未修改原件/仓库，未重跑旧修订审阅、原生Run或完整发布链。当前主路径需要实现新集合下的确定性组合，再独立复核其原生记录。
