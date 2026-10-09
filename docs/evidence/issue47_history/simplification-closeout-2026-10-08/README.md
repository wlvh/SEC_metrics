# 历史消费者接收：2026-10-08

本轮唯一主验证记录为 [verification.json](verification.json)。能力结构检查通过（6.868秒），检查器两个副产物按检查前字节恢复；这只证明结构对齐。实际 main 仍为 `8588ccbb`；这里是分支交付，尚未入 main，也不是完整五年业务接受。

当前可取得的组合是 PR67 的公共候选 `29c9c9e2080a1de8c809660ac8fbdfc49072ef12` 加本分支 `task/issue47-history-consumers`。原adee/c56验证按原版本保留，下方2026-10-09记录核当前组合。后者只增加现有历史期间选择、酒店 case 适配及同一公司 CLI 分派。公共控制器、保存器、投影、状态恢复和测试运行器全部来自 PR67。PR59 的已选来源共用计算已经包含在 PR67，不需要再次顺序合入 PR59。现有 `historical_dei` 旧命名空间包装作为必要上游依赖保留，没有将删除所有旧包装作为接收前置。

## 2026-10-09 首批接收审查入口

[当前组合与自动回归记录](pr71-first-batch-20261009.json)是本主记录的增量；旧日志及结果保持。PR71已在既有 `company-current-records.yml` 加入两个测试文件的精确路径过滤，并新增同一作业内的verbose步骤实际执行两个模块，不修改公共runner、原作业或五分钟时限。本地12项0.140s全部通过。`0d58e55f` 的[pull_request工作流37881312033](https://github.com/wlvh/SEC_metrics/actions/runs/37881312033)已SUCCESS，job113661400662及历史步骤均SUCCESS；[实际日志](pr71-history-ci-0d58e55f-remote.log)列出两模块12项逐例ok、0.845s、零skip。触发范围由精确paths核对，本提交的workflow变化实际触发；没有为测试文件单独触发制造提交。

随后按当前拟接收PR67/29c9接收实际普通处理依赖和B03数值来源修补。历史分派、producer和两个历史测试字节保持，公共controller/writer/reader与当前公共候选一致。84项受影响当期/历史/酒店/状态/公司测试7.486s全部通过，[原日志](pr71-current67-combination-local-20261009.log)。未再跑既有两年B01、全部酒店原文或五年集合。

当前组合直接用PR71已提交原件、headers和日志运行Marriott FY2024/25 B10/B11：[真实首跑及禁止工厂复跑](pr71-current67-real.json)分别19.130/2.465s，四值与本页原数值/单位/实际期间相同；[独立进程读取](pr71-current67-read.json)1.021s，选源/计算/update/业务网络禁止，32个结果和指针不变。不依赖开发者私人来源目录、不拷程序/来源树、不产生新调用。正式命令与输出目录解释在[历史使用指南](../../../historical_company_usage.md)，只读来源，审查输出写新的外部目录。

PR58固定372f4b74与PR62固定09563892分别依赖PR61/86e63816；两份原PR head的实际检查已SUCCESS。机械D02直接执行 `python3 -m unittest tests.vnext.test_legal_review_contract -v`：夹具为12份完整原回答及所引原块，8拒绝/4合同通过、14条真实长引文仍保持。H2直接执行 `python3 -m unittest tests.vnext.test_history_business_boundaries -v`：15短例调用实际业务判断，JPM完整来源既有9.249s核对复用，不重读。两个模块的夹具都随各自PR提交，不需恢复虚拟机。两PR一起接收的selector/CI冲突使用#28固定补丁，现有c318725a组合及[联合验证记录](https://github.com/wlvh/SEC_metrics/blob/c318725aad605b1ba37c6cf9e1be0b19bce4338b/docs/evidence/issue47_h1_h2_combination_20261009/README.md)实际30短例/66导入文件检查通过；不重复建立runner或审查包。

首批接收范围保持：PR71酒店保存来源历史；PR58引用机械分类；PR62业务反例。后续PR75—79/83等不并入。公共默认新任务/在线安装问题由#28按同一保存HTTP输入复现与修复，本方按返回增量验证历史消费者，未审PR83不解除首批阻塞。PR71仅需接收PR67实际公共候选，不再顺序合入已经包含的PR59。修订、主体变化、其他历史指标、在线发现/补齐和D02公司模型链仍未完成；这些限制不取消完整五年责任。技术可审查与合并授权分开，全部保持Draft，没有Ready/合并/正式采纳/部署/active操作。

## 实际公司入口

```bash
python tools/vnext_company.py run --company marriott_international \
  --source-root /absolute/saved-source-root \
  --work-dir /absolute/company-state --output-dir /absolute/company-output \
  --metric B10 --metric B11 --period fiscal-years \
  --fiscal-year-start 2024 --fiscal-year-end 2025
python tools/vnext_company.py results --company marriott_international \
  --state-root /absolute/company-state --output-root /absolute/daily-export
```

来源包只含已保存原件、headers、请求日志及公司登记，不含规则、代码或答案。公司命令自动选择所请求年份，使用 PR59 共用计算，再由公共接口保存和导出 CSV/证据。它不会自行发现或补齐历史来源；缺失年份有具体失败分类。首次接收范围为未修订 B10/B11，修订保留在选择记录中并明确报告 `IMPLEMENTATION_GAP`，不偷偷替换成原申报。其他历史族仍使用 PR52 原入口，本增量不会给它们制造当前结果或改变旧 Run。

Marriott FY2024/FY2025 实际结果为 B10 69.8%/69.3%、B11 128.23/128.8 USD，期间各为 1月1日至12月31日。保存来源后，生产 case 工厂首跑 16.538秒，复跑 2.342秒且工厂禁止计算仍成功。独立进程读取 0.919秒；32个结果/指针文件保持不变。旧任务独立读取 0.935秒，42个旧文件保持不变。见 [production-cli.json](production-cli.json)、[独立进程复现脚本](check_production_company.py)及对应 stdout/stderr；没有复制来源树或程序树。耗时包含公司命令、检查和出口，不将它写成单独表格计算耗时。

## 公共状态的历史表现与新发现的读口缺口

此前58项状态/分派/公司测试 6.482秒全部通过，命令及结果在 [shared-state-and-dispatch-final.log](shared-state-and-dispatch-final.log)。新增5项历史状态及6项分派小例；其余复用公共测试，不另建 runner。早先默认 macOS 临时路径的四项失败是夹具 `/var` 与 `/private/var` 键不一致，原日志保留；公共方 `7944bc96` 修复后在默认路径通过，没有放宽业务断言。

- 不同年份的同指标各自保存、读取；成功同输入复跑 factory=0。
- 稳定扣留由 `completed-check.json` 记录，复跑为 `PREVIOUS_INPUT_WITHHELD`、factory=0、不新增同结果目录。
- 同年成功变成当前扣留时，公共 `current-result.json` 仍保留最后成功，而当前公司 CSV/日常读取采用最新已完成扣留，值为空；旧成功不代替当前结论。
- 新来源/补齐依赖及相关配置变化重新处理一次；同输入再次执行不再计算。
- 缺失年份及局部指标失败保留其他期间和指标；小状态恢复无需重新计算。

真实 Marriott 来源上的扣留是明确标记的 `CONSTRUCTED_CONTROL_BUSINESS_WITHHELD` 测试替身，**不是财报结论**。它通过公共 Calculator 的扣留结果、公共保存器、公司 CLI 和日常 CSV 验证上述行为。见 [company-consumer.json](company-consumer.json)；成功和扣留重复分别2.220/2.268秒、factory=0，读取0.809秒。首次构造控制误读了 Result 中不存在的 `scope` 字段，失败保存在 `initial-control-error/`；改为使用实际 Trace target 后完成。该错误属于测试控制，不被写成业务来源错误。

新增一项“同年成功→扣留→仅运行其他指标→日常读取”的构造反例在公共7944失败：公共读口回到最后成功pointer，忽略该坐标completed-check，实际显示100/PUBLISHED而应null/WITHHELD。见 [subset-withheld-read.log](subset-withheld-read.log) 及 `test_completed_withheld_survives_read_after_another_metric_subset`。#28唯一实现者在8805777d修复，本方a00480df接收；不写第二控制器。此前失败保留。**本接收矩阵现已通过：61项6.398秒**，见 [shared-state-after-8805777d.log](shared-state-after-8805777d.log)。公共读口逐坐标优先completed记录，检查其声明与Result publication一致；不会改变requested标记或跨财年分组。

还在既有真实Marriott来源/保存结果上，显式构造“后续仅请求B11/FY2025”的latest-execution控制，独立进程读到B10/FY2024仍WITHHELD/null且requested=False，其他三个值保持，读取0.859秒；禁止来源选择和update仍通过，56个结果/pointer文件不变，测试执行元数据随后还原。见 [saved-source-subset-read-verification.json](saved-source-subset-read-verification.json)。扣留和子集执行都是测试控制，未改原财报结论；没有重新计算真实来源。

当期模式使用同一原公共分派，新增参数不会改变默认期间。已完成两年B01、酒店原文及全帧核对直接复用；未重新联网或重新调模型。

## 三份既有交付与边界

| PR | 本轮审查对象与依赖 | 剩余边界 |
|---|---|---|
| PR58 `f321e554` | main目标仍只有引用合同、保存回答夹具、15项测试及简短说明四文件；旧8份失败/4份合同通过含义、原请求保持。代码可独立审查；公共快测基础由PR61/T1接收。 | 当前main CI快测仅两个旧 NormalAnnualInput 单例30秒超时，参考/兼容及公司作业成功，材料作业取消；未记全绿。main没有历史D02公司消费者，不能宣称公司法律内容全部修复。 |
| PR59 `9ae16dab` | 已选来源/期间共用读取和 Calculator 成立，PR67已消费其核心 `a0685346`；本方指定年份case实际进入该同一函数。 | 独立旧大CI仍有祖先字节门和旧状态断言失败；本组合受影响消费者通过不等于PR59独立CI全绿，也不要求先删除所有旧包装。 |
| PR62 `139a6d60` | 15项银行、非自然年、主体/事件和模型材料短例已交公共T1；独立测试增量，无自己的CI平台。 | 主快测、参考及兼容/公司作业成功，材料取消，不能写成所有检查成功；内容正例不等于全部旧答案正确。 |

精确当前 PR 状态保存在 [pr-status.json](pr-status.json)。公共共享测试/CI由#28负责；本方没有重签旧祖先或更改业务失败预期。PR52继续保留全部历史实现、原件、响应和失败，本接收不关闭它。PR69/70输入方法研究在本批暂停扩展；JPM FY2024参考虽已冻结，独立试验尚未启动。8192开发配置不等于非默认 DeepSeek执行通过。

Paramount可见表头起日2025-08-07与原生context2025-08-08冲突必须同时保留。PR67已有公共具名冲突修复；本次历史接收只支持B10/B11，没有接收旧历史B01/B03适配，不会以“日期已确认、仅年度长度不适用”接受该收入来源。未重跑全部Paramount历史。

## EX-99 单独处置

[ex99-status.json](ex99-status.json)记录 `NOT_CALLED`：1547行账本和SHA未变，加224保守计数累计1771/1867；没有1548次申领、没有新GET或UNKNOWN。指定附件的最多一次/零重试原批准保持。

原拒绝是后续 extension 替换了广义范围，而 capture 没有把另行获批的单URL范围传给准入判断。最小修复 `22c851e1` 已提交历史两分支；八项离线预检0.023秒通过，包括错URL/公司/用途/日期/重试/次数拒绝及真实capture函数的HTTP前边界。修复不恢复旧广义范围，不消费其他余额。

当前旧完整运行链仍在HTTP前被 `ISSUE_47_OFFLINE_WIRING_EVIDENCE_CHANGED:scripts/vnext/historical_event_sources.py` 拦截。这是旧运行字节门，**不是附件用途未经批准**。本批未重新铸造旧回执或扩大恢复协议，未改在途机制或新建账本；附件未取回，不授E01内容结论，也不阻断本份离线公司接收。

所有本轮新增SEC/provider/paid调用均0。来源发现/补齐、完整五年业务接受、其他未成熟指标、合并、Ready、正式采纳、部署和active切换均不在这份已完成交付声明内。

2026-10-08接收公共CI增量a4a568b1：仅workflow与说明/诊断变化，无生产或测试源码变化，复用本记录61项和真实历史消费者结果。六个旧完整native创建/安装作业退出当前候选必过集合，原测试/原runtime保留，原失败不改成PASS。有限诊断确认20项测试中16个错误均先被issue_28_v11祖先源码字节守卫阻断，其后业务没有到达；不是六条业务链通过。C04现检查来源/申报/CIK/比较前期/事件完整性，公共实际26项7.768秒、零skip。计数/停止、恢复/真实混合、原件材料及旧保存版本读取继续保留；不补称当前默认在线安装、C04/D04/剩余指标已接入。详见[公共逐项诊断](../../issue28_company_records_20261007/diagnose-retained-ci-01efa3d/conclusion.md)。PR58/62/70自身已有CI终态按各自head保留，这份公共候选范围调整不把其旧结果改为全绿；新公共37676590569终态另核。

后续已核公共a4运行37676590569最终CANCELLED：历史对象作业全历史取码约385秒，34项测试187.808秒全部通过及scalability/egress/reference检查通过后，达到原10分钟作业截止；取消不改称失败或整体成功。已接公共adee3036最小取码修复：候选depth1，仅显式fetch baseline_manifest声明的旧提交完整对象，再读取其实际active对象。34 selectors、原命令、10分钟期限与业务生产源码保持；本方6项取码范围回归通过，原61项和实际历史消费者结果复用。新的37678715800现已实际核为SUCCESS，七个作业全部通过；详见[新公共CI终态及取码耗时](public-adee-ci-terminal.json)。这里不证明全部旧运行或新在线安装。

后续接收公共c56e6335（原67自身CI全部SUCCESS），形成可取得组合d68b2d4d：公共增量为旧独立ordinary journal的只读引用及CLI识别；同一ordinary controller/writer/reader、历史公司分派和酒店producer与原ac6910逐字节相同。仅对新CLI组合做旧保存Marriott任务的独立读取0.968秒，选源/计算/业务网络禁止，42个结果和指针不变，仍导出FY2024/25的69.8/128.23与69.3/128.8。不重算本记录既有H4、酒店全帧或B01。[组合检查](c56-combination-verification.json)不借作旧journal计算族或新模型接受。
