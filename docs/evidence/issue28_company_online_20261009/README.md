# 空来源公司调用的有限接续

基于PR67精确`29c9c9e2080a1de8c809660ac8fbdfc49072ef12`，薄接现有SecHttpClient/SEC元数据验证/选年报/原生实例清单及普通记录公司计算。首批B01/B02；新AI、其他指标/事件全采集、OpenShift及生产未接入。不是另一个业务内核，也不把旧AI/Result当来源答案。

`run --call-context`用调用上下文指定原已存在账本、原用途、模式/上限及公司/指标。程序不建立真实账本、不扩大预算；每次HTTP前使用原CallLedger申领、原finish_sec登记，原历史/初始化锚点/UNKNOWN/重复与计数保留。元数据每个显式调用刷新一次，原件不重复取。零自动重试。记录型演练只使用隔离recorded ledger，不转换LIVE，不触碰原195槽账本。

来源/程序/计算根分离；来源在任务sources，计算在company-state，输出独立。无需FULL_SOURCE、内部树选择或旧计算。普通renderer此前把recorded来源一律当旧checkpoint，造成KeyError；只对录制来源的无旧checkpoint情况保留null，旧有checkpoint值及native默认保留，未伪造旧来源身份。

已实际执行的HTTP边界脚本见recorded_cli.py：只替换sec_http.urlopen，socket/DNS禁止，CLI main/发现/真实原件落盘/原计算/普通保存/CSV实际执行。Marriott原文件来源与长度/哈希逐请求核对。FY2025收入26186m、FY2024收入25100m，原文表中同名Revenue总计，与计算26186000000USD及增长率0.043266932270916...一致。原件引用/期间由实际接受链保留。开发内容检查不是正式业务接受。

演练包含空任务正常完成、禁用计算工厂的重复、刻意修改CompanyFacts消费数值的新结果、HTTP503刷新失败、来源恢复、独立读取，以及前期原件404时B01成功/B02失败隔离。数值修改是明确测试夹具，不是新真实财报或可接受结果。所有错误/早期失败日志保留，不从旧失败裁剪结果授信用。

所测源码为工作树，不能标成提交SHA已测。小测试、最终原件链的具体终态/计时见日志；后续提交对源码/依赖字节关系核对。PR80公共文档独立基于main；本候选只追加自身在线使用节，合并时保留PR80的main/候选/保留版本区分。

共享影响：ordinary_projection.render_ordinary_records录制来源无checkpoint兼容；CLI新增可选call-context，原source-root/原生任务入口默认不变。原SEC客户端/CallLedger/旧冻结Spec及默认_binding()未改。本候选依赖PR67接收，未把全部PR43/历史分支带入。

现有CompanyLocal模拟测试在本机20项中4项因未解析macOS系统临时目录别名报LOCAL_PATH_ALIAS；原行为未改，不伪称通过。新在线真实用户入口在显式绝对/已解析路径执行，不借该错误跳过计数/恢复验证。

61adc0e限定独审REQUEST_CHANGES保留：申领后计划落盘失败的摘要漏报、B02缺前期先阻断B01。修后pending在claim返回即设置，run/acquire摘要均保留未知槽；当前来源先获取，B02前期限制单独传递，继任主体不强迫前期比较。两个新增回归及原公司入口33项8.311s通过。原34行源/完整演练复用未变的HTTP/计算/保存责任；改变的获取顺序与摘要另作定向检查。非阻断观察：整体在线状态/计数从run_summary.json读，company-results/latest-execution描述计算阶段而非全流程。

精确f1c0088提交的最终HTTP边界链实际PASS（fixed-sha-program-chain.log）：首跑9.164s、禁工厂复跑1.102s、消费数值变化4.073s、503失败1.054s、显式恢复4.093s、禁网禁计算读取0.00841s、前期文件404时局部完成6.675s。原件/来源读取及计算原实现未mock。此前全链日志中的最后AssertionError是测试把程序正确的CANDIDATE_WITHHELD误写为异常；存储检查已确认原真实处理，原日志未改。后续修正测试断言后f1实际完整执行通过，B02具名NORMAL_COMPANYFACTS_ROUTE_UNRESOLVED及404出处保留，不改程序标准来迁就预期。

f1限定P2增量独审APPROVE_WITHIN_P2_INCREMENT：8短例+10边界，见independent-p2/conclusion.md；前次61adc独审REQUEST_CHANGES及两个反例保持。不是全PR/所有公司内容批准。后继仅归档该报告及日志，产品源码/测试仍精确f1，不重新重跑未变材料。

追加防意外重复获取的有限检查：原账本已成功捕获同一不可变URL时，换task/source目录不会重新申领，返回ALREADY_CAPTURED_SOURCE_REUSE_REQUIRED；元数据刷新仍显式计数。9短例2.067s通过。运行配置可指定原完整source_root，不复制/裁剪/重编号账本。实际CLI新公司状态复用原recorded来源库，仅2个元数据HTTP、0不可变原件GET，原请求行保留为18行，B01/B02完成；日志见existing-store-cli.log，未消费旧Result作为答案。这个新增源库接缝及重复目录保护尚需限定增量复核，不能继承f1两个P2的限定结案为其独审。

继续定位到一个实际模式边界缺口：早期recorded上下文依赖测试进程替换urlopen，普通CLI未注入回复时仍可能触达真实HTTP并按模拟计数。这不能交付。现明确RecordedSecHttpClient只读取recorded_http_root的原HTTP回复，复用原客户端持久化/日志，完全不打开网络；缺回复不回退HTTPS，LIVE拒绝录制输入字段。10短例通过；原SecHttpClient/CallLedger/默认原生调用未改。新增模式边界和源库复用待限定增量复核，旧两P2结案不扩大。这不是恢复信任/防伪框架，而是防止普通调用模式错误产生未计数网络。

4e09590录制客户端接缝重验仍完整PASS，见recorded-offline-chain.log。这是受影响HTTP模式的必要重验，不重跑未变D04/历史公司/还原包。原独立31/33测试与旧接缝证据保留其范围。

新增d91489e源库/录制模式增量限定独审通过：10例2.060s、20小边界，无网实际reply读取/原生写入/日志，缺件或字节变化不回退；未改旧两P2结论。报告见independent-store/conclusion.md。后继仅归档报告和订正docstring网络边界名称，不声称整个PR、业务/合并/生产批准。首批67默认入口回修不依赖本PR，本候选仍独立后续。
