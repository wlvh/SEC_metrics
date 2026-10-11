# 历史期末RPO的有限公司接收

从实际main9493ed0e短分支接续，不扩事件PR93。现有historical_capital_cases中的已选期末case提为一个私有共用函数，A01/A02原入口/白名单保持；新的B12薄入口同函数、normal_accession原生检查器、Calculator、普通controller/store/read/CSV。政策/公式/普通当前入口不改，不写第二个采集或财务内核。

Salesforce FY2022–FY2026的原primary实例及已有独立rpo-read逐项同：43.7/48.6/56.9/63.4/72.4 billion USD，实际各年1月31日为期末存量，原FY2026 DEI字面2025与发行人FY2026解析及日期保持。五份原件检查29.776秒，FY2022只使用既有受控日期版namespace适配，其余原政策保持。它是RPO替代，不是ARR、cRPO或客户流失率，也不是全年收入。

同公司CLI五年首25.430s、禁止原factory复2.026s、独立读.508s，数值/单位/期末正确，45结果及pointer保护；记录器要求明确RPO != ARR的展示断言失败，原结果不重算，实际CSV仅写RPO substitute，公共投影责任已交#28。展示补齐前不记整段交付通过，见salesforce-fiveyear.json及salesforce-cli.log。

同任务只新增FY2026 B01的混合调用10.055s，旧B12不准备不重算，B01=41525000000 USD；原5年RPO保持。缺FY2027明确拒绝且5旧值仍读，新增一行失败/null不借FY2026。初控制错误把禁止复算施到新缺年，得到AssertionError；初记录器又错误要求读口仅有5行（实际还应有缺年空状态行），均保原log。修后只运行真实缺年.749s和读取.436s，得到源/选期报因、保45原文件，不重做混合或5年计算。见mixed-missing.json/日志。

真实Marriott FY2025 B12在检查器调用即失败下仍返回N_A_STRUCTURAL/null/TRAIT_NOT_APPLICABLE，约3秒，有所选来源/期间/行业规则；不表示财报没有RPO。当前登记只有Salesforce属于B12的subscription_or_contract_revenue范围，不擅扩其他公司。

27历史原件小反例/分派/状态例.164s零skip，保旧资本与其他家族工厂；错误单位/时点/分部范围/收入概念不能冒充RPO总额。初测试变异raw而未重造SourceReference被原校验拒绝，已修构造fixture而非放宽生产规则，原失败log保留。旧A01/A02完整来源证据复用未重读JPM，代码提取会作为相关处理版本变化，旧Run/保存结果仍按原版本读，不要求复刻身份。

本记录全部来源只读/网络禁止，新SEC/provider/paid/native Run/正式接受0。年度来源发现/补齐、修订/继任RPO范围、未测其他公司年度和全1950目标继续。该入口目前分支实现/展示待公共补齐；主要证据仅本目录，不制作新审查包或CI平台。

复现采用已恢复PR52 source-inputs和该分支程序，在外部新目录执行：

```bash
python3 tools/vnext_company.py run --company salesforce --period fiscal-years \
  --fiscal-year-start 2022 --fiscal-year-end 2026 --metric B12 \
  --source-root /saved/sec/source-inputs --work-dir /writable/rpo/state \
  --output-dir /writable/rpo/runs
python3 tools/vnext_company.py results --company salesforce \
  --state-root /writable/rpo/state --output-root /writable/rpo/read-01
```

## 公共展示增量接收

实际已接公共PR97/e53609e7，只有ordinary_public_projection_v1的B12公开说明。旧任务results只读保持原保存CSV文字，未原地改旧版本，不能把这次读口当新说明已覆盖旧数据；见display-old-read.json。随后以原五份已算records/Result/Trace及输入ID，通过现有save_calculated_case纯保存/渲染/读29.413秒，禁止原生金额检查器与Calculator，5结果和Trace/输入ID都相同，旧文件保持，新另存CSV明确RPO!=ARR/cRPO!=ARR/not a churn rate。只补实际期间/身份元数据，不重算原金额。见rendered-saved-summary.json。初保存输入未带原claims导致SELECTED_CLAIM_MISSING，原拒绝保持；补的是保存records里的原claim引用，不是新答案或手工操作数，随后在新目录保存。

公共PR95/0ff6fc9e也作为实际必要普通更新依赖接收：不让未用录制source_session变动触发旧结果复算，当前ordinary_current_update仍由#28实现，本方未重写；其Paramount唯一C01消费者验证在原事件主记录接续，不扩本RPO业务族。两个共享增量未入main前，本候选明确依赖其源码，旧记录/现行新展示版本分开，当前新用户RPO入口仍需受影响最终公司读取验证。

最后在同一公司入口只处理FY2026一个相关配置迁移：首4.233s、禁止factory复.818s、独立读.510s，72400000000 USD/2026-01-31/原Result ID保持，当前CSV明确RPO非ARR/churn；其余四年没有重算，所有旧Result文件保持。见final-cli-display.json/log。共享95+97实际组合43例19.856s零skip，原公共配置/展示反例进入其真实接口，本方不写第二controller；public-combination.log保结果。这里的公司接线验证成立，完整其他公司年度/在线来源与1950目标仍未完成，正式接受/发布权限不增加。

## 其余公司结构输出与身份缺口

除Salesforce外九公司FY2021–2025/B12共45位已同CLI首次/禁止原factory复跑/独立读，每公司5个源/期间绑定N_A_STRUCTURAL/null/TRAIT_NOT_APPLICABLE，与现行登记subscription_or_contract_revenue范围对应，不声称财报没有RPO。Macy’s期末分别2022-01-29/2023-01-28/2024-02-03/2025-02-01/2026-01-31，其他已选年末保持。全部原保存Result/pointer在复/读不变；实测每家阶段在other-companies-structural.json/log，没有全源或模型重跑。此验证不把空状态数当业务完成率。

逐行再核报送主体发现真实公共投影缺口：Param21–24 Source/Trace实体813828正确，CSV.cik却取今日registry2041610。原ordinary_projection验证prepared.entity属于登记集合后，baseline/_project_result仍用registry.primary_cik，未用已核报送人。此前已核的旧Param21事件CSV五项也出现该错误（values/窗口/源池相符不解除这一问题）。此前消费者核对遗漏CSV的CIK列，现补核并纠正交付范围，不修改旧Result/CSV或借旧接受记录盖章。准确代表源/trace/row见predecessor-cik-mismatch.json，旧事件行见predecessor-affected-old-event-rows.json。公共#28按共享renderer职责处理，本方不写第二版本；修后仅核实际受影响渲染/新读口，45结构结论及50B12完整导出接受目前未证明。

上游main4a03f223只修本指南此前误写的B04/B07名称：B04为净利润，B05为自由现金流，B07为利息保障倍数。该文档增量已接本候选06f02369，原计算/真实数值不因名称修正重跑。原错误及修复版本在Git保留，不把模块名当指标业务定义。

公共身份修复用的单个真实预计算case已保存为paramount2021-b12-precalculated.json.gz（gzip JSON，30796B；原JSON SHAcc9c10babf53e428ba93a4c9158bb39c46cda29a6379b876467db199f6f8ebb4）。只从原保存records/Result/Trace及输入ID重组，源金额检查器禁用，期间/报送身份用既有选期/DEI读取器核，旧Result文件未改；不是重算全批或新审查包。prepared.entity/trace.entity/源813828，原CSV2041610差异可经现有save_calculated_case→CSV→read真实重现。来源仍用原PR52恢复data_root，不给这个case新增许可/Run/接受。

## 公共报送主体修复的接收结果

远端 e4eff843 的十项检查全部 SUCCESS。实际 company-current 日志 run37931586112/job113823358130 明确加载并执行历史分派/保存状态两模块21项，1.082秒、零skip，包含RPO分派；现有工作流的 paths 同时列出两个测试文件。摘录在ci-e4eff843-history-execution.log。不是只核CI总绿，也没有为路径过滤制造额外提交。

公共固定79ff47b4已接入本候选c0487230，仅消费同一renderer，不另写历史版本。原Paramount FY2021 B12预计算case经真实save_calculated_case/独立子进程读取，CSV只有CIK从2041610变813828；原Result/Trace/input身份、期末、结构NA/null保持。该结构结果没有财务证据行，header-only evidence按原合同保留，不制造金额出处。金额检查器/Calculator禁止，无新SEC/provider调用。见reporting-cik-real-saved-case.json。记录器曾误用不存在的检查函数、将Result ID视为基础CSV列、要求结构NA有金额证据，原失败保留本地；更正的是记录器，最后直接读取已经保存的结果，没有重算。

同一组合的52项短/保存来源回归21.144秒中，51项通过、1项error、零skip。失败是既有真实当期Salesforce B12的RpoDisplayTest，不是旧防伪机制：_ordinary_case准备的annual实体1108524和accession0001108524-26-000060正确，但当前deterministic_source_set Trace的entity/accession按旧合同为null，新renderer直接要求Trace字段相同因而TRACE_SUBJECT_CHANGED。实际字段在reporting-cik-current-rpo-trace-boundary.json，完整日志在reporting-cik-combination-tests.log。

该具体兼容缺口已直接交公共#28，用既有SourceSet/claims可证明身份处理旧Trace格式，并保留未知/混主体的拒绝；不改旧Trace、删回归或放宽来源检查。当前仅Param旧期另存修复验证成立，组合尚未可接收；不得据此宣称当期不退化或50位置完整导出通过。后继修复返回后只跑受影响回归及必要保存/读取，不重做其余45结构检查或完整五年计算。

实际同一公司CLI另核只FY2021/B12一个相关处理版本：首7.998s/禁factory复.905s/独立读全部5年.582s，FY2021 CSV.cik=813828、原ResultID保持。其余四年未处理，30旧结果文件字节相同；旧年度CSV仍按原版本读取，不暗中重渲染。见reporting-cik-company-subset.json/log。结构NA在当前controller按CANDIDATE_READY→NO_SOURCE_CONTENT_CHANGE保存，其业务行仍N_A_STRUCTURAL/null，不误称业务扣留。当前真实当期SF旧Trace兼容失败仍待公共后继，不借这一历史路径通过消除限制。

同固定83225a57程序另核受影响的Param FY2022/FY2023/FY2024原预计算记录：26.159s纯保存/读，三年CSV唯一CIK2041610→813828，原Result/Trace/input及日期/空值保持；金额提取/Calculator禁止，旧每年六文件保持，不更新原公司state/其他年份。见reporting-cik-remaining-predecessor.json/log。首驱动漏已有admission字段在保存阶段被拒，补现有verify_ordinary_source_proofs返回后重做，未构造新scope或修改原件。四个前身年均有实际修正呈现验证，不据此授予当期null Trace兼容或完整B12五年接受。

## 公共null Trace修复后的实际组合

固定公共74b05a60已原样接入fa6619bc。已有填值entity/accession仍须同annual匹配，合法null需要同CIK/申报的已保存primary引用；仅无金额/无text的元数据状态可用同CIK inventory。缺字段、未知或foreign来源、混主体及未证明scope仍拒绝。原79ff独审NEEDS_FIX保留，74修后独审尚待公共方，父/消费者测试不冒充独审或接收批准。

本方59项组合29.896s/零skip全部通过，覆盖同公共controller的历史成功/稳定构造扣留/来源处理变化/子集读取，以及实际current Marriott酒店与Salesforce RPO保存/读。原52项中的真实当期B12拒绝已消除，旧失败日志保留。reporting-cik-nullable-combination.log为本方实际执行，不借作者37项或旧CI。

最终同一Param FY21/B12公司入口只处理一个相关版本：首7.869s、禁止factory复.874s/调用0、全5年独立读.520s，新CIK813828、原Result ID保持；其他四年未处理，36旧结果文件不变。reporting-cik-nullable-company-subset.json/log保准确执行fa6619bc。未重跑三旧期纯呈现或45结构NA，旧年度CSV仍保原版本。全家族当期/历史接缝通过不等于完整1950或在线取源。

已读并收到实际main67ae2c19到候选d66ddbc5，仅新增PR100的独立SecureGPT探针/说明/公共入口；相对fa6619bc，scripts/vnext、公司CLI、所用期间/展示配置字节无变化，因此不重复财报计算。没有执行探针或授内网调用；共享95/97/主体修复未main前仍是本候选的明确代码依赖。当前远端终态须按本次push的head核，原e4绿不移签。

提交前capability结构检查因本主要记录尚未进入HEAD而报clean-clone evidence differs，日志保留；不是业务断言失败，不修改检查器或重铸旧材料。先提交真实已验证代码/记录，再按当前main重复这个受影响结构检查；两个检查副产物始终还原为检查前字节。

远端f3dd9b31实际终态：company-current run37939874754/job113851224576 SUCCESS，172项143.849s含新真实current null来源/guard逐项ok，历史两模块21项.962s、事件13项.171s/9项.044s也执行。vNext37939874755整体FAILURE：fast/material/foundation三作业导入run_fast_tests_v2.py:200报NameError SOURCE_MATERIAL_TESTS未定义，原清单名为SOURCE_TESTS；其余四作业成功。失败完整日志及公司摘录在ci-f3dd9b31-*，公共#28修最小登记名，本方不改runner、旧快照或业务断言，不把公司SUCCESS称整CI全绿。登记修复后只核导入/实际选择器归属及新远端终态，不重算财报或重跑59已通过业务。

已原样接公共abb7abdd到0e6aff15：唯一清单名SOURCE_MATERIAL_TESTS→SOURCE_TESTS，不变业务/runner函数。实际导入通过，9guard在FAST_TESTS一次、3真实current来源类在SOURCE_TESTS一次且不在快测，加载12无error，函数/类AST与f3相同；runner-fix-receiving.json保接收结果。上述f3远端失败不删除，后继新head另核CI；本次不重跑已通过59组合或财报。

## 修后限定独审与既有登记重复项接收

公共c3ee8c84已原样接入561482f9：74/abb的null修复经限定独审12例+27有限反例通过，原79ff P1保留；范围、未覆盖及一次越限定GitHub只读请求如实在公共nullable-review/conclusion.md，不冒充全公司/全历史审阅。独审另发现两个旧selector重复导致真实runner开跑前FAST_TEST_SUCCESSOR_SELECTOR_CONFLICT，公共只删第二条相同声明。

本方既有runner实际定向执行两事件模块+reporter纯类22例/总1.464s全部rc0，173个fast及99个source共272登记全唯一，四函数/类AST同5ee，源/计算代码不变；dedup-receiving.json为消费者执行。初核对脚本把已含继承项的successor FAST列表再次接inherited而错误断言，修为实际runner使用FAST+SOURCE，不改生产或为重复字段开新测试平台。59组合/所有实际CLI和财报不重跑，5ee十项CI终态保持为旧版本，新head另核。有限组件可审查、接收决定及用户合并权限仍各自独立。

## 2026-10-10：实际历史事件出口接收边界

用户要求公共CIK修复同时核实际事件出口。固定51bfa32d纯渲染Param FY21/C01原Result(value1)、Trace(entity/accession为合法null)、25个完整813828事件hdr/primary/submissions引用时，公共renderer拒ORDINARY_PROJECTION_REPORTER_SOURCE_NOT_PROVEN。原事件case不携带annual primary引用；B12的null兼容通过不能代替这一类完整event-scope接收。historical-events-reporter-boundary.json/log保原字段/准确失败，已给#28公共作者。没有重算事件、GET、改Trace/来源、覆盖旧state或扩大B12结论。原20位计划首位即止，其他未验证位置不说通过。修后沿同一个公共renderer定向纯保存/冷读，原值/证据字节保留。

实际修后Param21–24五事件族二十位90.900s纯保存/冷读全部成功，120旧文件保持。只添加原选期已验证annual RAW/SOURCE，使共享renderer证明报送主体；矩阵及证据CIK均813828，原Result/Trace/input/值/单位/期间/状态、引用原文与金额/locator保持。CSVcontext新增annualref；纯重构首驱动遗漏原filing metadata导致form/filed回到annual，改用已存真实submissions metadata恢复原事件form/date（不是放宽业务检查），另零值证据允许其实际CIK submissions URL。三个驱动失败保本地，未算事件/GET/改旧结果。historical-events-reporter-fixed.json/log。九shared reporter反例.002s通过，错CIK/错acc/未知/无证明scope仍拒；30历史source/dispatch/state.186s零skip。此二十位的实证补齐，不能扩大为全事件/1950。

同一公司入口再核实际FY21/C01一个受影响处理版本：首13.161s/禁factory复2.247s0/独立读全任务.886s，新矩阵CIK813828、原ResultID保持。只此source-proof呈现依赖改变的坐标处理；其他年/指标及旧结果文件不动，原206文件保护，新增后212文件复/读保持。historical-event-company-subset.json/log精确终态；其余旧版本仍按原字节读，二十位纯渲染新输出不暗改旧current指针。不把这个代表迁移说成所有历史事件现行版本已全部切换。无新calls/Run/采纳。

## 已接六金融main后的PR96兼容接收

接收者已合金融104/107/109及105/108/110到main f6，PR96随后真实DIRTY。正常合入main为b0043687：保main公司六族和workflow全部模块，再加既有RPO；投影原公共c3报送函数与main平均期间函数共存，公共runner保各自既有selectors，未开发新内核/runner。42分派/主体/季度/事件例9.238s零skip，main-conflict-controls.log。旧公共说明采用main更完整审阅结论，不修改原日志。

另进程同新版读原Salesforce五年B12及受影响ParamFY21C01，原值/单位/日期/ResultID保，factory/socket禁止、旧结果/pointer字节保；main-received-old-result-read.json/log。驱动误把Salesforce CIK写794323导致首摘要断言失败，实际CSV一直1108524，随后只读该现成输出更正，未重复CLI/计算；首CLI耗时未记就保null，不把.001s摘要核对当性能。Param新独立读.819s保CIK813828。PR96只解合并/兼容冲突，原五年RPO、20位事件纯投影及一个实际公司迁移不重跑。新head远端终态另核，不借3905旧CI。

新ae293公司workflow实际触发37977413671/job113979074778并终态SUCCESS。日志逐模块核geography5/average17/scope14/dispatch18/state6共60方法.476s、零skip；shared主体12方法也实际执行，原保存源步骤208例194.737s，事件源13/.192s、历史scope10/.105s、原账本兼容22/6.049s均执行通过。ci-ae293-company-current.log/summary证明本提交的路径触发、作业执行及具体方法，不借旧CI。较宽fast/基础作业当时仍运行，整体终态另读，不因此重跑本地财报。


## 事件来源报送主体的当前接收修复

Claude6086515406的实际反馈按公共PR102/446bf33d接收，历史producer移除为了CSV新增的年报读取，恢复事件自身来源责任。固定组合04671728只正常迁移ParamFY2021/C01该一版本，1count/813828/全年/原ResultID保持；首22.255s、禁factory复2.276s、独立读.885s，其他坐标与全部旧结果保留，219受保护文件复读不变。48相关例9.449s零skip。原20位额外primary呈现记录保留，不把它当当前反馈已闭合；具体源码依赖、实际来源、未覆盖边界见同一目录[event-source-receiving](event-source-receiving/README.md)。本方未重复公共Marriott两反例，不新renderer/PR/真实调用。
