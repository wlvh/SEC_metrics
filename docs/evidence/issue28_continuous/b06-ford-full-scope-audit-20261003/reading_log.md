# Ford FY2025 B06 原件阅读与出处日志

- 开始 UTC：2026-10-03T01:07:33.644357+00:00。
- 以下独立原文判断先于读取已有 probe、visible-debt-balance、审计 README 和程序实现；登记 UTC：2026-10-03T01:13:20.131145+00:00。
- 固定代码提交：`1f6272512d96e8bd0ea617bca010a4977791f80d`。起始 HEAD 相同；原有 `execution-state.json` 工作区修改未操作。
- 原 HTML SHA256：`3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`，5,281,502 字节。
- 原 XML SHA256：`35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe`，5,591,122 字节。
- 阅读方式：标准库 HTMLParser 提取可见正文、逐表逐段读取；不是浏览器渲染检查。`ix:header`/隐藏事实资源不作为可见正文。XML 全文件结构解析，事实筛选仅用于原文判断后的金额/主体佐证，不能代替财务范围阅读。
- 覆盖：财务报表正文打印页111–114；附注目录115、附注1–25全文116–175；审计报告108–110；Schedule II 176。MD&A全文读取的选定页为43–46、62–72、77–84；另读Item7A全文94–97（包括Item8财报位置说明）。
- 未全文覆盖：10-K其余页（封面、目录、Business、Risk Factors、Legal Proceedings、市场/治理/展品/签名等）；MD&A47–61、73–76、85–93。全篇索引/命中定位不计入全文阅读。本次未核对外部引入文件、未取新来源、未读Ford Credit单独申报、未做审计级尽调。
- 输出截断处理：首次111–125批次中部被截断，115–121已单独完整重读；169–179输出缺失174页开头，174已完整重读；46–49初次截断47–48，47–48已完整重读。没有将被截断部分计作已读。

## 对原文先形成的判断

1. 在已完整读取的财报、全部附注和上述MD&A财务范围说明中，没有定位到Ford FY2025同`Company excluding Ford Credit`工业范围、归属于Ford股东的直接期末权益。合并资产负债表112、权益变动表114给的是合并归母权益35,952百万美元，含非控制权益的总权益35,980另列；不能配工业债务。补充资产负债表82给工业资产与负债，表止于总负债，没有权益行；不推算资产减负债残差。Ford Credit leverage页70给14.8十亿美元的子公司股东权益，不能用合并减该数制造工业分母。ROIC页72/78把合并权益与不含FordCredit债务组合，属于公司自行定义的另一指标，不能改变B06范围。
2. Note18页156明确工业债务账面数21,919百万美元，来自当期5550、非流动16369两列。页154融资租赁136/754均直接列在工业当期/长期债务，页156脚注(a)再确认；890已经包含，不可追加。
3. 页156有已报告的短借款、普通债券、可转债、UKEF及其他债务(包括融资租赁)和折溢价/发行费。页157债券本金17,059包含页158可转债2,300，不能重复加；合同到期付款、未来利息、公允价值不替代期末账面数。MD&A页62的不含融资租赁债务21.0十亿美元不能冒充完整21,919。
4. Note15页145另外报告合并应计利息1,453百万美元，位于Other liabilities and deferred revenue，而非Note18债务行。未找到其工业范围和借款/债券/融资租赁对应分拆。不能因不在Debt标签内而自动排除，也不能把全合并数加给工业数；这是一项需保留的范围/应计组成缺口，21,919只获得已报告债务余额包含关系信用。
5. Note2页118的SCF148为Payables，原文说明供应商自主转让、不变付款条款/金额且无Ford担保；按已批准普通贸易应付分类处理，不扩建隐性债务重分类。Note17的经营租赁2402单列；融资租赁含通常合并计量的非租赁服务，不拆掉。Note23/24分别说明已合并证券化与未合并BOSK；后者2026拟承接贷款不提前放入2025工业借款。担保最大风险与已确认担保负债不是借款本金。
6. 以上仍不授B06数值成功信用。未找到直接工业权益是有明确阅读边界的结论，不是依赖标签缺失宣称所有可能来源无披露。

## 附注逐组阅读摘要

| 附注 | 打印页 | 与本次范围相关的读后结果 |
|---|---|---|
| 1–2 | 116–122 | 合并主体含子公司/合并VIE；FordCredit往来、SCF应付分类、成本/公允价值说明；没有工业权益直接数。 |
| 3–5 | 123–126 | 新会计准则、按工业/金融收入拆分、递延收入、租赁收入与利息收入；收入/资产不是借款负债。 |
| 6–8 | 127–132 | 股份激励、税项、资本股与EPS；权益/稀释份额没有形成工业归母权益。 |
| 9 | 133–134 | 工业/金融现金和证券拆分；企业债券投资在资产侧，不计债务；不以现金净额代债务。 |
| 10 | 135–141 | FordCredit应收及租赁应收、信用损失；融资租赁应收是资产；证券化继续合并，非第二份债务。 |
| 11–14 | 142–145 | 存货、出租资产、固定资产、权益法投资和往来；投资净资产不是Ford工业归母权益。 |
| 15 | 145 | 经营租赁、应计利息、雇员及递延收入等其他负债；应计利息1453需单独保留范围缺口。 |
| 16 | 146–153 | 养老金/OPEB计量、计划资产和回购协议；不能把养老金计划资产组合中的债券/回购负数计作Ford借款。 |
| 17 | 153–155 | 经营/融资租赁分开；融资租赁136+754直接归入工业债务；未来未开始租赁和现金流不是当期负债。 |
| 18 | 155–160 | 债务定义和账面计量；工业分项/账面总额与合同到期表；未使用信用额度不等于借款；FordCredit资产支持债务独立。 |
| 19 | 161–163 | 衍生工具和债务套保调整；债务账面套保调整已在FordCredit债务中，工具名义金额不计债务。 |
| 20–22 | 164–166 | 离职/退出准备、持售负债、AOCI；不把全部其他负债或权益组成粗略纳入工业债务/分母。 |
| 23–24 | 167–170 | 合并证券化和未合并BOSK、2026拟承接义务、金融担保、诉讼/保修；按2025已报告分类和主体处理。 |
| 25 | 171–175 | 分部定义、内部交易、共同资产归属、分部资产/业绩及消除；没有直接工业归母权益行。 |

## 可复核逐页定位

下列均为实际完整读取的页；字节范围采用原HTML的0起点、左闭右开。分段以原HTML的page-break-after HR为界；打印页不等于HTML页序号。可运行 `python3 docs/evidence/issue28_continuous/b06-ford-full-scope-audit-20261003/locate_source.py --pages 157:159` 复核租赁/债务关键页。每页哈希是该原始字节段的SHA256，不是新来源身份。

| HTML页 | 打印页 | 原始字节范围 | 页段SHA256 | 页标题 |
|---|---|---|---|---|
| 46 | 43 | [1128914,1136850) | `107e8d708f5126f820ec67d4cd1399e3637337ff73a9726a878cb72115609349` | ITEM 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations. / Key Trends an |
| 47 | 44 | [1136887,1145034) | `119f1a2fc5aac576794922e2b46e98ac0ae18d956cc03ed421cb520f6fe04fab` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Th |
| 48 | 45 | [1145071,1153537) | `7face10ff1ee8073406a3c32f8a01db9a842808283e574eb8150204f4a935dd1` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Pr |
| 49 | 46 | [1153574,1162360) | `e946571aff215567d7230913ae5c9685ca393bd3b39c00288e610b3ad810a2a4` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Tr |
| 65 | 62 | [1505073,1522462) | `61c7506e599bf261a8eb27e670728d7c5bb0dbcfd6661e26a453c6b523f561cb` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / LI |
| 66 | 63 | [1522499,1532208) | `6d83fcbeab7f46a9edf110b708c434c8c008f6a2b51f7a0576f51384a03a6525` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Ma |
| 67 | 64 | [1532245,1539442) | `04106e8a9ac73e0501e3d43f631161a117320bae207dcfce1fc3734ff0a3464b` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Ch |
| 68 | 65 | [1539479,1580146) | `a6765e66c727454bbfbdd05876ad36c976838e5f59a5c94038e3b0ef715c8f98` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Un |
| 69 | 66 | [1580183,1588812) | `f582509dfb8b306127a1db0d756868a2840b2d1b4681a40144ef00c501f7af04` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Th |
| 70 | 67 | [1588849,1611338) | `09b44330528ebae167c4c1301ddbddb97406a3631b7b9fca01d9938204a2862f` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Fo |
| 71 | 68 | [1611375,1650609) | `04a099a840a6e77937d8f9167431a94185ad86109fece77a3f466d168348555e` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Pu |
| 72 | 69 | [1650646,1670615) | `e29fda28b35abd80abee6f0b607814e3acacc7fc7b09dbd9c6c31daac6920f9b` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Ba |
| 73 | 70 | [1670652,1679828) | `af1e5b2c8ed97391781ab893c50c5dfa79dcd0fabd520da0da4da0d1cf84f455` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Le |
| 74 | 71 | [1679865,1693836) | `af92ccaa2eed3b0165038416f2106ca8066a90a7ee8b13ffa88359b84ec0db59` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / To |
| 75 | 72 | [1693873,1729827) | `981ee4557069aabe15ed85a83e63d48be477505f990241cabc7304ac6bde9691` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Re |
| 80 | 77 | [1773558,1783800) | `e96382e24e244f701efaeee0774f3e8eecc55cc44ed0be865b752457264cd224` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / NO |
| 81 | 78 | [1783837,1787017) | `b73957abc8fca73a35d4ad6e39549aeab74251158f4ca7a1fe8b6c8deb146235` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / •A |
| 82 | 79 | [1787054,1835303) | `baa7b0f319c3f5180080d9e04875c5f64337ec4d412b278f88f0230384bf1cc2` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / NO |
| 83 | 80 | [1835340,1878176) | `4f1bbb48665de1d8a80cb76e25068bc591998b2dea242eee9ad1c3f2358d71f7` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Ef |
| 84 | 81 | [1878213,1899926) | `2e30eb3dfa0b4dd79a89fb2d7fd1428f4a36827d37ae988f2ad7c0d3fd404ec0` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / 20 |
| 85 | 82 | [1899963,1960504) | `1625eded41d4c5aa5e1e033a70b40321a18b158904a83dad196edc23f3649396` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Se |
| 86 | 83 | [1960541,2046788) | `c921a5547cba17f45697854478d2b9f258c6367c7b35a8ea5066365fd8c5b801` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Se |
| 87 | 84 | [2046825,2056522) | `34a4d9744fadecf79f1385d5c13f21dd3f3b10138906d61e55060aa1230d2bb5` | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations (Continued) / Se |
| 97 | 94 | [2147148,2154656) | `1dbbbc2973df4aed486f614de69afde4324777b230c47028f3d69cf078244969` | ITEM 7A. Quantitative and Qualitative Disclosures About Market Risk / OVERVIEW |
| 98 | 95 | [2154693,2161531) | `77a294f9cf58467772aa40fd698704aa3e7328c755f9c2283bd0e6833866a194` | Item 7A. Quantitative and Qualitative Disclosures About Market Risk (Continued) / The net fair value of foreig |
| 99 | 96 | [2161568,2173121) | `6b5c87d13da4f9afa1505faada4bf62f2815f4d163874e9f886933d66397c7ef` | Item 7A. Quantitative and Qualitative Disclosures About Market Risk (Continued) / FORD CREDIT MARKET RISK |
| 100 | 97 | [2173158,2179803) | `b640f725147e894e1d18b3e36b0310ef7532bc0efd8228db3cfc8077bfe64379` | Item 7A. Quantitative and Qualitative Disclosures About Market Risk (Continued) / Foreign Currency Risk. Ford  |
| 111 | 108 | [2404156,2412301) | `a63b97bf3eb49ae72a94ded180d96890f87d504e4b9061fb2cd8fb056dff6d65` | Report of Independent Registered Public Accounting Firm / To the Board of Directors and Stockholders of Ford M |
| 112 | 109 | [2412338,2419923) | `bb84186552767589c59f0228471d58346a55370c42aefff71ba51247b6206c98` | detection of unauthorized acquisition, use, or disposition of the company’s assets that could have a material  |
| 113 | 110 | [2419960,2427583) | `cfba7dc1e03b6f9b9b26b5026fa91a10a429e40411239712ef06eb85f9d88c20` | December 31, 2025, of which the United States comprises a significant portion. Management accrues the estimate |
| 114 | 111 | [2427620,2500434) | `689b9164f142f69a1437790127d15253f95a80004283e47fd0ea1097a8777762` | CONSOLIDATED INCOME STATEMENTS / CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME |
| 115 | 112 | [2500471,2572191) | `a4c3506d68b3f89dd2ef9794e5ce0e7720684cfeb5f3dcdbfe6190d8ac502fca` | CONSOLIDATED BALANCE SHEETS |
| 116 | 113 | [2572228,2662171) | `228f4a01cb567e0ab6a3e9dcf0a85e2461930031c10a9ac0d033898a92cb0a69` | CONSOLIDATED STATEMENTS OF CASH FLOWS |
| 117 | 114 | [2662208,2781499) | `c056220dc5395ffc58577c993f3fd69a07dcc40363c1efa62c80010501567c71` | CONSOLIDATED STATEMENTS OF EQUITY |
| 118 | 115 | [2781536,2806886) | `d095695d716331b9853b252420622ce9c8fb6d28489a68a4d1e5669b68f54526` | FORD MOTOR COMPANY AND SUBSIDIARIES / NOTES TO THE FINANCIAL STATEMENTS |
| 119 | 116 | [2806923,2823467) | `ab3338647f42c11e4a8dee74d76eebfdc623db332b9b11319759b2d88a3b0525` | NOTE 1. PRESENTATION / NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES |
| 120 | 117 | [2823504,2835950) | `69ad576ebc5822b5974c897cb975527746fb3c25fea6a63b1cc182c193c665dd` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 121 | 118 | [2835987,2856203) | `a10d01a87fffa791434f7b427617b781fd683966fd550f4471b146ba8e79c9d3` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 122 | 119 | [2856240,2866761) | `1309b9ff45d37ec021398b5c9ecea57ababab9c84a5b4499f66fb39f9eea915a` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 123 | 120 | [2866798,2874603) | `1608526a8375f1644c8fd4b14274923974e9923786dfbfb59eadec714e87c4e2` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 124 | 121 | [2874640,2885226) | `f4798711b44f1bed315988e6dee42f3743d1e88e2271d89877c278202affbc7b` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 125 | 122 | [2885263,2899754) | `62586ed05f0b96c2853fa01250b153411a2c435b3f78acd7739a972e66e7346b` | NOTE 2. SUMMARY OF SIGNIFICANT ACCOUNTING POLICIES (Continued) |
| 126 | 123 | [2899791,2904422) | `bf1e16c46cede85ac4994736cad089c1901b61637a26ec3b4b505b4d7d5e493d` | NOTE 3. NEW ACCOUNTING STANDARDS |
| 127 | 124 | [2904459,2967781) | `75ee21532d59b18d9c71e4329c1311e8c0e5dd1c069a9f16f4273709db095d38` | NOTE 4. REVENUE |
| 128 | 125 | [2967818,2980773) | `fe7650248756e536e72f8a47d6d7c899e2e5f6e15ab7498eddb026c9f58d3a91` | NOTE 4. REVENUE (Continued) |
| 129 | 126 | [2980810,3007972) | `23c071387bb534bb1e58716b16fe8b21e10bb2b13852d7852fbd1bd15b27ed25` | NOTE 4. REVENUE (Continued) / NOTE 5. OTHER INCOME/(LOSS) |
| 130 | 127 | [3008009,3038534) | `6ab63f0689f675dc6e86c0eeccaff46dcab5a115c06bb04bcd381317aa32a74d` | NOTE 6. SHARE-BASED COMPENSATION |
| 131 | 128 | [3038571,3057294) | `9ba52a99875f0f327ae98896e0212150cd5fe56f205844e5f7e868074edc1f06` | NOTE 6. SHARE-BASED COMPENSATION (Continued) / NOTE 7. INCOME TAXES |
| 132 | 129 | [3057331,3109939) | `5f0f75dc3e051fc95f635db11a6afed0dd9ca4198054dfe03ae21314a4361547` | NOTE 7. INCOME TAXES (Continued) |
| 133 | 130 | [3109976,3155815) | `9a07ef9318dc9a57fb7775a9fb95ddd93a393cbf57de71d122a55bf4c505ae03` | NOTE 7. INCOME TAXES (Continued) |
| 134 | 131 | [3155852,3200836) | `462524e71e3f93452b9ce5536992b935456cd3ae43d04583ace9f4a357a77560` | NOTE 7. INCOME TAXES (Continued) |
| 135 | 132 | [3200873,3220958) | `266e13c6fd12dedf42eaeccd2b7585b60665db9de67e0f7b0fedd1dd597bbedb` | NOTE 7. INCOME TAXES (Continued) / NOTE 8. CAPITAL STOCK AND EARNINGS/(LOSS) PER SHARE |
| 136 | 133 | [3220995,3310735) | `4de203af6b344049b3cc0c2c980d1816a6e3fe8a24c5c3f774b97e75d2b07e3d` | NOTE 9. CASH, CASH EQUIVALENTS, AND MARKETABLE SECURITIES |
| 137 | 134 | [3310772,3402152) | `36818e09b14f569fd9c6f976d95d4c47b6a546f22a7cc5fa15f25d90edf0a6e4` | NOTE 9. CASH, CASH EQUIVALENTS, AND MARKETABLE SECURITIES (Continued) |
| 138 | 135 | [3402189,3411293) | `bce788b4e04ab796c5996125d55d8523afebd037d07484beacfbcde49055ccfe` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES |
| 139 | 136 | [3411330,3453713) | `07010c61084239b51461426896700a80832f15f43f3ee052f9bd6342cc4defb1` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 140 | 137 | [3453750,3474376) | `a6566f721f9bb2d33a1f76dd3d9612ab85cef9474570946ba8d11c6a3cbd49ad` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 141 | 138 | [3474413,3560413) | `e94c0f4bd1810f8126e7b0c85c8739f62d0a3fb8ea186f51a777279580ff2f5e` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 142 | 139 | [3560450,3666337) | `4fa5625231ffab5691c6b7dbf4f992a66a4fcd26cab6ba67df17637365fac830` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 143 | 140 | [3666374,3674998) | `7f694c65e9013d137acfcd19d99cabbc9dea74e005f7aec773a9d1e832adcef3` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 144 | 141 | [3675035,3712046) | `c7f0a6f04c30d8950b5f8cba1f143bb10099dac97edfc2fde9d0b2547633c7b9` | NOTE 10. FORD CREDIT FINANCE RECEIVABLES AND ALLOWANCE FOR CREDIT LOSSES (Continued) |
| 145 | 142 | [3712083,3748587) | `41fcb575d7dba9793e728be6fa1c770bbaeebd41108960ea22d53ce3f0941535` | NOTE 11. INVENTORIES / NOTE 12. NET INVESTMENT IN OPERATING LEASES |
| 146 | 143 | [3748624,3786288) | `717f994a003f73925ffc62a7d78859ad88c61b885f9a2b1a8e3b0fce8df312de` | NOTE 13. NET PROPERTY |
| 147 | 144 | [3786325,3838848) | `683b0c2f80b20fe639ea55a993f7b88a7d4bcc4b75e200452afec437ac117ebb` | NOTE 14. EQUITY IN NET ASSETS OF AFFILIATED COMPANIES |
| 148 | 145 | [3838885,3883606) | `f909155adcc13c62e1341c00a315c0f9ad9e87cbe026d6961c39a1a6af6b3e36` | NOTE 14. EQUITY IN NET ASSETS OF AFFILIATED COMPANIES (Continued) / NOTE 15. OTHER LIABILITIES AND DEFERRED REVENUE |
| 149 | 146 | [3883643,3893675) | `f7d86dc3680d6c23d9d42b7e8f18fdce861df7be0119b566e3db3c3120595961` | NOTE 16. RETIREMENT BENEFITS |
| 150 | 147 | [3893712,3987712) | `f069c963d24475a4676029be64436b7743192c0ad8c63e03c399898749e0c469` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 151 | 148 | [3987749,4131776) | `a7900c0de2cef564892bb389e024a4577877da34c57cb3c6e051b00f76db94c7` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 152 | 149 | [4131813,4153754) | `aeeb236f5c0cfc2e0423cdf72948bbdd30e2070bae5a761116cb28a6111b76ab` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 153 | 150 | [4153791,4161055) | `b783a368883d6b375e1eef71efd41f4ba48f0eb19babd6916b7cecd85fbbe63f` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 154 | 151 | [4161092,4277098) | `50a26308a0c98682abb60667d949551fcde44e9f33398d95bd280c33b5fcd04e` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 155 | 152 | [4277135,4394356) | `3e7859d2a2e574241e01646e1b98db35ff13e61d6583ea39d00ad4d714a6dbef` | NOTE 16. RETIREMENT BENEFITS (Continued) |
| 156 | 153 | [4394393,4427478) | `ecd03a7f81ee2ed762034f298c7ee170ee486b0d1a1b210669432b40762032e8` | NOTE 16. RETIREMENT BENEFITS (Continued) / NOTE 17. LEASE COMMITMENTS |
| 157 | 154 | [4427515,4465867) | `bdfe89a8bc9e12c715a9ffd29ef12d1cd98c350a37fceea503780b2b64cc09f3` | NOTE 17. LEASE COMMITMENTS (Continued) |
| 158 | 155 | [4465904,4509956) | `ec072054a7981d047aece5b627449f4f291fe860f9a3ca10fcf6a6f8a1c84df8` | NOTE 17. LEASE COMMITMENTS (Continued) / NOTE 18. DEBT AND COMMITMENTS |
| 159 | 156 | [4509993,4577962) | `05c36168e23e960ca4f71e7ee4adb667baa8995c8d0dc995954f206c4e76a53e` | NOTE 18. DEBT AND COMMITMENTS (Continued) |
| 160 | 157 | [4577999,4677579) | `360f1151645dbdafefc44e253a1b8857b05693199613816a2a5a8ccb6258412e` | NOTE 18. DEBT AND COMMITMENTS (Continued) |
| 161 | 158 | [4677616,4690418) | `ea19be3ad8cd7d3a8d9d169e6c47e6da12385e9dcec815f5a26f77851909b5a5` | NOTE 18. DEBT AND COMMITMENTS (Continued) |
| 162 | 159 | [4690455,4702356) | `d06115f4db8eb99b91de36bdb89742d8cc5d2a34f997f7aee7d3cd13f2f398fc` | NOTE 18. DEBT AND COMMITMENTS (Continued) |
| 163 | 160 | [4702393,4713624) | `e164a5c0846f0b871b2be70e353d5ca74753d737fa96015ee23070bc98a383dd` | NOTE 18. DEBT AND COMMITMENTS (Continued) |
| 164 | 161 | [4713661,4729053) | `119c9cf649f2906ac64c3c60f03a456d58fce75d6967c7c76e9fd7f29820ec0f` | NOTE 19. DERIVATIVE FINANCIAL INSTRUMENTS AND HEDGING ACTIVITIES |
| 165 | 162 | [4729090,4768373) | `c17d204aaaee24a3440cb177496da24e4c0db64289d6097afa2acf5b87e77857` | NOTE 19. DERIVATIVE FINANCIAL INSTRUMENTS AND HEDGING ACTIVITIES (Continued) |
| 166 | 163 | [4768410,4825907) | `8251cf3418c4c5fba1be17d784463fe63f3af8a2d416dbb10a3340dcb1a088af` | NOTE 19. DERIVATIVE FINANCIAL INSTRUMENTS AND HEDGING ACTIVITIES (Continued) |
| 167 | 164 | [4825944,4843667) | `e417e8061e091b3fd34c8f9e670ec5b36b8811e9835a42872de878c95afe00c6` | NOTE 20. EMPLOYEE SEPARATION ACTIONS AND EXIT AND DISPOSAL ACTIVITIES |
| 168 | 165 | [4843704,4849878) | `ddcfbf60801ac0b5bf68dc40a5356e1d638fe7b9cc375e17db6ab50e0efe812d` | NOTE 21. ACQUISITIONS AND DIVESTITURES |
| 169 | 166 | [4849915,4940381) | `5a5b9c058dbcb521349b8f4c589330dadcdd6720a9e83c46da668a0a61af532c` | NOTE 22. ACCUMULATED OTHER COMPREHENSIVE INCOME/(LOSS) |
| 170 | 167 | [4940418,4951701) | `93bb5dc0c52af1e21e11df18f87656b802cb15f984037ac7486d3ba5aeb4b545` | NOTE 23. VARIABLE INTEREST ENTITIES |
| 171 | 168 | [4951738,4960667) | `b4cbfcac5bb4d6109c8b9d5bac49f29e3afac0d19aee50efec61511dcaddc883` | NOTE 23. VARIABLE INTEREST ENTITIES (Continued) / NOTE 24. COMMITMENTS AND CONTINGENCIES |
| 172 | 169 | [4960704,4966750) | `bf2678aecdbf65edfe48ea96310f410af169bc0a798385a7a3a155e517a709a8` | NOTE 24. COMMITMENTS AND CONTINGENCIES (Continued) |
| 173 | 170 | [4966787,4981847) | `ad3a9352b9fa1960f6a69cbda398ec836384ee7b64569960615bf8fbe10f2a1b` | NOTE 24. COMMITMENTS AND CONTINGENCIES (Continued) |
| 174 | 171 | [4981884,4990503) | `3421df25846cf944cbba58b968450670e42bade28c867da1db72289a366dad81` | NOTE 25. SEGMENT INFORMATION |
| 175 | 172 | [4990540,4996643) | `503a5206205c3f07dc80ed39a262ad485a7fceaf0cd79c1b0a33840e3a0fa199` | NOTE 25. SEGMENT INFORMATION (Continued) |
| 176 | 173 | [4996680,5010419) | `c7807ee4085935dfe4244f632e9ebae3fbb9513f05a7012e2372cdf2f5dd68f9` | NOTE 25. SEGMENT INFORMATION (Continued) |
| 177 | 174 | [5010456,5116936) | `81fe1a616f2e57b0bc777a3068e6297ba607bc133b14fc80dee4420ea5bf7162` | NOTE 25. SEGMENT INFORMATION (Continued) |
| 178 | 175 | [5116973,5210253) | `ea322559ad13898893f31040077353afe594f3904585c314253249e0fad1699d` | NOTE 25. SEGMENT INFORMATION (Continued) |
| 179 | 176 | [5210290,5281502) | `c1d5ba532d98f07cbdb9acf8b9ab735c6d1c02765f850a7b8adb0436581fee9a` | FORD MOTOR COMPANY AND SUBSIDIARIES / Schedule II — Valuation and Qualifying Accounts |

## 独立原文记录之后的固定实现/探针对照

对照时间UTC：2026-10-03T01:18:49.463849+00:00。以下固定提交文件逐份读取，未执行旧探针；新阅读结论与原有有限探针的对象/数值一致，新增覆盖与剩余应计角色缺口见conclusion.md。

| 固定提交文件 | SHA256 |
|---|---|
| `catalog/r5/B06_new_source_v2.md` | `e34a540f246302cd67abfa4c98a6da62bcced32f14b28be30a64049e80bfd944` |
| `config/r5_b06_debt_sets_v3.json` | `0ef10b3f5fb97678efe96c7915a3c10992779f1804107a906d3d0a1eea48e203` |
| `config/b06_special_scope_v1.json` | `ffa15f36da77df45802d863d59b64673f04bc5febdbc101c237595be60d0080b` |
| `scripts/vnext/ordinary_special_debt_scope.py` | `9c2bc47b455fd6a6deedfc52fc5f6bc406f35725f5f3f58b90482b78962d50c0` |
| `docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/README.md` | `fe9763fac65779b8edca30e21ca9e542937e9eab3ca00da119fdd2e33e119dd5` |
| `docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/probe.json` | `3a3a4268d6d0b222ec00407126b19245da143090d9216794fd397713c2994ef6` |
| `docs/evidence/issue28_continuous/b06-ford-equity-scope-20260927/visible-debt-balance.json` | `809e53020715483d0672cb926001ab3063a988cd03d1cd5e31056c6bfb94e7ba` |

补充XML角色核对：`InterestPayableCurrentAndNoncurrent`/`c-21`/USD=12,749,000,000，与Note18页157未来合同利息行一致；不能把这个标签当应计余额。真正Note15应计利息为`InterestPayableCurrent`/`c-19`/USD=1,453,000,000，无工业维度。该事实佐证在独立记录之后读取，不替代已完成的全文原文判读。
