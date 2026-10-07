# 历史消费者接收：2026-10-08

本轮唯一主验证记录为 [verification.json](verification.json)。能力结构检查通过（6.868秒），检查器两个副产物按检查前字节恢复；这只证明结构对齐。实际 main 仍为 `8588ccbb`；这里是分支交付，尚未入 main，也不是完整五年业务接受。

可取得的组合是 PR67 的公共候选 `7944bc96` 加本分支 `task/issue47-history-consumers`。后者只增加现有历史期间选择、酒店 case 适配及同一公司 CLI 分派。公共控制器、保存器、投影、状态恢复和测试运行器全部来自 PR67。PR59 的已选来源共用计算已经包含在 PR67，不需要再次顺序合入 PR59。现有 `historical_dei` 旧命名空间包装作为必要上游依赖保留，没有将删除所有旧包装作为接收前置。

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

Marriott FY2024/FY2025 实际结果为 B10 69.8%/69.3%、B11 128.23/128.8 USD，期间各为 1月1日至12月31日。保存来源后，生产 case 工厂首跑 16.538秒，复跑 2.342秒且工厂禁止计算仍成功。独立进程读取 0.919秒；32个结果/指针文件保持不变。旧任务独立读取 0.935秒，42个旧文件保持不变。见 [production-cli.json](production-cli.json) 及对应 stdout/stderr；没有复制来源树或程序树。耗时包含公司命令、检查和出口，不将它写成单独表格计算耗时。

## 公共状态的历史表现

58项状态/分派/公司测试 6.482秒全部通过，命令及结果在 [shared-state-and-dispatch-final.log](shared-state-and-dispatch-final.log)。新增5项历史状态及6项分派小例；其余复用公共测试，不另建 runner。早先默认 macOS 临时路径的四项失败是夹具 `/var` 与 `/private/var` 键不一致，原日志保留；公共方 `7944bc96` 修复后在默认路径通过，没有放宽业务断言。

- 不同年份的同指标各自保存、读取；成功同输入复跑 factory=0。
- 稳定扣留由 `completed-check.json` 记录，复跑为 `PREVIOUS_INPUT_WITHHELD`、factory=0、不新增同结果目录。
- 同年成功变成当前扣留时，公共 `current-result.json` 仍保留最后成功，而当前公司 CSV/日常读取采用最新已完成扣留，值为空；旧成功不代替当前结论。
- 新来源/补齐依赖及相关配置变化重新处理一次；同输入再次执行不再计算。
- 缺失年份及局部指标失败保留其他期间和指标；小状态恢复无需重新计算。

真实 Marriott 来源上的扣留是明确标记的 `CONSTRUCTED_CONTROL_BUSINESS_WITHHELD` 测试替身，**不是财报结论**。它通过公共 Calculator 的扣留结果、公共保存器、公司 CLI 和日常 CSV 验证上述行为。见 [company-consumer.json](company-consumer.json)；成功和扣留重复分别2.220/2.268秒、factory=0，读取0.809秒。首次构造控制误读了 Result 中不存在的 `scope` 字段，失败保存在 `initial-control-error/`；改为使用实际 Trace target 后完成。该错误属于测试控制，不被写成业务来源错误。

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
