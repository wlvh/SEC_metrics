# Pfizer FY2024 D02：完整参考和正常审阅问题

正常保存来源准备已经认证 `pfe-20241231.htm`，accession `0000078003-25-000054`，原件SHA `05b77064b72e16b39bc80dfa10d12d18e4b470c0df63c2cb89d3884e813bb97f`。完整Item8范围 **[1882,4249)** 的 **2367原块**在16个连续未筛分包中全部读完。原文档全部字节跨度在准备时验证，完整问题并未只保留含关键词的块。图片/完整表格未包含在这些文字审阅问题，不能授各媒介接受。

完整开发问题SHA `ad92f3abb9e0a4ab2a39310f06e52688905778e3e5d0e0a6218488b918be3a17`，87457输入+4096=91553，150必答块。它保留原 `D02_ITEM_8_LEGAL_REVIEW_V1` 含义、结构和20–300字符连续引文合同，但池子比正常审阅更完整，**不可直接注册成正常池的回答**。没有读、改、裁剪或重发旧付费失败答案。

执行者完整阅读后判114正向原块。参考引用只从本次原件绑定：80字符引文表示4723token、48字符4153，均超原4096；最后有界的32字符表示3781，全部150判断和114正向块相同，仍按原20–300合同验证。第三种首次在短标题B3815取了不足20字符的窗口，原校验拒绝；修正窗口位置以保留最低20，未放宽合同。原两份超限参考和该失败说明均保留，**不是修补旧模型响应**。3781只证明参考可表示，不证明独立模型生成。

最终完整参考SHA `f17999a5db99e9e0ee213f86aa1a69394824b3c9bcccc39774f6d60e6eaf6e49`，实际冻结时间见包内receipt；参考固定后才读取当前v4实际选择和正常审阅池。

原件的实际区分：

- Note1S B2351/2352是真实legal/environmental loss recognition/insurance recovery政策，计入；审计师报告1882–1918即使描述实际产品诉讼或税务settlements，仍按原定义排除。generic estimates2214/15、legal-fee/cost/collection政策2280/2288/2314不是案件。
- 已收购且合并的Seagen在2397确实涉及patent/IP/product诉讼；“普通业务”“不重大”不排除。2395是广义收购会计计量，2396假设environmental/ARO/guarantee、2398普通tax-position计量，分别排除，不把全部 acquisition contingencies 收取。
- Certain legal matters567million及产品责任费用2666/67/2679/3987有实际来源；保持“primarily”限定，不当案件数，不把重复披露当第二敞口。递延税资产表中“Legal and product liability reserves”2813及其税资产金额，不是新的法律损失金额。
- B2877关于tax-position估计、settlements/statutes及“can include formal administrative and legal proceedings”是泛述/可能过程，排除。B2876明确陈述已有audits、appeals和investigations；执行者仅以实际tax-authority investigations/appeals作为正向依据，不把所有open years/普通audit或税额转成诉讼。若业务含义意在排除这些普通税务行政程序，仍需澄清；这份参考是执行者判断，不是owner新增决定，不能用tax整类收取/排除解决。
- Note16A完整原诉讼、政府请求、相关政策、标题和延续句计入。原告和被告均保留；2019等历史事件、Jan/Feb2025后续事件保持实际日期，FY2024仅是申报容器。Warner-Lambert/Pharmacia/Hospira/Biohaven合并关系及实际赔偿/防御责任由原文支持；另公司名称不自动成为排除理由。
- Note16B/C/D的通用indemnity/guarantee、purchase/milestone commitments和acquisition contingent consideration，没有实际索赔，排除；既有Warner-Lambert/Pharmacia实际claims及indemnity另属正向。3936/37自保product liability、existing accruals和insurance不足敞口计入，不要求每项都具名诉讼。养老金/投资settlements、销售true-up settlement4158及产品withdrawal4159不按同一个词收取。

当前规则真实提案107摘录，其中106在Item8。与完整参考逐块对照，B2877是明确误中；九个参考正向块未选。计数的范围是原块而非案件/指标，不能用107与114直接算漏项。正常审阅机制已经能够处理其中大多数：其实际池1384块、64必答，原keyword admitted仅2352/2397/2877；池中包括实际2876及可能泛述2877，也包括自保3937、费用2679/3987等。Note16A由其他既有范围负责，不重复交给该审阅。2667金额格不在该池，其他原段已另有567million表达；本次不因此改正常池或强制纳入所有短格。

**正常生产问题已按真实函数和渲染器重建**：`legal_review_request`、`continuous_semantic_calls.request_body`，无参考/旧答输入。精确SHA `7a8ec74c91841dc5be473ffadddf9f221339aab034975a0f5860682846ee1b9b`，59765+4096=63861；执行者正常池参考1294输出token。第一份手动outer-wire问题 `1d5802df…` 与实际渲染器字节不同，虽semantic对象相同，已保留为失败identity比较，**不当作native request**。第二份真实渲染器字节在新目录独立重建完全相同。仍未调用、注册、创建Run或给业务信用。

五项原合同内存注错均明确拒绝：>300字符连续quote、quote不属于本块、缺一个必答、加入不属正常池的Note16A块、重复判断。原短标题作为>300反例的首次试探没有满足前置条件，保留为precondition failure，不算已进入负例。没有修改原合同、checker、原源或调用预算。

归档包含完整准备文档/问题/准入记录、16阅读包/笔记、三种执行者参考及冻结时间、实际v4提案比较、两种正常问题与identity失败、正确生产渲染器重建、原合同内存负例和实际源码。原raw/header从既有SEC导出恢复；准备源时用私有`.git`克隆的原认证日志，不能在linked worktree绕过准入。五个相关执行模块逐字节与本方当前代码相同。

`prepare_full_item8_development.py`保留正常navigation原状态，不给新注册入口；`prepare_native_review_question.py`只重建真实原问题；`rebind_executor_quotes.py`只包装本次人工式判断的来源引文。它们均不作为运行操作数或默认consumer。重建完整参考需包内前一版人工参考，属于开发材料，绝不提供给独立答题代理。

新增DeepSeek/paid/SEC `[0,0,0]`，新Run/接受0。独立精确输入验证及最终DeepSeek一致性验收没有新增许可；正常接入与接受尚未完成，既有旧结果/失败/模型包不改。本参考及正常请求为后续方法验证提供具体对象，不能用计量/格式通过替代生成和内容判断。
