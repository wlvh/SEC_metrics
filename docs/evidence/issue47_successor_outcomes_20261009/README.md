# 转换年度的已批准可比性结论接收

独立从PR82/d279接续，原候选不扩。公共catalog/graph原已对注册表noncontinuous且REQUIRE_CONTINUOUS的年度指标返回ENTITY_CONTINUITY_NOT_COMPARABLE；旧历史实现也已消费，普通历史薄入口却先报未实现。现仅verified SUCCESSOR_REGISTRANT_ONLY、selected CIK=prepared entity=registry primary、cross_entity=false、当前年度companyfacts REQUIRE_CONTINUOUS时，用同一早期guard输出结论。不改globalregistry/普通当期/公式/概念，也不自行形成财务值；B01继续要求statement scope，修订年度金额不借此获得准入。

Paramount FY2025同CLI混合B01/B02/B04/B05/B07首23.322s，B01原范围未接失败不掩其余四项，四项NOT_MEANINGFUL/null、APPLICABLE、原ENTITY_CONTINUITY_NOT_COMPARABLE原因为已批准业务限制。0 financial claims/observations、statement_values_used=false、annual/amendment statement scope未准入，原件/headers仍普通来源核对。不把这四个正确空值说成四个数值或完整39指标接受。

四项子集同输入复跑1.165s source准备/graph0、32结果/指针文件不变；另进程只读0.127s selection/update0、CSV/出处四结论保持。两个临时驱动原期望把B01失败也算第五个current保存行，得到AssertionError；原log保留，按实际保存语义只读核四结果通过，没有重算/造第五个结果。B01原失败仍留初始执行日志；仅选四项后的当前结果读不把该失败冒充保存的财报结果。

实际源四guard25.810s在_filing_source和_select_deterministic_branch“调用即失败”下仍过，证明没有选金额或算算术。50小例0.134s零skip，wrong selected/entity/mode/cross/route拒绝，B01仍scope拒绝、原前身/持续/修订边界不放宽；cap对实际父分支PASS。

[唯一验证记录](verification.json)和[实际普通结论/CSV/驱动/原失败](consumer-materials.tar.gz)已Git。无源码/来源整树复制、无新存储器/runner。新SEC/provider/paid/native Run/接受0；旧Model35、Run、失败与费用归属不动，未main/Ready/merge/正式采纳/部署/active。后继实际年度金额与源scope/日期仍是未完成业务，完整1950目标保持。

## 同一历史薄入口的适用性报因修复

JPM五年B07原先先取金额，在银行没有适用的operating income时误报APPLICABLE/NONE/来源未决。既有Spec要求non_financial，实际trait是financial；公共普通解析和银行case已先判行业不适用。现历史薄入口复用同一个metric_is_applicable和_manual_result_trace，在金额选择前给N_A_STRUCTURAL/null/TRAIT_NOT_APPLICABLE，保原件主体/期间身份，不改trait、定义、公式、单位政策或公共controller/store/runner。适用公司仍须满足来源要求，不把任何缺源改成不适用。原继任状态case只提取共同元数据保存形状；完整实际case比较逐字段保持，原四个Paramount状态不重算。

此前已完成的JPM FY2021–FY2025同CLI定向处理176.044s，现在直接复用：五个正确行业不适用结论，0财务claims/observations；原五个错误WITHHELD保存记录及字节保留。禁止source准备/计算复跑6.042s=0、75结果/pointer不变；另进程只读0.146s。真实FY2025额外在_filing_source/graph调用即失败条件下20.905s仍生成正确NA，证明不提金额；不是模拟财报结论。52小例0.153s零skip；初构造fixture把trait写成字典而非真实list的失败保留，修测试数据格式后通过，不放宽生产规则。旧180.402s误报与修后176.044s不作提速归因，期间元数据准备仍较重。

[主verification](verification.json)新增此修复段，原继任验证保持。10份原普通结果（5错误+5正确）70文件604735B按原字节保存为structural-results及索引，可用共同read_saved_result直接读取，无程序/来源整树复制，无新审查包或证明链。两新短例的公共CI登记由#28统一接收；不据旧head CI宣称新类已执行。修复收口在现有PR84，不新增PR/更深依赖，不纳首批PR71；main、线上来源获取、业务接受及完整1950责任未完成，新增SEC/模型/Run/接受0。

已接公共90e5e511提供、目标d279的pr82-small-selectors固定补丁：原年度金额/主体两个短class进入既有v2清单及实际workflow显式步骤，runner函数/类AST保持。当前7f18代码上的9类实际41例0.041s、零skip，日志及补丁SHA在同目录public-pr82记录；原52本地结果及真实金额/状态验证复用，不重算财报。继任三例和新增结构适用性两例的公共登记仍待#28增量，不把这41例说成新五例已执行；没有新runner/历史CI平台。
