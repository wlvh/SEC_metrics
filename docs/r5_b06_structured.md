# R5 首批：B06 结构化主路径

最新实际结果与独立审阅见[本轮主交付](evidence/r5_b06_followup/README.md)：三数值、两非正权益、五项具体内容缺口；完整候选250坐标/328行，BLOCKED，正式根未变。[首次交付](evidence/r5_b06_structured/README.md)保留原计量与原阻断。

本入口从既定十家公司已保存的 submissions 与 Company Facts 选择最新普通10-K及其确切申报时点，不读取旧B06值来选择输入。指标仍是结构化优先、歧义触发既定fallback；本轮没有执行fallback，也未把B06整体标为已迁移。

`catalog/r5/B06_structured.md`仅定义结构化主路径，旧table Spec和历史ReleasePlan保持原字节。分子优先直接总额，不再加组成项；其次只使用完整同族current/noncurrent。lease-only、standalone noncurrent、冲突总额、另列短期债务或租赁涵盖性不清时，原生Result为WITHHELD/STRUCTURED_SOURCE_AMBIGUOUS，保存全部候选和原因。已保存instance中的实际金融业务member触发工业/集团范围复核，XML中的已核对账面调整事实可沿原生Observation参与计算，不从审阅报告补数，也不推定工业权益。

权益只使用同主体、同申报、同单位、同实际时点的StockholdersEquity，不擅自换成含少数权益总额。分母<=0经通用`denominator_positive`约束输出NOT_MEANINGFUL并保留实际输入，不能取绝对值。原生Run重新解析原始Company Facts、重新执行选择和Calculator；输出文件中写PASS不能绕过这一重放。结构化事实沿原生确定性链，不伪造AI Evidence或人工Review；独立内容审阅另作验收。

普通10-K后若有同期间10-K/A，保留原10-K的as-filed Run及修订事实。新采纳层只有在确切原年报和修订全文绑定、独立完整范围判断及机械负例核对均成立时，解除对应修订阻断；未知或财务相关修订仍标记AMENDED_ANNUAL_REQUIRES_REVIEW。本轮Southwest/Paramount的确切非财务修订已完成此判断，不构成未来同类修订的自动豁免。

## 运行与读取

在干净已提交实现上，所有输出写入checkout外的新目录：

```text
python3 tools/vnext_r5_b06.py prepare --candidate-root <新的外部目录> --output-json <新的外部JSON>
python3 tools/vnext_r5_b06.py read --candidate-root <同一目录> --output-json <新的外部JSON>
```

默认且仅支持已保存材料，provider/paid/SEC=0/0/0，没有网络获取或AI分支。prepare复用既有Run、Projector、完整文件封包与校验；read经相同PublicationView查看完整矩阵、证据和B06原生来源。再次prepare核验并复用同一包，不新增生产事实。输入不足导致准备失败时保留日志及原正式版本，不拿旧值补缺。

完整候选包含250个候选坐标=240个正式继承坐标+10个B06新结果/阻断坐标，公共矩阵为328行：前驱327行中原有9条B06，另新增JPM B06明确阻断行。原B06行被本批结果或明确空值状态替换，其他318行及证据逐项保留，所有期间来自各自来源。包内BLOCKED不是正式成功；全部切换、部署、回退、恢复及镜像写权限均拒绝。本轮未创建active指针。

`issue_28_v9`是待最终审阅的有限Requirement草案，承接全部父级义务并逐文件绑定当前执行内容；没有激活旧金融路线，没有新生产grant。正式集合保持24指标。包内继承的旧semantic/scalability/retirement收据明确保留原范围，不用来声称新实现已经受其认证。新实现的检查与独立审阅单独归档。

## 后续决定

B06正式采纳前须解决本批受阻坐标或明确允许的部分采纳范围，并批准实际发布计划。租赁是否已计入、短债涵盖、standalone非流动额与总债务、工业分母及修订影响不靠默认值决定。旧B06语义生产/补数入口的正式停用与本批正式采纳一起验收；本轮只证明新路径无需调用它们，不提前破坏实际生产。

PR41已用merge commit合并。持续生产许可、正常触发与真实新材料运行仍单列责任；R5其他三项、WB-7、R4新路线、R6和Rf未在本轮展开。

<!-- capability-anchor: CAPABILITY.r5_b06_structured_primary -->

本工作包的候选来源核对限定为已提交、已保存的SEC请求材料，程序自动从原始清单选取并核对获审head内的正文、headers与请求账；不手填答案。它只约束这份零获取的迁移候选，不宣称已实现未来新材料的B06持续生产许可，也不将逐份Git提交作为未来正常更新的产品设计。后续真实输入权限仍须沿已记录的正常运行责任解决。

## 本轮来源判断修订（语义 revision 2）

新发现入口在排序前校验所有10-K/10-K/A的期间、申报日期、申报身份及原文文件名。日期不明不会被过滤；涉及当前/后续期间的历史分片未读取时明确阻断，较早分片排除范围可追溯。保留非自然年度。旧v1仅用于旧快照的读取与重放，不授权新建旧v1 Run。

用户已明确新B06的计量为已定义债务集合的期末账面余额。Lumen按原XML同主体、同日、同单位的本金减折价及发行成本，与流动/非流动账面额及直接账面总额闭合；Southwest按同表扣减成本前小计减成本，与流动/非流动闭合。gross和扣减项真实进入Observation/Calculator/Trace，非从审阅报告抄数。完整附注的独立关系判断绑定原件SHA/文本SHA及关系类型，金额从原件重读；同计量的CF/XML冲突、符号/单位/主体不一致或差异无解仍拒绝。新语义和新候选另行保存，旧冲突与旧计量结果不追认为已通过。

两份修订的完整独立原文判断作为数据影响证据进入新采纳记录。程序核对受控review字节、原10-K与10-K/A原件、issuer/期间/引用关系、完整正文身份、段落/事实集合及财务反例；不按公司或accession白名单或关键词独自放行。原始as-filed Run及修订存在事实不变，新采纳层单独给出NO_B06_SOURCE_IMPACT。两份原件AmendmentFlag=false的矛盾仍保留。未知/改变原件没有对应全范围判断、财务重编或原件缺失时继续阻断，不将此处理扩成所有PartIII修订的通用豁免。

五家公司组成关系补充记录只解释原文包含/排除关系，不成为Calculator数字输入。剩余命题分别是Ford工业权益分母、Pfizer现金抵押短债的集合归属、JPM银行融资集合、Salesforce融资租赁是否纳入、Macy’s融资租赁与其中非租赁组分是否纳入。它们不被笼统称作缺材料或需要AI；本轮仍零业务调用、无生产权限。
