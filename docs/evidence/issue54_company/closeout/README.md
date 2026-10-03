# #54 有限收口：消费者接收、历史重复成本与公司展示

接续303d751f；收口产品代码为191d148775995827f957e2a0d22ed70268bfcba2。来源、持续结果/公司CSV及保存D04接线沿用已经完成的实现；本轮不重新调查全部材料，不扩建发布、缓存或调度平台。最终证据提交、实际CI合并树和终态在 [#54唯一执行队列](https://github.com/wlvh/SEC_metrics/issues/54) / [Draft PR55](https://github.com/wlvh/SEC_metrics/pull/55) 固定，不能把源码、CI树、执行authority和Requirement closure当成同一个身份。

## 接收的实际消费者证据

`received-consumers.json` 固定读取六份文件的完整提交、路径、大小和SHA256，不冒称本方重跑全部材料。

- #28 [5963721452](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5963721452)，材料1f627251，实际代码303d751f：其52捕获历史的Enphase来源、原判断依据的SEC版本和原LIVE173–178处理材料分别准入；194.293s公司成功、91.240s另进程同尝试/一Run、0.657s实际等价SourceProof引用header篡改拒绝、旧成功不改。已有52来源61成员索引已接收。此前本方13捕获实验不升级成52，通过范围各自保留。
- #47 [5964869271](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5964869271)，材料af29ab2f：Paramount前身FY2024/继任FY2025各六事件，结果/期间选择/行哈希12/12一致、原生另进程冷读12/12通过，两期共存；保留8a→303差异分析及root限制，不升级为非root或五年业务接受。
- #28 [5964192295](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5964192295)，材料8dec9468，普通固定2a/a696树：Marriott C04同一source_root基线→52捕获更新，两Run及另进程双冷读；覆盖同财年来源更新，不是新财年或集群验收。

`change-impact-self-review.json` 是执行者自审/适用差异，**不是独立审阅通过**。普通/native分派、C04/D01内核、保存D04认证/完整等价和原V14身份未改。新历史作用域及外置信任键按差异在下面的固定场景验证；已直接向#47回链 [5965712264](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5965712264)，不要求机械重做12项内容验收，不自动为新closure释放D02。

## 704/5197秒的真实边界

#47 [5965535848](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5965535848) 补交原入口命令：`period_runs.py ... paramount-2025 paramount_skydance_paramount_global 2025-12-31 C01,E01,E02,E03,E04,E05 --layout shared --block on --memo on`。

原保留日志：select0.1s、install385.8s、create154.5s、**独立read_back163.3s**，合计704.0s；安装/create/read的memo computed/answered及replay计数在 `received-704-timing.json`。原period-outdir已被提供方为容量清理，本方接收其保存日志/执行者回执，不冒称拿到完整该轮period.json。5197s公司计算原报告未包含同一段独立冷读，且分别安装数据；不能把7.4倍直接归因于一个函数。

## 固定六事件的前后实测

受控准备端先验证原1547捕获完整来源，再导出Paramount公司包；计算端只携该公司原件与完整账本/准入元数据。来源包ID `sha256:a48403140e84c58cdd122bb7e45e1ca492492dbd0eeace0a4320ead7c30ad3e4`。scope含六事件及五年来源依赖，因此包ID与原消费者不同，原来源历史/账本未裁行或重编号。

金融程序固定51250475的受绑定字节，分别叠加303/191公司模块安装到独立只读树。准备工作区Git HEAD仍为60c6b4d6，是425项已核字节覆盖，不冒称checkout到了512；运行身份以实际封印为准：

| 身份 | before | after |
| --- | --- | --- |
| Requirement closure | `7034593a819db653e2a9589834b677105097433a8e94e55b2690119992cb5a0a` | `ef00c13440ddf809d6fd406f5c861d4e55984a37c56bf31d019b590534e24adc` |
| 安装execution authority | `2ec8b765ea6de8fec0ceb4ad5f01c22f268dbb03e35b7e413719428663a746e6` | `5b64bd93d113cc7ff698928a1ffbfd0a56883fde7bc545832651df01c004ff71` |

所有上述hash使用sha256命名空间，完整字段见 `runtime-identities.json`。这是新建的两组固定Run，未改签旧Run。两个新进程顺序执行，UID1000、程序/source-trust只读、独立可写state、同一公司包、各指标独立data目录、同一容器配额和温热文件缓存。通过本地审计拒读原checkout、准备根和完整恢复根，禁止网络/DNS；不声称内核隔离或独占宿主负载。计时从公司compute调用到返回，准备/安装和独立冷导出另列。插桩仅在内存，原程序字节不变；前段少量开发读取与来源安装重叠，不能将此单轮比值当成严格硬件基准。

| 相同计时范围 | before | after |
| --- | ---: | ---: |
| 公司入口总耗时 | 3388.767s | 372.774s |
| 输入准备实际调用 | 78 | 24 |
| 准备独占耗时（扣除嵌套被测步骤） | 2102.401s | 249.766s |
| 完整公司来源核验调用 | 172 | 11 |
| 完整来源核验耗时 | 1165.476s | 39.119s |
| 安装阶段（含嵌套准备/复制） | 573.606s | 160.982s |
| 建Run阶段（含嵌套准备/核验） | 1726.576s | 113.397s |
| 渲染阶段（含嵌套准备/核验） | 771.683s | 10.854s |
| 原有receipt哈希读 | 0.024s | 0.027s |
| 输入复制阶段 | 43.584s | 25.154s |
| 新复制文件 / 字节 | 6864 / 731078424 | 6870 / 731213094 |
| 被插桩sha256_file调用 / 逻辑字节 | 83606 / 16155070831 | 18501 / 1674210964 |

嵌套inclusive列与准备/来源核验重叠，**不可加总**。逻辑hash字节只是被插桩canonical helper的调用计数，不是物理磁盘读取或所有哈希。复制仍逐指标独立；新增134670字节是六份绑定所需的原memo程序副本。复制阶段下降也受已有账本纯函数作用域与文件缓存影响，不单独宣称IO提速。

这轮入口墙钟约9.09倍、减少约89%，确认重复准备/核验属于本次适配引入且可以复用已有机制消除。`before-profile.jsonl` / `after-profile.jsonl` / `performance-summary.json` 保存实际分段、结果和计数。六项Result ID、period_selection ID、row hash与before及af29消费者结果均一致；Run与Requirement身份因新执行绑定而不同。内容正确性仍按原规则/消费者接受，不以哈希一致作业务金标。

修复只打开#47既有 `run_checks_replay_once`、`derived_once_per_state`、`xbrl_parsed_once`：首次/改变状态仍运行冻结验证器；company census先独立比较trust，进入原多状态核验。fresh历史安装器将整个外置信任目录同时加入派生状态fingerprint和审计allowed读集合，原stray-read不豁免。不共享可变data、不建设长期缓存、不取消独立冷读。剩余复制属于独立数据安装，本轮测得约25秒，不继续扩建优化平台。

受控准备472.970s；before/after程序安装3.244/3.278s、来源安装21.769/22.159s。来源分项：原件81109007、账本/登记1478951、规则4245165、准入7062326字节。后续冷导出/重入、绑定负例及分项导出体积见集中摘要，不混入上述compute比值。

## 正反例、期间及释放解释

`trust-memo.json` 验证真实现有状态键/读审计/独立准入：相同状态ANSWERED、信任树变化COMPUTED、实际登记内容篡改拒绝 `COMPANY_SOURCE_NOT_IN_INSTALLED_TRUST`。小工厂只做真实准入，不当作财务派生测试。六项在各自新进程原生冷重放通过，冷导出130.429s、公司矩阵6行/证据30行；随后C01局部重入58.319s为NO_SOURCE_CONTENT_CHANGE/原attempt，无新Run，results14.871s仍列六项。`bound-header.json`从C01实际SourceReference/RawBlob及request_attempt_id定位headers：同作用域正向16.292s后，仅私有副本改写，0.524s被原账本locator检查拒绝（异常链明确headers hash mismatch），原成功8份pointer/Run/rows文件不改，原绑定header另核对准入哈希一致。这里证明活动作用域没有错误接受篡改，拒绝发生在原ledger locator重建；不据此声称观察到了哪一个memo调用。首探针确实拒绝，但仅识别顶层文案的断言误报失败；首脚本/日志保留，修异常链期待后复核通过，没有产品改动或新调用。

保留`period`兼容为Run归档坐标，另列`period_role`及原生`measurement_period`。这组六项FY2025均归档2025-01-01至2025-12-31，实际测量2024-01-01至2025-12-31；公司CSV同时列出两者。查询只有原生文件哈希验证，冷出口明确NATIVE_REPLAY_VERIFIED；缺记录或篡改不猜测窗口。单项失败不丢其它结果，旧值不冒充本次成功。

`d02-existing-release-read.json` 使用实际af29登记和消费者D02结果：相同result5aa340a1在ed360ebc/500ddf5f已接受，而消费者723f08af未释放，显示CURRENT_RUNTIME_RELEASE_REQUIRED和既有阅读/接受引用，仍WITHHELD；精确旧closure的释放仍有效，不同result仍扣留。此项是读取政策检查，不是本方重算D02或批准新closure。52项组件测试涵盖相关期间/记录篡改/跨版本与精确释放反例；模拟编排不冒称真实财报。

## 使用与未覆盖责任

完整可运行的来源交接→安装→B01+D01计算→仅B01更新→公司CSV导出命令见 [公司运行边界](../../../company_compute_boundary.md)。混合创建树显式提供各`--runtime-root`；旧规则/Run按原版本保留。容量不足时，仅本任务完成的私有负例副本和本轮before状态作逐文件SHA核对的无损tar归档，记录于 `space-preservation.json`；原执行者现场、既有成功state、原账本/旧规则未删。可在同路径解压恢复本轮对照state，归档保留全部Run/data/rule字节及模式。

本期支持保存基线、目标公司recorded增量、准备端验证后交付的混合普通/历史捕获、持续多指标/多期间视图及CSV、独立完整已保存D04普通判断接线。B13完整公司判断由#28；历史处理登记消费者及全部五年业务正确性由#47；历史公司处理参数仍明确IMPLEMENTATION_GAP，不把本期前置扩成全36项。Fable原脚本/日志未取得，未冒称复跑。OpenShift脚本/镜像/Job/卷/网络/SCC和新内网AI调用留下一Issue。

已有303的CI合并树af0b454与16/16+1/1成功固定于 `ci303-identity.json`；191的实际fast合并树5e174e66/基础9e37beb9与52项日志固定于 `ci191-identity.json`，不借前次CI为最终修改授信。最终源码和全部CI终态在#54/PR55集中固定。本期新增真实SEC/provider/paid始终0/0/0；无Ready、合并、正式采纳、部署或active切换，**DO NOT MERGE INTO PR43 BRANCH**。
