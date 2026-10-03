# JPMorgan Chase FY2025 D01 原件标题级独立核对

结论：在下列确切本地原件、D01合同与Result范围内，标题级内容核对通过。独立从完整Item 1A重建的序列为56条：1个Summary标题、12个风险类别标题、43个具体风险段首标题；当前Result逐条文字、来源定位、原始跨度哈希及顺序均一致。未发现应纳标题遗漏，也未发现目录、正文标签、页眉、页码或下一节混入。这一结论只覆盖标题级来源摘录。

## 对象与身份

- 委托固定开发基准：`ea6293c5081ca6fe74c936574bc9dca497a33e3c`；委托指定修复来源：`31beeab5486a30366afa395124c7ecbb492c93b8`。本核对只消费指定四个输入，没有读取修复源码或重审旧补丁；这里登记委托基准，不额外证明修复实现。
- 原件封面主体为JPMorgan Chase & Co.，CIK `0000019617`，DocumentType为10-K，DocumentFiscalYearFocus为2025，封面财年截止为December 31, 2025，AmendmentFlag为FALSE。当前计算目标/Result期间为2025-01-01至2025-12-31，主体范围为registrant。
- 来源记录accession：`0001628280-26-008131`；文档：`jpm-20251231.htm`；source role：`target_primary`；source reference：`sha256:7179ce77593c01b74f13278d25e9dab8627a864c58d35de769dc14bfdcb819ff`。原件12,927,325字节，SHA-256为`4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23`，与Run内raw asset identity一致。仅核对已提供本地字节，没有发起SEC或其他业务网络请求。
- Run：`run:ordinary-integrated:557e26f5cc3e1ffe4ee5d79947a2911de78929852384ab69b4807e831e5e6ec1`；本次材料路径attempt：`bb9e9ce65d9f4fdfa3547b885fcae875`。
- Result：`sha256:f8da54962750aa727051d66ba699bae53afbf21e2ce19a51abd023666f683f89`；trace：`sha256:a97c6822f8a1a11274031d082ccea1cedc3c31313315e7ec77de7f68dc3801c9`；review unit：`sha256:bbc745ef61a75221fc4634c9779038a33828368ff41ba20da3c69688c77a896d`；candidate：`sha256:ab739cf54345e658f62ea4b23d910542ebc6e292f9270835efd11c182e8bc04c`。
- Result字段为APPLICABLE / EXACT / PASS / PUBLISHED；manifest仍为OPEN。PUBLISHED是所给记录的字段值，不是本核对授予的正式发布或生产信用。manifest的records_file_hash为SHA-256空文件值；本核对固定实际records.jsonl字节，未据此字段宣告Run闭合，也未检查整个Run终态。

|输入|SHA-256|
|---|---|
|D01合同|`c782daf4ed1d49ef226adcf80d22dec9d72038f186931a67bc4e63638018096c`|
|records.jsonl|`d2cbe1dc874556ca6efe7fcda4c324f9cf2ab17905ba15d1b52aa91eb2a1e823`|
|manifest.json|`8264eed8983dc322893a5abdf0b712d657734ffa92e6890e9d61906edc70be4d`|

## 独立阅读方法与完整性

先在原年报定位目录中的Item 1A链接及印刷页9–31，再定位正文真实的“Item 1A. Risk Factors.”；从该段开始按原HTML的左栏、右栏、换页顺序完整阅读至People类最后一段及页31，继续读取相邻的Parts I and II页眉与Item 1B以核实终界。通用HTML解析仅用于把原件文字、字体、段落和原始字节位置列成日志；未导入仓库模块、未执行原有标题选择器，也未把已有Evidence PASS或当前Result列表作为完整性的依据。之后才将原件分类清单与当前Result、candidate、56个VERIFIED_OBSERVATION逐项比对。

阅读包络内共有668个有文字的段落、1070个非空span。整段原HTML去除标签后的文字，与日志中的完整段落文字在去掉空白后完全相同；这项辅助核对用于确认通用解析没有吞掉文字。该范围的字体权重只有400和700，没有b/strong/h1–h6等额外标题标签；80个粗体span均已分类，两个斜体段落均已阅读。正文标题清单是对这个确切披露的阅读判断，不将“全粗体段落即标题”推广为新规则。

80个粗体span分别是56个应纳标题、摘要正文中的12个分类标签、Item 1A页内11次Part I页眉，以及下一页1次Parts I and II页眉。另有页码9至31共23个，均为8pt常规字，不是标题。Item 1A自身12pt常规字的章节标记用于确定范围，不作为风险标题输出。

摘要中的“Legal and Regulatory risks, including …”等12项是一个带项目符号的完整叙述句：加粗类别词后紧接普通字体的“risks, including …”。它们是正文内标签，不是独立标题或另一个风险段首标题。相同12个类别稍后各以独立棕色粗体段落领起具体风险标题，已全部纳入；不应因摘要标签重复这些类别而重复输出。此判断来自原段落及后文层级，不能只凭关键词或粗体认定。

两个斜体段落分别是风险范围说明及“上述摘要以以下讨论为准”的说明句，既不命名风险，也不领起一个风险条目，因此不纳入标题清单。原件定义说明中提及extraordinary-events风险标题的普通字体引文，也只是正文内交叉引用；真正的对应粗体风险标题已在其正式位置纳入。

Part I位于hr的page-break-after:always之后、min-height:40.5pt的页顶容器中；它在原风险正文跨页续句之间重复，不能形成业务类别。页31后的Parts I and II同样是下一页页眉，其后立即是Item 1B. Unresolved Staff Comments. / None.及Item 1C. Cybersecurity.，均排除。目录行只有跳转链接、条目名与9–31页码，与实际正文起点相隔很远，不被借用为标题证据。

逐条比对结果：56/56原始跨度在独立识别的标题段内，实体解码和空白归一后文字完全相等，跨度SHA-256一致；56/56 observation的原件identity、source reference、accession、source role、段落/跨度/顺序等定位字段与相应candidate一致；Result的56行文本与独立序列完全相等。原始直引号和弯引号、逗号及句号均保留，例如第8条的JPMorganChase's使用原文直引号。完整逐项SHA-256保存于item-by-item.log，不以本报告的缩写文本替代。

## 原始范围

以下均为原ASCII文件的0基字节半开区间：[start,end)，end字节不包含在跨度内。

|范围|字节区间|SHA-256|
|---|---|---|
|Item 1A opening heading|`[1385578,1385767)`|`7ecb8eacf635a04f62eef5239d69effae3c23081e2000b5251c1f0c0ec290d5d`|
|Item 1A through final body paragraph|`[1385578,1690021)`|`bcf4797a733fb2b306c9117cca31fef277122d28e5d5ffe648f1acad722de154`|
|Item 1A inspection envelope up to Item 1B|`[1385578,1691240)`|`d99c078c6bd2763a88e328e7618879ce7ebaf2ed13815d259c2b81ac4f7dc171`|
|TOC Item 1A linked row|`[1257064,1258075)`|`5c6971de12559a7627b2146b7754f4775acfcb859f8cf9027dd0a90898b2aedb`|
|Summary labeled sentence example|`[1386946,1388475)`|`010706e63a129e13e444eed1725d814fa8c0aa6e414953d27dbca905549dd329`|
|Part I running header example|`[1397586,1397716)`|`59b7eb044410398d38c6908603362aaf634b84b72a0bb8cf38a99f44b721792a`|
|Next page Parts I and II running header|`[1691001,1691139)`|`adc799c66db1313f2ba454dd3b80833549435150ee777a585d9bf6592f958626`|
|Item 1B opening heading|`[1691240,1691425)`|`6914de68190dd6b42e9d5e73bab35d9a32d2bdfb69f164274ad5acb0aabe5cd4`|
|Annual report cover period including nested inline tags|`[1218247,1218529)`|`9b36a16093de816b040c330f3e2254525e205e434b29e4dabbd5b35d740089ae`|

主Item 1A内容区间截至最后一个People正文段落；较宽的检查包络继续覆盖页31页码、下一页页眉及Item 1B前的版式间隔，以证明边界，不把版式文字认成风险标题。

## 逐项清单

序号从1起，日志中的order从0起。每行均完成原件文字、来源、顺序及跨度哈希核对；原文序列如下。

|序号|层级|原文|原始字节跨度|
|---|---|---|---|
|1|摘要标题|Summary|`[1386740,1386747)`|
|2|类别标题|Legal and Regulatory|`[1400705,1400725)`|
|3|风险段首标题|JPMorganChase’s businesses are highly regulated and are significantly affected by applicable law and supervisory expectations.|`[1400876,1401008)`|
|4|风险段首标题|Differences in the supervision and regulation of financial services firms could require JPMorganChase to modify its operations and incur higher operational and compliance costs.|`[1408606,1408783)`|
|5|风险段首标题|JPMorganChase faces significant legal risks from civil and governmental proceedings, including litigation, investigations and enforcement actions.|`[1418765,1418911)`|
|6|风险段首标题|Resolving an investigation by a governmental authority could subject JPMorganChase to significant penalties and other repercussions.|`[1420393,1420525)`|
|7|风险段首标题|JPMorganChase’s compliance risk and operating costs could be higher in jurisdictions with less predictable legal, regulatory and judicial frameworks.|`[1432768,1432923)`|
|8|风险段首标题|JPMorganChase's business and operations could be negatively affected by governmental policies that discourage or penalize doing business with certain industries or that require specific business practices.|`[1438603,1438808)`|
|9|风险段首标题|Changes in the requirements for the regulatory evaluation of JPMorganChase’s resolution plan could increase its funding or operational costs or require restructuring or curtailment of its businesses.|`[1441787,1441992)`|
|10|风险段首标题|Holders of JPMorgan Chase & Co.’s debt and equity securities will absorb losses if it were to enter into a resolution.|`[1443934,1444062)`|
|11|类别标题|Political|`[1449156,1449165)`|
|12|风险段首标题|JPMorganChase’s businesses could be negatively affected by economic uncertainty resulting from political and geopolitical developments.|`[1449316,1449457)`|
|13|类别标题|Market|`[1464381,1464387)`|
|14|风险段首标题|Adverse economic and market events and conditions could negatively affect JPMorganChase’s results of operations and investment and market-making positions.|`[1464538,1464699)`|
|15|风险段首标题|JPMorganChase’s consumer businesses could be negatively affected by adverse economic conditions and adverse impacts of governmental policies.|`[1472249,1472396)`|
|16|风险段首标题|Unfavorable market and economic conditions could adversely affect JPMorganChase’s wholesale businesses.|`[1477661,1477770)`|
|17|风险段首标题|Changes in interest rates and credit spreads could adversely affect JPMorganChase’s earnings or its liquidity and capital levels.|`[1483637,1483773)`|
|18|风险段首标题|JPMorganChase’s results could be materially affected by market fluctuations and significant changes in the valuation of financial instruments.|`[1490333,1490481)`|
|19|类别标题|Credit|`[1493108,1493114)`|
|20|风险段首标题|JPMorganChase could be negatively affected by adverse changes in the financial condition of clients, counterparties, CCPs and other market participants.|`[1493265,1493417)`|
|21|风险段首标题|JPMorganChase could suffer losses if the value of collateral declines.|`[1500654,1500724)`|
|22|风险段首标题|JPMorganChase could incur significant losses arising from concentrations of credit and market risk.|`[1504193,1504292)`|
|23|类别标题|Liquidity|`[1509980,1509989)`|
|24|风险段首标题|JPMorganChase’s ability to operate its businesses could be impaired if its liquidity is constrained.|`[1510140,1510247)`|
|25|风险段首标题|JPMorgan Chase & Co. is a holding company and depends on its subsidiaries for funding to make payments on its outstanding securities.|`[1517896,1518033)`|
|26|风险段首标题|JPMorganChase’s liquidity and cost of funding could be adversely affected by downgrades in its credit ratings.|`[1521988,1522104)`|
|27|类别标题|Capital|`[1527917,1527924)`|
|28|风险段首标题|JPMorganChase’s ability to distribute capital to shareholders, and to support its business activities could be limited if it does not satisfy applicable regulatory capital requirements.|`[1528075,1528266)`|
|29|类别标题|Operational|`[1533983,1533994)`|
|30|风险段首标题|JPMorganChase’s businesses could be adversely affected by the failure or disruption of operational systems on which they depend.|`[1534145,1534279)`|
|31|风险段首标题|JPMorganChase’s interconnectedness with clients, customers and other external parties could be a source of significant operational risk.|`[1553579,1553721)`|
|32|风险段首标题|A successful cyber attack could cause significant harm to JPMorganChase and its clients and customers.|`[1556347,1556449)`|
|33|风险段首标题|JPMorganChase’s businesses could be adversely affected if it fails to identify and address operational risks associated with the introduction of or changes to products, services, delivery platforms or technologies.|`[1580434,1580654)`|
|34|风险段首标题|JPMorganChase’s business and operations rely on appropriate staffing and on the competence, trustworthiness, health and safety of employees.|`[1586699,1586845)`|
|35|风险段首标题|JPMorganChase faces substantial legal and operational risks related to the processing and safeguarding of personal information.|`[1591763,1591890)`|
|36|风险段首标题|JPMorganChase’s operations, results and reputation could be harmed by occurrences of extraordinary events beyond its control.|`[1596616,1596747)`|
|37|风险段首标题|Any failure to maintain adequate data management processes could adversely affect JPMorganChase’s ability to effectively manage its businesses, comply with applicable law or make informed business decisions.|`[1607866,1608079)`|
|38|风险段首标题|Enhanced regulatory and other standards for the oversight of JPMorganChase’s vendors and other service providers could result in higher costs and other potential exposures.|`[1615605,1615783)`|
|39|风险段首标题|JPMorganChase could incur losses arising from any significant inadequacy or lapse in its risk management framework and control environment.|`[1618486,1618625)`|
|40|风险段首标题|JPMorganChase could recognize unexpected losses, its capital levels could be reduced and it could face greater regulatory scrutiny if its models, estimations or judgments, including those used in its financial statements, are inadequate or incorrect.|`[1622364,1622614)`|
|41|风险段首标题|A significant inadequacy in disclosure or financial reporting controls could negatively affect JPMorganChase’s business, operations and reputation.|`[1630993,1631146)`|
|42|类别标题|Strategic|`[1633880,1633889)`|
|43|风险段首标题|JPMorganChase’s results or competitive standing could suffer if its management fails to develop and execute effective business strategies and to anticipate changes affecting those strategies.|`[1634040,1634237)`|
|44|风险段首标题|Competition in the financial services industry could lead to negative effects on JPMorganChase’s results of operations.|`[1644600,1644725)`|
|45|风险段首标题|JPMorganChase’s operations, results, and competitive standing could be adversely affected by the development of advanced technologies such as AI.|`[1650766,1650917)`|
|46|风险段首标题|The effects of climate change could adversely affect JPMorganChase’s business and operations, both directly and as a result of impacts on its clients and customers.|`[1657466,1657636)`|
|47|类别标题|Conduct|`[1659126,1659133)`|
|48|风险段首标题|Conduct failure by JPMorganChase employees could trigger litigation and regulatory actions and harm JPMorganChase’s reputation.|`[1659284,1659417)`|
|49|类别标题|Reputation|`[1660789,1660799)`|
|50|风险段首标题|Damage to JPMorganChase’s reputation could negatively affect its business, results and prospects.|`[1660950,1661053)`|
|51|风险段首标题|Failure to effectively manage potential conflicts of interest or to satisfy fiduciary obligations could result in litigation and enforcement actions and cause reputational harm.|`[1666376,1666553)`|
|52|类别标题|Country|`[1670067,1670074)`|
|53|风险段首标题|An outbreak or escalation of hostilities between countries or within a country or region could have a material adverse effect on the global economy and on JPMorganChase’s businesses within the affected region or globally.|`[1670225,1670453)`|
|54|风险段首标题|JPMorganChase’s business and operations in certain countries could be adversely affected by local economic, political, regulatory and social factors.|`[1677938,1678093)`|
|55|类别标题|People|`[1687433,1687439)`|
|56|风险段首标题|Various factors could impact JPMorganChase’s workforce.|`[1687590,1687651)`|

## 限定范围与工作记录

覆盖全部指定原件Item 1A的标题/强调段首层级、56条Result及其所给定位。没有未完成的本次标题级核对项；没有开展每句风险发生事实审定、年报所有章节、其他公司/期间/新输入、修复实现或全生产更新链的审查。此结论不能替代DeepSeek真实验收、正式Review授权、Run终态、全公司验收、生产采纳或自动更新能力证明。无需新增内容补丁，也未提出修改业务口径。

只写本目录中的conclusion.md及日志；没有修改原Run、Result、原件或代码，没有测试、长链、commit、push、spawn、业务网络、账户操作，或#47/#54分支/工作树操作。

原件解析辅助脚本第一次因HTMLParser内部已有offset属性发生命名冲突，未产出审查材料；更名后正常读取。该失败不涉及业务程序或原件异常。初次全records输出及一次阅读输出被工具截断，随后使用针对身份的摘录及补充连续段落读取，完成缺失段落覆盖，未以截断输出作为完整阅读证明。

工具计数按保守口径共24次：12次functions.exec及内部12次exec_command，包含1次失败；若只按实际执行工具计数为12次。普通消息共3条：开始说明、1次进度、最终报告；没有问题或额外消息。首次工具完成时间为2026-10-03T08:33:00Z，本报告写入时累计耗时约8.9分钟，最后一次输出复核后以operation-summary.log登记实测总耗时。上限80次工具、90分钟、3条普通消息均未超过；普通消息恰好为3条。

日志：original-blocks.log（完整逐段原文及字体/原始位置）、original-spans.log（所有文字span）、scope.log（原件及包络身份）、item-by-item.log（56项跨度/段落哈希及分类）、exclusions.log（12标签及12页眉排除清单）、result-bindings.log、observation-locators.log、raw-boundaries.log（原始边界片段及哈希）、operation-summary.log（工具次数、耗时及最终输入不变检查）。

最终输出复核：四个指定输入SHA-256均与首次读取一致；实测总耗时约9.5分钟，24次工具调用（12次编排、12次执行）及3条普通消息。
