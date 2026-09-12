# 普通来源后继组件

本轮把旧22项全部接到普通已保存来源（包含明确WITHHELD，不表示全部已有数值），输出现有Observation、Trace和Result记录，尚未创建后继Run或扩展12指标CLI。实际原件、来源失败和开发缺口逐项保留；当前材料不证明实时SEC最新或正式采纳。

<!-- capability-anchor: CAPABILITY.ordinary_zero_ai_native_components -->
<!-- capability-anchor: CAPABILITY.ordinary_companyfacts_native_components -->
<!-- capability-anchor: CAPABILITY.ordinary_accession_native_components -->

| 入口 | 已实现范围 | 实际来源与处理 |
|---|---|---|
| `normal_zero_ai_results.resolve_ordinary_zero_ai_metric` | B01/B03、C01/E01–E05 | 原Spec和Calculator；B03复用本次原件生成的B01收入观察。六事件共用完整8-K/8-K-A原件和中性条目事实，按原目录分别投影 |
| `normal_companyfacts_results.resolve_ordinary_companyfacts_metrics` | A05/A06/A07/A08/A10、B02/B04/B05/B07/B08/B09 | 既有目录公式；当前/上一期申报独立绑定。原HTML缺失时，经同申报目录认证的原生XBRL可以证明上一期DEI期间；不回退已失败的最后GET |
| `normal_accession_results.resolve_ordinary_accession_metrics` | A01/A02/B12 | 既有目录的概念/维度范围；新普通政策核对完整单位定义、实际主体和时点。JPM取母公司标准法，B12取无额外维度的RPO，不取收购对象单独金额 |

三个入口都只接受数据根、配置公司ID和受支持指标ID（后两个入口分别一次返回11项、3项）。没有调用者提供的答案、期间、事实或选定申报参数；验证入口从原件完整重建，不接受自洽但改过结果的JSON。数据目录可以不含Git；安装的原始获取基线、来源账本和实际body/header必须仍通过验证。代码未调用旧release准备器或读取历史矩阵答案。

首批80个B01/B03/事件坐标有50个数值、2个结构性不适用、28个WITHHELD；不是80项成功或80份正式结果。六事件的完整来源缺口会影响各自计数，不能缩小来源后报告零。C01和E03按现有政策共享Item5.02事件，不能解释成已核实CEO/CFO变更人数。B03明确为EBITDA利润率，本次Marriott由营业利润4,141百万、折旧145百万、摊销313百万和收入26,186百万复算，未借用旧答案。

11项目录指标覆盖十公司110坐标，并保留以下区别：

- 当前指标和上一期指标分别处理。JPM的历史清单范围与实际文件冲突使A05/A06/A07保留WITHHELD，A08/A10仍由本期原件计算。
- Macy’s上一期原生XBRL证明2024-02-04至2025-02-01；Salesforce证明2024-02-01至2025-01-31。当前时点指标仍是截至2026-01-31，不能统一改成全年测量。
- Southwest修订影响及Paramount主体接续还没有在这两个组件完整接线，相关适用指标保留开发原因；结构性不适用与这些缺口分开。
- Salesforce当前财年原文2026与DEI/同申报CF标签2025冲突仍未在普通输入中解决；这些组件保留原字段和真实起止日期，不能据此宣称财年选择已经正确。历史记录不改写。

D03/D04和财年对照作为另外三个来源准备组件同时交付。D03独立审阅发现的引语归属、相邻结案、机关否认/转述和私人主体反例已修复，12份原始HTML反例复验通过，真实十公司原有9条有限支持陈述未丢失；它们不是9起当前调查。D04把12份原年报/修订年报的全部可见块分为97组，保存原字符及字节身份，十公司新进程重建通过；全文语义检查尚未执行，关键词缺失、普通无保留意见和名字匹配都不证明不存在持续经营疑虑。财年组件对比来源定义、DEI与同申报CF，提供冲突证据，不自动重写已有输入。

作者报告、独立发现、修复后原反例、真实材料、测试和首次失败分别保留在`docs/evidence/issue28_continuous/successor-source-components/`。A01/A02/B12已覆盖30坐标，其中3项原件数值、27项结构性不适用；新政策使用ratio/USD和时点，保留旧目录/结果原字节，单位ID改名不改变单位意义。两公司完整图另经新进程/无Git数据根重建通过，6项默认及Python3.9测试通过。材料见`ordinary-accession-components/`。这些组件尚需进一步独立审阅、统一Run、来源更新及完整390坐标验收；费用与最终生产权限仍按总委托分别核实。
