# JPMorgan FY2025 A05 从当前保存来源完成私有普通更新

上一步跨Issue核对确认 #47 的JPMorgan FY2021同概念资产重述，不应直接撤回 #28 FY2025。为检查正常更新是否能从本方**当前累计**来源而非早期仓库自带旧元数据产生结果，`run.py`用现有 `current_processing_source()` 形成受当前 V14 闭包约束的处理副本，再从正常 `vnext_normal_update --process --company jpmorgan_chase --metric A05` 入口运行。整个过程禁网、禁DNS/HTTP，关闭116个旧语义生产导出；没有读取 #47 运行根或发真实调用。

首次执行在代码提交 `6e2c78b57df05d33c596ea7ecaaff2b0e51b429d`、处理来源快照 `sha256:a5dcc4af3d1eae0cd4af880a794a5deab6731772bf767c53b3d959a2cf519baa`、后继 Requirement 闭包 `sha256:3112b4766e47e2f59a36c8fae63e631fc7c6a3631b4e360ccbca11bafd920657` 下，109.839秒返回 `CANDIDATE_READY`。私有 Run 的 A05 新 Result `sha256:b4af4d3bb42610f98df83d72080b168a4ed4cf25baa9e9a692b6bf5b72e6b9d7` 为内部 `PUBLISHED/EXACT`、数值 `0.01353819078340816975991354239`。另一进程禁网重入在40.858秒返回 `NO_SOURCE_CONTENT_CHANGE`，仍指向该Result，未创建第二个Run；`cold.py`保存两个attempt的关联。`verify.py`进一步从盘上复核成功指针、私有公开行哈希和旧归档对象，旧`f8f2a182…` Result保持原身份，归档Git blob未变。新私有Run的`validation.json`仍为`NOT_RUN`，因此不是正式采纳或390更新。

历史归档的同一FY2025 A05 Result `sha256:f8f2a182897cd8ab4dd3f0ad16c399fc8ba259cc4c1706ff4db59e76ffd68639` 保持原身份；其数值相同，不把两个不同来源/闭包下的Result合并。`run.py`和`cold.py`分别比较了真实调用账本、累计来源日志和正式active指针的前后哈希，三者均未改变。受影响当前来源上的同概念重述核对、原始值与身份见相邻的`collab-a05-peer-recast-impact-20261002/`。这里证明的是一条当前保存来源 A05 私有正向更新及重复触发，不是新财年在线发现/获取、十家公司390坐标全面更新、A05完整独立内容验收或生产发布。

`audit_original_content.py`额外从该私有Run绑定的两份**原始10-K HTML**逐字节验哈希，用原生XBRL解析器单独读取无维度、同CIK、同期间、美元单位的原文数值：FY2025净利润57,048,000,000；FY2025期末资产4,424,900,000,000；FY2024期末资产在FY2024原报及FY2025比较栏均为4,002,814,000,000。由已批准的`average_denominator_ratio`直接计算为`0.01353819078340816975991354239`，与新Result完全一致。重复的原文事实在同一身份下无互异值。`original-content.json`保留原件身份、上下文与四个核对值。该核对由本会话执行，不冒充子代理独审，也没有扩张到全部财务事实或其他公司。

随后一次性[限定独立原件复核](independent-review/conclusion.md)未调用上述父会话脚本，而是按新Run的原始SourceReference重读两份10-K、可见财务行、XBRL主体/期间/单位与批准公式，结论`PASS_LIMITED_ORIGINAL_CONTENT`。它额外发现一个需要在解释时保持的差别：发行人年报自己显示ROA **1.29%**，本项目按获准的两期末平均资产公式为约**1.354%**；两者不能互称。当前私有`metrics_matrix.csv`的`formula`栏为空，而参考表A05说明有清楚公式；后续正常公开解释要用兼容的显示路径填明计算口径，不能为这一显示修正改签旧Result。审阅没有批准正式390或生产，审阅代理48工具、共3条普通消息，无真实调用。

第一次以裸 `nohup ... &` 发起的后台壳进程未保留会话，尚未建立处理目录，也没有输出或执行收据；随后采用持久会话内的 `nohup` 运行，`run.exit=0`和`run.log`是实际执行依据。不把首次空日志计作通过。
