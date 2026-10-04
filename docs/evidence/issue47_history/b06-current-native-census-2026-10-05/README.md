# Macy's：完整期末 USD 原生事实清单补充

从已提交原capture的primary/XML原字节各解析 **1555事实**，固定期末2025-02-01。每源336个瞬时事实中，258个为USD金额；其余78个的单位分布保留，包含无单位、shares、pure、USD/shares及来源自己的计数单位。期末context不意味着每个金额都是已确认负债，未来摊销和养老金未来付款也有这个as-of日期。

原153候选中114项在该USD金额集合，其余39项是其他单位或无单位的候选；这里不是把153与258直接相减。额外144个USD事实、92个不同concept由执行者全部读，相关38个完整context也读。当前258金额事实的HTML/XML多重集合全部相同：主体、期间、展开后的维度/member集合、单位及数值逐项一致；重复出现的事实仍按次数保留。XML解析器已有local-name大小写行为在比较中明示casefold，原QName和原文字不改。

全部258记录保留原text、完整numeric attributes（含scale/sign）、format QName、nil属性、context及规范化值。使用本方history-owned Registry4固定零支持，全部期末USD金额都可规范化，无新未知值；这不是改#28冻结解析器或获得融资含义信用。额外原生条目也含普通税务no→0的例子，不把这种零当作借款零。

额外144项分别位于已提供的正文/完整表：140个有visible block位置，131个有native cell位置，两者联合覆盖全部144。131个金额格的原text/raw text、row/column及grid SHA与原108份prepared grids逐项相同。**没有发现由于153候选清单而完全没有供应给模型的这144项金额**；并未因此修改原固定请求 `9feffb12…aee951e`，未扩充、压缩或换来源。

本补充的实际发现和边界：

- 额外清单并非只有资产：包含GeneralAccountsPayable8.53亿、OtherLiabilitiesNoncurrent9.02亿、当前负债合计45.24亿，以及customer/employee/pension/claim余额。8.53亿和9.02亿原本就在完整正文/表格中，原153只没有相应原生条目。泛称不能证明所有成分都是ordinary trade，也不能自动纳入融资债务。9.02亿的完整性质/重叠关系需继续查原件，融资租赁非当前1300万已另有来源支持，不能重复加。
- 完整养老金context表明资产分类、FV层级和plan type。Treasury/corporate debt/mortgage等标签是在养老金计划的资产测量，负300万衍生头寸也保留资产表口径，不能凭debt字样加到发行人借款。
- 期末税务资产/负债、valuation allowance、uncertain-tax-position及不同balance-location维度保留本身性质；未来无形摊销、未来benefit payments及未确认股票报酬不成为期末账面借款。ordinal1351的4700万是未来第二年SERP benefit payment，**不是**Note7已计应付利息4800万；二者日期、测量和归属不同。
- 原4800万应计利息、Property-related4.46亿、Other当前1.94亿及完整债务集合的证明问题仍保留。此前27.79亿借款+1500万融资租赁只获组件信用，不能由本次原生数据一致性自动变成完整B06。

`native-census-materials.tar.gz`保存258×2全部金额记录、完整计数/单位分布、144额外原生行和完整context、人工判断组及整体两源比较、位置对照和真实构建日志。原1555全部事实没有都保存为新金额行，258不是整份native universe，也不宣称解释了所有108表/图片/外部协议。

`inspect_current_native.py`是只读清点，禁止网络socket，不调用任何正常Run或provider；它只从已校验capture的原源读取。程序不通过concept关键词选择期末USD，仍保留候选清单成员关系用于比较，没有给任何原生金额自动指定debt角色。人工组是执行者判断，不能接入运行作为手动债务操作数。需新目录重建，原构建输出保留，不覆盖已有材料。

```bash
work/issue47-venv/bin/python \
  docs/evidence/issue47_history/b06-current-native-census-2026-10-05/inspect_current_native.py \
  --capture work/issue47-inputs/b06/capture \
  --prior-inventory work/issue47-b06-source-v4-equity/native-current-financing-facts.json \
  --out <新清点目录>
```

归档九成员全部核字节/SHA；从原capture在新目录重建的四个清点输出与解包文件逐字节相同。人工判断和位置对照单独保存，清点重建不冒充重新阅读或业务裁定，见`verification.json`。

本次新增DeepSeek/paid/SEC `[0,0,0]`，新Run/接受0。B06独立精确输入子代理权限仍待用户答复；原请求、原模型包、旧回答、Run和来源不改，完整债务总额及ratio仍null/WITHHELD。
