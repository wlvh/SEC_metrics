# PR41：分组归属提示修订与两轮真实验证

**本次两轮隔离连续更新已完成。PR41保持Draft，实际正式active未变。** 相同受审实现、提示、模型和一次阶段许可下，FY2024生成S1，FY2025真实接续S1生成S2；没有逐年度改代码、重写政策、开PR、人工填入数值或定位。两份材料仍是已知历史材料，申报可见性为明确模拟，本结果不是未见材料资格或真实生产跨年度更新。

## 实际改变

`config/annual_continuity_request.json`将选择顺序和从属关系加入真实任务提示：先找目标业务分组，再选地区和指标/年度列；数值归属于同标签列最近的前置分组标题，直到下一标题之前；后置标题不能证明前一行数值的范围。提示明确分组标题可以是`header=false`，同地区/同数值的其他分组仍是竞争项。

提示在`table_task_contracts`任务工厂中按已重载、文件哈希匹配的当前Requirement选择，进入请求、任务身份、Run、发送前重建及封存重验。保留原catalog身份，仅改变system_prompt、system_prompt_hash、task_spec_semantic_hash；MetricSpec、完整输入、输出schema、Evidence接受条件、模型/采样/通道及发布机制未改。没有该绑定的旧v8仍按旧提示解释，未修改旧catalog、失败响应或历史包。

Schema3的阶段许可承接已关闭Schema2→Schema1的原生调用链：旧2/2/0，本轮最多2/2/0，整线4/4/0，SEC0、retry0、无修复名额。两个历史失败保持原状，没有借用其余量。

## 代码、请求与独立审阅

最终受审及两次真实执行提交：`d00b2e261fd3e48ae4efaf76fbae33090359c219`。

- 实现身份：`sha256:b91cb13afc0fc6cdb5abecf562e4f0ca78550effc47b60a9865a41f45a7a8ef1`。
- 测试身份：`sha256:f022f1ce4fc401e49fbc8c9c34cd2ff264dd52e96c55c760a59c59db9cf63106`。
- FY2024请求文件SHA：`383604ecd2737d35e88d2d8f9135b015e0e16095d85f5bdb04988717619945ea`，392500字节，完整67表。
- FY2025请求文件SHA：`35649a2438257d5c5723ce794b5093e1e5872f3835696d9970524e071dc9c1df`，398582字节，完整68表。

独立审阅者从原始HTML重新构建全部表，再经实际Reader/provider工厂逐字节比较新旧请求；表集、cells、定位、顺序、manifest、来源、schema及非messages参数保持不变。新指令不含公司、年度、正确数值、表号或行列答案。28项当前提示下的原生正反例通过，两份旧错组响应依然被拒绝；正确、同值错组、标题在下方、跨分组和错年等检查均保留。

`7f1d727`的定向离线测试真实生成原生成功候选、在既有success-reference文件替换故障点阻止继续发布，再准备并重验保存snapshot，通过（1项、825.471秒计时器）。该测试仅在外部HTTP边界回放保存的正确assistant内容，不是新模型成功。之后只将fast中的4项拆成独立入口并更新该工具文件绑定，形成d00；最终请求再次完整重建且字节与7f1一致，独立审阅者用d00冷重验保存snapshot通过。未重跑未变的整套长发布演练。

本地及[CI34497310237](https://github.com/wlvh/SEC_metrics/actions/runs/34497310237)44入口通过；4个新增方法在原日志中各实际运行1项。较早合并入口因30秒上限超时的CI保留，拆分不增加超时或放宽断言。

## 真实执行与内容

[阶段批准](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5621515016)与[委托说明](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5621515355)由Codex按用户明确委托，通过真实wlvh账户代登记并回读；不是用户亲手输入或新的人工代码审查。

阶段对象ID：`sha256:cd9ac81283f0d5934ef54c2d7ac11d696f606174cf0f8bf5d80d4edc79e20dce`。两轮均使用`deepseek-flash`，HTTP200、原生SUCCEEDED、retry0，无UNKNOWN。

| 年度 | B01原生结果 | B10原生结果及独立原文核对 | 实际usage |
|---|---|---|---|
| FY2024 | USD25100000000；CIK1048286，us-gaap:Revenues、年度、accession、单位和计算匹配Company Facts | 69.8%；原文row19 Systemwide标题管辖row28 Worldwide，Occupancy/2024列、%及全球脚注匹配 | input160154＋output807＝160961；cache1536＋158618 |
| FY2025 | USD26186000000；原始FY2025事实、主体、概念、年度、accession及计算匹配 | 69.3%；row18 Systemwide标题管辖row26 Worldwide，真实year/Occupancy表头、%及全球脚注匹配 | input162211＋output812＝163023；cache1920＋160291 |

表中数字和定位只用于**验收报告**，没有放入新增选择提示。独立审阅者用未改的新响应重新执行Reader/Evidence，与持久原生对象一致，并核对SYSTEM Review、Observation、Trace、Result及两Run重放。此前69.7错组失败和审阅中的转义解释更正仍按原记录保留。

本轮新增 **2/2/0**，旧两个失败阶段 **2/2/0**，连续更新验证线累计 **4/4/0**。PR38原累计2/2/0独立保留，未转用。新阶段许可与期限不授予实际生产根权限。

## 完整版本链与边界

- S0：`publication_f6755af0dbd96895197dfccc1299a55bc9b74e53ea7722088ec98dab48cdb317`，明确标记的真实FY2023历史起点。
- S1：`publication_8f8584e265cf88ed256c6efbcf3bdd77c131b75dcb816686a9838502d363d4b9`，FY2024；manifest文件SHA`50bb89eb46307a397830ac00e814773a9b054102a263f25164883b97c905e074`。
- S2：`publication_029248ff2572cf913627ed1462fa772e29ca97edebc1f42e8413609986f921f1`，FY2025，明确以前述S1为前驱。

三包文件大小和SHA均核对。每轮240坐标＝2更新＋238继承、327公开行；每轮325未选公开行及未选证据与前驱逐项、顺序完全一致，期间不重标，B03不误选。publications的对象ID与manifest文件字节SHA分别记录。

实际正式active仍是`publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`。它原本已有FY2025结果，本次只推进隔离环境，不把它描述为发现新的FY2025或正式更新成功。

## 交付停点

重复输入已返回NO_CHANGE，本阶段累计仍2/2/0；新进程S1/S2冷读通过，无pending intent。阶段已关闭，关闭后的执行核对明确拒绝CONTINUITY_STAGE_CLOSED，触发器TRIGGER_DISABLED；旧两阶段8201文件、原seed及实际正式包/兼容副本字节保护通过。记录见`live/`与`checks/`。PR41不自动合并，main与历史分支不推进，不启用长期生产任务，不进入R5。完整运行现场留在执行端，精简审核包只保留代码增量、不可替代原件、独立审阅、调用账、关键日志、版本摘要及逐文件索引。

本次支持了“分组关系说明改善两份已知完整输入上的正确选择”这一有界结论，不构成未来任意布局或未见年报的总体可靠性认证。可信结果、正常自动更新、39指标统一生产和旧生产/补数路径退出仍是项目终点；本轮完成后集中审核，不继续扩展Marriott异常能力。
