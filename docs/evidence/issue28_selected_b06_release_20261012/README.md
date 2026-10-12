# 显式选定B06原件的DEI/FASB读取选项

起点actualmain2741821e；来源和原复现由#47固定ee6024be提供。历史选年及来源已通过，但公共权益原文检查重复使用YEAR_ONLY，拒绝DEI季度声明与FASB日期版标签。本方先收尾具体接收请求后，仅落实已知调用链的这层，无新债务定义/金融完整性信用。

_source_equity/_rebuild_equity和ordinary_debt_guard的显式入口新增可选dei_release/namespace_policy，默认YEAR_ONLY。非默认按已有normalannual reader与is_fasb_namespace有限枚举，未改全局正则、未构造release_aware动态包装；wrongdomain、q5和FASBquarter不能被该选项接受。默认内部调用参数和完整返回结构保持。显式wrapper把source_reader_options写入自己的新组件身份；原件SHA、同主体、actualperiod、USD/visiblecell/sign/scale、primaryXML与同申报CompanyFacts仍逐项校验。

构造失败回归证明旧API不支持这些显式参数；修后guard8例及当前入口26例0.106s零error/failure/skip，含完整默认对象相等与原badsource/精度/非正权益/可见符号保护。

Root真实保存原件经既有historicalsource preparation再走公共ordinary_debt_guard：EnphaseFY2021 acc1463101-22-16 equity430,168,000，9.072529s；SalesforceFY2022 acc1108524-22-13 equity58,131,000,000，8.864991s。原default拒绝原因保，显式primary+XML+samefilingCF重建通过，两个status都是CONTINUE_DEBT_PATH、resultNone、debt_completenessNOT_EVALUATED。原period、source references、精度/可见格证据在equity-originals.json；该结果不代表完整B06或11公司年度全修复。没有source模型/GET/计算器新调用。

verify_equity_originals.py使用显式source-root/output，只有网络被禁止，来源准备/原生三源检查真实。实际执行工作树，后续SHA不得倒称已测。下一依赖仍为special/note/inclusive/bond等真实被用语法和selectedcaller的显式传递及处理配置，需source准备→完整公司保存/复跑/独立CSV再授完整信用。#28单写公共API，#47负责其历史caller/消费者；不让它复制第二内核。

此本地增量尚未发布/接收，不扩PR187，亦不当作全部B06、390、生产切换或预算授权。旧原件/Run/Result/ledger保持。

## 实际后续：选定期间的债务处理

已将同一显式选项沿现有 special、reported lease、note、bond、inclusive、融资清单及 selected B06 接缝传递。使用原来的来源、表格、单位、主体、精度和债务完整性检查；没有新建选择器，没有把无法解释的融资事实排除。`source_reader_options()`验证有限枚举，默认产生空参数字典，保持旧私有调用形态。选定调用的 input binding 保留选项；`SELECTED_RELEASE_PROCESSING_FILES`列明实际使用的年度读取和命名空间模块，历史消费者须显式消费这些依赖。默认公司入口未擅自切换。

真实原件使用原有历史选源和真实修订 packet，随后调用公共 `prepare_selected_b06_case`。Enphase FY2021 9.110s、Salesforce FY2022 9.627s，两者通过来源/年度读取并形成原生扣留 Result，不再因 DEI 格式在权益层抛错：

- Enphase：`NOTE_CARRYING_UNRESOLVED_FINANCING_FACT:debtinstrumentunamortizeddiscountpremiumanddebtissuancecostsnet`，Result `cadd0b9a...`。仍须证明该融资事实与债务表的关系；不能把不认识当作零。
- Salesforce：`IMPLEMENTATION_GAP / SEPARATE_LEASE_CLASSIFICATION_NOT_PROVEN`，Result `c4aac149...`。仍未证明独立租赁分类；没有获完整数值信用。

[驱动](verify_selected_originals.py)、[实际结果](selected-originals.json)和日志包含来源身份、实际期间、选项及具体未决；输出是完整case检查结果，不是正式公司 CLI 保存/复跑/CSV验收。历史调用方仍由#47接入并验证，不把两份case或两项权益通过说成11个历史位置全部修复。

修后62项必要短控0.156s，零失败、错误和跳过；包含默认调用不增加参数、三个现有语法逐项收到显式选项、匹配失败不绕过、未知选项在处理前拒绝、单位/主体/工业租赁关系及原B03日期版检查。此前46项含未变完整默认返回验证的21.629s日志保留。工作树身份在 `propagation-tested-worktree.json`，后续公开SHA不倒称实际执行SHA。

测试脚本的第一轮在计时序列化处失败（浮点计时进入拒绝浮点的canonical层），原日志保留为 `selected-originals-harness-error.log`；仅改计时字符串后重跑纯离线case。最初一个脱离等待的后台启动没有留下运行进程或结果，随后采用nohup加shell等待取得真实终态；它不记为业务执行。没有修改业务响应、来源或旧状态。

公司CI增加本批实际源路径及证据驱动触发，不改五层测试分工或吞掉已有测试。当前 main 已接收PR187；其完整费用证明与本次 B06 读取独立，待正常接入后仅补受影响短控。新默认、现有旧运行和真实业务额度保持；本批0新增SEC/provider/paid。

正常接入后：本地 `9d377cb8` 的接收部分与实际main `1b997f41` 完整树 `50b39c88` 对应，比较使用独立临时Git索引，没有修改来源或状态（见 `main-combination.json`）。唯一workflow冲突取必要并集，保main的 `scripts/**`，不重复添加各个B06源路径；只增本批guard测试/证据触发。组合62项0.149s零skip，B06源与两真实case实际被测字节未变，故不重复原件准备。此记录不把接入后的SHA说成此前执行SHA，也不替代后续历史消费者的正式公司入口验收。
