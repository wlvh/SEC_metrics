# B06工业融资租赁的已报告包含关系

从main8588ccbbb1独立开发，不修改PR67，不增加其指标/模型/在线范围。复用原[Ford完整财报有限阅读](https://github.com/wlvh/SEC_metrics/blob/1f6272512d96e8bd0ea617bca010a4977791f80d/docs/evidence/issue28_continuous/b06-ford-full-scope-audit-20261003/conclusion.md)，本次只核必要Note18原表/脚注和实际来源准备，不重读全部财报。

已有 `prepare_special_debt_case` / `inspect_special_scope`增加显式 `reported_relations=True`，默认False保留原行为。程序复用既有原件准入、主体/期间/USD/工业维度、同一可见列及两原件精度检查。在相应当前/非当前债务段，绑定“Other debt (including finance leases)”行、所属债务附注与实际租赁事实；其他段的标签或其他附注事实不能替代。记录890m已包含，追加额0，不用表外人工数值或公司名特例。

实际Ford FY2025、0000037996-26-000015来源准备入口通过：报告债务21,919m，租赁136m/754m、共890m已在内。两项独立限制同时保留：工业归母权益未建立、完整B06债务集合未建立；B06仍WITHHELD/null。没有制造净资产残差分母、选择合并应计利息或使用未来利息标签，没有创建新Run/公司结果。新处理文件摘要进入显式来源输入用于普通排错，不作权限证明。

首次六项小测试通过，但追加的两个反例暴露：当前段标签误用于非当前段，以及要求重复披露全在一个附注导致误拒。日志保留；限定修复只绑定对应债务段，并允许已同值核对的事实在别处重复。最终8项通过0.001s，覆盖排除标签、遗漏/金额冲突、错主体/期间、附注错位及两项新反例。不扩展通用语言判断。

实际默认来源case与main8588原实现整个对象相同（hash见default-and-persistence.json）；新显式case保存/读取也相同，三次准备＋读写合计8.943s。初始显式case3.044s是修段关系前的版本，不冒称最终版本计时。保存的是2,366,738字节源case，不称轻量日常结果或完整运行。原探针两次引用不存在的事实字段在打印阶段失败，随后使用既有 `_source_value` 完成；不是原件或业务失败。

本批限来源准备与机械处理能力。普通公司入口仍未选择这一后继，原生Run/CSV完整接入及独立内容验收未完成；不得以源case保存一致或标签匹配提升完整B06信用。旧默认、旧Run/Result/原件及账本不变，新增provider/paid/SEC为0。

复现：

```bash
PYTHONPATH=scripts python -m unittest tests.vnext.test_industrial_lease_relation -v
python docs/evidence/issue28_b06_relations_20261008/verify_saved_case.py --source-root /saved/SEC_metrics
python docs/evidence/issue28_b06_relations_20261008/verify_default_and_persistence.py --source-root /saved/SEC_metrics
```

共享范围：ordinary_special_debt_scope.inspect_special_scope、prepare_special_debt_case，新选项默认False；旧返回对象通过实际原件比较完全相同，未修改任何 `_binding()`、旧Requirement、Spec或冻结快照。#47如要消费须明确选择和本方验证，不复制本方验收信用。新B06来源case未接收进当前公司候选；不合并/Ready/采纳/部署/active。


## 508c限定独审及包含行金额修复

[原独审](independent-review/conclusion.md)为NEEDS_FIX：原表结构反例把当前租赁改为1,000m、包含行仍226m，总债务5,550m，初版错误确认包含。旧结论不改，原代理25工具/3消息/7分35秒已结束，不再续发。

修复只读取对应当期工业列的包含行金额。倍率来自同列原生总债务事实，并先将其可见数与已确认原生数核对；包含行不能用附加单位后缀放大，缺倍率/错列/数值矛盾均未决。关系证据保留包含行单元格、USD金额和倍率。实际当前包含行226m、长期1,210m；原136m/754m继续通过，1,000m反例改为UNRESOLVED/追加额null。

10项小测试通过0.001s；实际默认完整case仍与main完全相同，原件正例及保存重读通过（三次准备＋读写合计9.001s），B06仍WITHHELD/null。修复后的原结构反例只是内存派生测试，无原件写回或获取信用。反例探针先因XML标签大小写筛选失败，错误保留；后改用既有metadata概念的casefold处理。这是探针设置修复，不改业务事实。

修后差异尚待限定复核，不据父方测试改写为独审通过；普通公司入口／原生Run尚未接入，不计新增完整公司结果。


## 当前终态：推算倍率路线停止，显式入口关闭

c5修后独审仍NEEDS_FIX，详见[independent-carrier-repair](independent-carrier-repair/conclusion.md)：包含行自身scale6→3且XML对应226000，两原件一致，初版仍借用总额scale6误确认136000000租赁已含。前一个金额反例确已修复，但没有解决含行自身单位／金额读取职责。原31工具/3消息/275秒记录保留。

不继续修猜测倍率规则。显式reported_relations=True现在在来源处理之前以REPORTED_RELATIONS_SUSPENDED_CARRIER_NATIVE_UNIT_UNVERIFIED拒绝；旧False默认不变。11小测通过，包含关闭入口反例；它不证明不足的低层原型已变正确。既有正例/源case保存证据只保留当时程序事实，不能授现行关系信用。没有新增完整B06结果、公司CSV接入或生产信用。

后续必要改进是通过既有原生解析器和单元格绑定直接读取包含行自身事实、上下文、单位、倍率及HTML/XML对应值；不再从总额或邻格推断，不重读全部财报。此代码保留为独立开发分支，未加入PR67、未合并。


## 直接读取行自身原生事实（开发增量，尚待新差异复核）

已退出借用总额倍率的计算方式。包含单元格通过既有 `_fact_cells`绑定到自身原生事实；读取它自己的USD、倍率、金额、主体、期间及已证明工业维度，并按完整概念/上下文与XML原件金额相互核对。只允许明确债务类别附加维度，未知额外范围不拼接。原有总额/租赁只作上层关系核对，不提供该行倍率。

11项小型真实解析器输入测试0.025s，保留当前/非当前、重复披露、错附注、主体/期间/USD和两原件冲突；补行自身不同倍率的正负例。Ford保存原件实际当前包含行226m、非当前1,210m、自身scale6/原生ordinal2443/2455；新入口识别136m/754m租赁已含，总债仍21,919m，完整B06仍WITHHELD/null。

原1,000m租赁反例与行自身226000USD反例均经公开来源API得到UNRESOLVED/null追加额（仅内存派生、无获取信用）。默认整个case仍等于main原实现；新case保存读取相同，三次准备及读写8.973s。直接事实增加元组字段曾导致JSON读回结构不一致，失败保留后按既有exact_json_value规范处理；原件字节不规范化/改写。倍率探针先误选同概念UKEF项，设置失败保留，限定到本原表Other debt债务类别后复现，不是生产公司特判。

现有显式reported_relations选项选择直接原生机制，原默认False不改；不通过改版本名清除旧两次NEEDS_FIX。普通公司出口/原生Run尚未接入，不生成完整公司结果或新正确比值。新差异必须按实际复核结论登记，父方测试不冒充独审。


## bd1e新独审两项P2与修复

[bd1e限定独审](independent-native-carrier/conclusion.md)仍NEEDS_FIX：父范围用前缀文字预筛，合法相同QName换前缀误拒、同前缀不同命名空间误接受；另外包含行自身scale9与XML一致虽直接读取，却覆盖了表前“百万”说明的矛盾。35工具/3消息/390.712秒，旧结论保留。

新修复对照已经验证的dimension/member QName继承范围，不比较前缀字面；合法别名保留，不同实际命名空间未决。额外债务类型轴仍限定标准FASB范围，不拼未知维度。包含金额还必须与本表明确单位及可见数一致；不将原生/XML一致当作可见披露无冲突。

现有结构索引未单列同一个div中的表前引言，真实正例曾误扣留（失败不作为业务正确结果）。修复只从原件的前一个表末至本表始的有界字节读取引言，保存区间/SHA；不固定距离、公司名或年份，不更改原件。单位读取排除XBRL资源定义/隐藏头及script/style，原始来源全部保留；不是全球删除这些元素来判输入等价。

13小型原生输入测试通过0.037s，新增合法QName别名与不同命名空间负例。真实原件来源准备3.389s正例通过；scale9/两原件226000000000、表内226百万的反例经公开来源API仍UNRESOLVED/null追加额。默认完整case与main相同，新case保存/读取相同（三次准备＋写盘9.601s）；B06仍WITHHELD/null、两项完整性缺口不变。来源准备不是完整公司CSV/原生Run/生产验收。新差异待限定复核，不将父方测试记成独审。


## 表格单位范围回修（48b之后的新差异）

[48b限定复核](independent-qname-unit/conclusion.md)确认前两项QName/倍率P2已修正，但发现表前任意Euro业务词触发误扣留；原NEEDS_FIX及40工具/3消息记录保持。回修只读取本表caption/头行和明确表格引言（as follows或独立单位行），不再将普通外币债务介绍作为列报单位；不消费较早发行说明中的倍率。明确外币单位和相互矛盾的表单位仍未决。不建立通用英文判断器。

16项小型完整解析器回归0.054s、零失败/错误/skip。保存Ford原件及与独审完全相同的内存派生反例共5.980s：原SHA3bbda、派生SHA8cbe均识别REPORTED_INCLUDED/追加0；两原件/原表其他事实不变，未写回原件。倍率9与XML226b但表仍百万的反例仍UNRESOLVED。默认完整case与main8588完全相同；显式case保存/读取相同，9.663s、2395954字节。初始原件探针错用结构索引table_id字段，设置错误日志保留后改用既有table_order；不将其当业务失败。

日志：[小回归](table-unit-scope-tests.log)、[相同原件反例](table-unit-scope-original.json)、[倍率矛盾](table-unit-scale-conflict.json)、[默认/保存](table-unit-default.json)。本次测试树为48b加industrial_lease_relation.py及对应测试的未提交差异；提交后另记录精确SHA，不冒充先前SHA实际测试。本次默认/元组保存职责受新证据字段影响，故只重验这些短场景；旧长链复用。

本差异尚待限定独审，不以父方回归提升信用。公司入口未选择此选项，无新Run/CSV/完整B06；工业权益与债务完整性仍未建立。main8588、peer d7c7ceaf仅固定读取；对方登记明确未消费旧原型，不复制对方结果信用。PR67仍adee、PR61仍86e，两者远端全部SUCCESS且Draft不变；不修改它们、不新增本批指标或业务调用。


## 明确外币符号回归修复

[487b限定独审](independent-unit-scope/conclusion.md)保留NEEDS_FIX：完整原表caption写Amounts(in €)仍被忽略。只补明确单位表达中的€/£/¥，不恢复整段任意外币关键词拒绝。17小解析器测试0.070s；原件、Euro业务介绍与明确Euro caption三控制8.509s，派生SHA与审阅原反例一致：8cbe合法通过、74797外币冲突UNRESOLVED/null追加。旧原件无修改。

同审阅还记录既有范围限制：较早发行说明也用as follows(in millions)时仍可能被选中并扣留；不冒称已经排除所有较早发行说明。这是仍未解决的范围绑定限制，来源能力不计完整验收。当前不据此生成比值/完整公司结果。此前“只读明确引言”仅指有限支持的结构，不表示程序已理解所有段落归属。

默认/保存对象机制未再改，复用table-unit-default证据；不是复用同一case身份，当前显式处理文件摘要随源码改变。实际新差异待原限定代理在剩余工具/时间/消息内复核，历史NEEDS_FIX不改。


## 最新限定结论与交付边界

89d2d649的符号回修增量由同一代理在剩余资源内复核PASS（累计37工具/2消息/611s）；补充结论追加于原记录，原487b NEEDS_FIX及所有旧日志保留。17测试0.073s、相同Ford原件派生正负控制8.462s由代理实际执行；未变默认/JSON证据只读取复用，不称重新独立全模块验收。代码树与89d2一致，后继归档提交仅记录证据。

表前as-follows范围误拦仍为具体限制，本分支未接公司CSV，没有完整B06结果或正式接受；不把局部包含关系当债务完整性证明。该限制不影响PR67已交的保存来源公司范围。PR67 adee与PR61 86e仍为可审查的Draft候选，远端终态SUCCESS；本B06分支单独保留，不扩本批组合。新增provider/paid/SEC仍0；旧来源、失败、Run、Result身份不变。


## 显式本表单位下的相邻引言回修

接续89d符号限定PASS之后的已知误拦，不重审旧修复。先增加原反例：较早发行as follows(in millions)，随后独立当前表说明、当前caption明确dollars；旧代码完整解析路径UNRESOLVED，失败日志保留。新读取先核所选表caption/头行的明确单位；该表已有单位时，引言只检查紧邻可见块的矛盾，不跨中间块回取更早披露单位。单位识别词表原样提为reporting_factors函数复用，没有新增英文主体/业务关键词。直接caption/邻接引言单位矛盾、外币、原生倍率冲突继续未决。

18项完整小型解析器回归0.075s/无skip；四个保存Ford结构控制11.801s（原件、Euro业务介绍正例、同SHA外币caption冲突及较早billions＋本表millions正例），全在内存派生、无原件写回/获取信用。默认case与main8588整个对象相同，新源case保存读取相同，10.131s；代码根/来源根与日志一致。表内明确单位缺失时，既有有界引言搜索仍是有限支持，不能把本次局部回修扩为任意表前文本归属证明。

被测树为7ae99dfd加industrial_lease_relation.py、新小回归及verify_table_unit_scope.py差异；提交后记录精确补丁SHA供限定复核。原NEEDS_FIX与89d局部PASS均保持历史范围。工业权益及B06债务完整性仍未建立，公司入口没有消费本选项，不生成新比值/Run/公司CSV。PR67范围和源码不变，新增provider/paid/SEC=0。


## 930a3df 限定结案

[相邻引言差异独审](independent-adjacency/conclusion.md)PASS：18小测0.077s、Ford四控制11.550s、11个base/patch完整解析器控制由新代理实际执行。显式本表单位下的旧as-follows误拦已修复；缺表内单位的旧有限支持不扩大。新代理35工具/1消息/373.476s，先核实际UTC并在90分钟内结束。原代理第三次接续跨空闲累计时间超90m，未执行本差异测试，停止记录原样归档，不能替新独审赋信用。

本分支提交小Draft仅交显式B06来源关系能力及默认兼容，未进PR67/公司入口。当前小回归加入现有fast workflow独立步骤，在旧cohort之前报告实际结果，不删除旧断言、修改required-check或将旧失败记PASS。旧cohort仍按各自实际终态解释；本源码被测版本930a3df，后继仅CI命令/证据归档。main/T1基础接收由原PR61/PR67承担，不搬入旧大分支或冻结/发布系统。


## PR72新入口：保留旧默认原字节，显式模块承接关系

PR72 adc9的远端旧native创建实际在业务断言前失败：Normal successor rule bytes differ:ordinary_special_debt_scope.py，日志已取得并保留；首次下载代理错误与CLI转义保护不是业务失败。不是将所有CI失败概括为此项。相应修复把新显式入口移为ordinary_reported_lease_scope.py，旧ordinary_special_debt_scope.py整个文件与main8588逐字节相同、原签名/默认case相同；不删除原校验、重绑冻结快照或再建信任平台。

新prepare_reported_lease_case复用原partial case、Calculator/Result/Trace；只从该case的原SourceReference与source_proofs重开唯一同URL/申报/SHA的primary/XML，再以旧native认证和既有行自身关系检查补V2来源body。重复同路径证明可复用，多个不同路径/错误URL或申报拒绝；重开后原件字节变化仍被拒。原Result保持WITHHELD/null及原主体/期间/范围，debug处理文件含新模块。数据/程序根继续分开，未新选财报或网络获取。

23短测0.079s（18解析器＋5原件重开/银行边界）通过。当前新入口四原件结构控制19.667s通过；默认整个case与main相同、新case保存/读相同11.897s、2396080字节。本模块在base准备后重读/解析该确切原件以获取额外含行事实，未宣称更快；这是当前显式来源 API，不是日常未变重算、模型调用或完整公司Run。

旧930单位差异已独审PASS，原件重开/包装的新差异需另限定复核；不把该旧PASS自动转作新包装信用。23回归单列在原CI，旧继承作业保留，当前主CI37761974002仍看其实际终态；现已证实18原检查远端成功，不冒称整条全绿。旧reported_relations可选参数原型只按其旧提交/日志保留，不是现行旧默认的新接口。
