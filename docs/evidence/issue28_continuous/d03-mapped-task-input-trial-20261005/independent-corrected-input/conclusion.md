# 限定盲态 corrected input 试读结论

按唯一输入中的两条消息完成本次离线抽取。原始第一份 JSON 答案已直接一次性写入 `response.log`，之后不调整。答案保留三条税务机关检查陈述：截至 2025 年末，2022 及以前税年的 IRS 问题已全部结清；2023、2024 税年 IRS 审计仍在进行；若干外国、州和地方所得税申报仍在检查中。披露没有说明这些检查属于指控违法的执法调查，答案没有作此升级。所有发现均引用本次 owned reference。

- 委托指定补丁 SHA：`851ca976eede74b849e2e8ad088d5df452d63f3e`。因盲态限制，没有读取 Git 或源码验证此提交；这里仅登记委托绑定。
- 唯一输入：`/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-mapped-task-input-trial-20261005/corrected-request.json`。
- 实测输入 SHA256：`48adcf767a8d6f63208a79e4ad015f4653a30bc3bde3ae3d7125256a7da54c69`，与委托一致；505,355 bytes。
- 原答 SHA256：`cee06e09745ae78179c36716bc32cba5418f83eec2a061b4c0aed62090ccf670`。
- 起始 UTC：`2026-10-05T11:51:02.188717+00:00`；结束 UTC：`2026-10-05T11:59:09.509873+00:00`。
- 工具保守合计：54 次，即 27 次 `functions.exec` wrapper 加 27 次嵌套 `exec_command`；没有其他工具调用。普通消息含最终报告共 3 条，问题 0 条。未触及 80 次、90 分钟上限。
- 实际 hosted token usage、内部推理 token、账单与实际服务端用量均为 `UNKNOWN`。输入信封写有 `model=deepseek-flash`，只是待交付请求配置；本次没有调用该 provider，也不据此声称实际执行模型是 DeepSeek。

完整读取范围：system 消息 2,838 字符全文；user 消息 479,493 字符经标准库 JSON 解码后完整读取其提供的数据及元数据。可见文本全部 1,965 块，按 `[unit_position, block_index, text, html_quotation_context]` 恢复，块号 0–1964、unit positions 0–4；对应 `visible-context-decoded.log` 的 [0,348918) 字符完整顺序读取。原生 facts 共 64 条：unit position 7 的原 ordinal 449–507 及 509–513，使用 `row_layout.columns`、`fact_columns` 解码，沿 `source_order` 完整读取，没有把 row 位置当原 ordinal。五个负责的 continuation roots 为 [12,NATIVE_SUPPLEMENT,0–3] 及 [13,NATIVE_SUPPLEMENT,0]，含 f-444-1、f-470-1、f-497-1→f-497-2→f-497-3，以及 f-497-2 内嵌的 f-408-2；完整根、表格、嵌套文本与上下文都被保留和解码。`native-decoded.log` 的 [0,97403) 字符全文已读取。

shared 字典全文已读取：20 个 context、6 个 measurement unit、1 个 namespace environment、59 个 exact style entries；包括 unit position 8 仅带 c-88/c-89 的 dictionary-context-only partial view。所有原生 root 的 namespace、context、unit 和 data-b13-style-ref 均能按精确 key 解码，无缺失 key；恢复后的五个 root XML 摘要均与输入内给定摘要一致。17 个 original unit descriptors、完整 original document metadata、69 个 owned references、69 个 native context references、三条完整 chain path 及全部其余字段已读取；对应 `input-metadata-decoded.log` 的 [0,39741) 字符全文。request envelope 的全部字段也已读取并记入 `decoding-structure.log`。

早期结构总览出现一次工具输出截断，并对部分 payload 作了显式预览；这些都未当作完成证明。随后使用上述互相连续的字符范围恢复全部可见语义数据、原生内容及元数据，范围记录见 `reading-coverage.log`。原 XML 经标准库解析；显示的是完整文本、表格单元顺序和 inline 属性，未逐字展示重复排版 markup。未解码及未读的已提供语义内容：无。未提供的完整父 native units、外部原件与实际 SEC 获取凭证未读取、未重新验证，原始 source_sha256 与 provenance 声明仅按输入保留；这不影响对这 69 个 owned references 的 scan_complete，但不能扩成全公司原件完整性或真实性证明。

语义判断由开发模型依据完整阅读完成，没有使用关键词搜索代替阅读。IRS 的税年与财报 context 是所报告的期间，不是调查开始或结案日期；所有 event_dates 保持空数组。现金缴税和有效税率表中的国家、州名称不能给未明确归属的审查赋予机关或地域。上下文中的 EPA 和 Starwood/FTC 等事项没有对应本次 owned reference，未冒充本次负责范围的发现。未阅读 Spec，因此本试读不声称三条税务检查已满足任何仓库业务口径或验收条件。

必要日志包括原生 roots 原样日志及 exact style 恢复后的五个 XML 日志，均仅由指定输入生成。没有读取仓库源码、Spec、父参考、其他答案、旧输入或外部原件；没有 spawn、网络、provider、SEC、长测试、commit/push、账本操作或 #47/PR52 操作。本次仅完成独立开发输入试读，不提供 DeepSeek 真实验收、业务语义批准、正式采纳或生产信用。
