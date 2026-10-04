# Lumen FY2021 D02：保留标题拒绝，准备完整 Item 8 开发问题

正常历史入口仍拒绝 `HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE:['UNRESOLVED_INCORPORATED_CAPTION_NOTE_18']`。这次没有删除拒绝、修改原标题、添加同义词规则、接入手工选择或恢复旧失败信用。

原件 `lumn-20211231.htm`，accession `0000018926-22-000007`，来自原已提交 SEC 导出；SHA `d71a12108032256fd7ee6b95bd70b4cb4fb24e6652a57b3e8b8852651c81b7d4`。在既有私有克隆（真实 `.git` 目录）及它自己的已认证恢复输入根，正常 `tools/read_d02_excerpts.py --packet` 到达来源准入后再次以原标题错误拒绝，exit1。七个相关入口/读取器字节与本方当前代码相同，逐文件哈希及实际命令保留。linked worktree 上直接调用先被原信任日志门拒绝；两个失败分别保存，没有把前者误称为业务标题拒绝。

实际原因是原件自身两个命名不一致：

- B537 的 Item3 引用 “Pending Matters” 和 “Other Proceedings and Disputes”。
- Note18 的真实标题是 B2533 “Principal Proceedings” 和 B2558 “Other Proceedings, Disputes and Contingencies”。
- 同一附注后来还包含 B2564–2578 的 Right-of-Way / Purchase Commitments。把引用未找到当作“整份附注都纳入”，会误带这些没有索赔的合同购买安排。

`prepare_full_item8.py` 先用正常历史来源适配器认证原件，再读取原冻结来源准备及后继结构范围，保存原 `INCOMPLETE` 提案。它不调用必须通过该 gate 的 native candidate/Run。它对唯一 Item8 范围 **[900,2682)** 的 **1782 个原块全部提问**：包括短标题、数字格、页码与审计报告，未按关键词裁源。沿用 `D02_ITEM_8_LEGAL_REVIEW_V1` 的定义、系统提示、输出结构、原 20–300 字符连续引用合同及 4096 预留；关键词只产生 60 个必须明确判断的块，任何其余原块仍可以列入 `also_in_scope`。

这个问题的池子比正常 runtime pool 更完整，**并非正常 pool 的重建**。它没有解决 Item3 引用标题的对应关系，不可注册成正常 Run 的审阅，也没有保存 LIVE plan、授权或空账本。旧模型 35 次许可及八个失败回答都没有读取、修改、裁剪或重发。

最终完整请求 SHA `651008095806cc9be4782d17fb2ba18e221d232357f351ee08ef6ce3e712b181`，**66166 输入 + 4096 = 70262**，符合原 200000。首版助手误以为年报文字对象拥有 C02 的 `source_filing` 字段，在写 metadata 时失败；此前已写出的请求体保留原字节。改为该年报对象真实的 `source_reference` 后，完整来源准备再次通过，最终请求 SHA 与首版已写体相同。没有放宽任何正常校验。元数据中的已认证 SEC 信用来自既有获取与恢复，不是本次新增访问。

执行者参考的阅读方式也明确保留：FY2021 代理附录已完整阅读且明确未更新，Item8 的 **1452 个原文字块**与该已读附录逐字符串完全相等；其余 **330 个原块**在本次直接全文读。没有用相似度、大小写归一化或模型摘要冒充字面相同。随后直接读了全部 60 个必答块、B537 引用句和整个 Note18 B2528–2578。映射、未相等原块全文及此前完整阅读记录的 SHA 保留；这复用了执行者自己的原件阅读，不能称为新独立上下文或留出。

`bind_executor_reference.py` 的 34 个正向块来自上述执行者判断，不是生产关键词提取器。30 个在必答集合，另四个是 B2543 的事故背景、B2552/2554 的真实巴西税务索赔及损失敞口、B2556 的 Qui Tam 标题。原件的法院诉讼、调查、未决/已解决状态及损失计提政策保留；普通税务头寸计量、养老金会计结算、借款条款、法律费用政策及会计估计清单不按同一个词混收。特别是 Missouri / Peru / Brazil 的真实税务诉讼没有因含 tax 被排除。

新参考的连续引文只是从本次所读原件绑定，未从任何旧模型回答裁剪。原合同的字段、完整必答集合及逐字引用检查通过，证明参考结构能按原合同表达；**不证明独立模型能在输出限额内生成，也不证明正常源范围已解决**。完整表格和图片没有包含在这个问题中，其他媒介接受不授予。

`development-materials.tar.gz` 包含正常入口两个原失败、代码字节核对、来源准入/完整原文档/未决提案、完整请求与计量、首次助手失败/最终日志、阅读对应映射与 330 原块、执行者参考及绑定日志。逐成员字节与 SHA 见 `manifest.json`。原 SEC bytes 从已提交 export 恢复，包内不提供许可或私有信任日志。

重建问题需要在拥有原认证恢复日志的普通 `.git` 目录克隆中读取来源；相关代码哈希先按包内记录核对。示例：

```bash
work/issue47-venv/bin/python \
  docs/evidence/issue47_history/lumen-d02-caption-development-2026-10-05/prepare_full_item8.py \
  --code-root <固定代码的私有克隆> --source-root <该克隆认证的恢复输入根> \
  --company lumen_technologies --report-end 2021-12-31 --out <新的开发输出目录>
```

新 DeepSeek/paid/SEC `[0,0,0]`，新 Run/接受均0。下一项仍是完整源范围及媒介参考、独立精确输入方法验证和必要后继接线；不能把正常拒绝解释为来源未披露。
