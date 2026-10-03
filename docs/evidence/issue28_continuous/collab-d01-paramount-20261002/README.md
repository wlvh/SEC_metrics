# Paramount FY2025 D01：一个标题在 U.S. 的句点处被截断

固定读取的 #47 登记 `1f3f446c` 报告本公司风险标题中 `U.S.` 两个句点未加粗，导致“前导强调文本”在第一个句点前停止。`audit.py` 没有复用对方 Result：它从 #28 的已保存同主体 10-K/A、正常私有 D01 Run 与保留 390 对照自行核对来源、时间及 Result 身份。

本方 `ITEM_1A` 原块292的全文以 **“Failures to comply with or changes in U.S. or foreign laws or regulations …”** 开始；保存候选的 `LEADING_EMPHASIS` 却只有 **“Failures to comply with or changes in U”**，并且这条残缺标题进入本方38条 D01 Result。原始资产、截短 span 和 Result 的哈希／原文对应，原解析器重建相同的错误前缀。这个精确 Result `sha256:a7a52ae7…` 既是保留 390 索引的身份，也是当前禁网正常更新所读的身份。它不满足当前 `catalog/r6/D01_risk_factor_headings.md` 所要求的原文标题级摘要，因此只撤回 `paramount_skydance_paramount_global|D01|2025-12-31` 此坐标的当前可信信用。旧 Run、Result、390 分母及其他 D01 坐标不改。

这不是“风险已经发生”的判断，也不是全部标题的独立完整内容审阅。对方已有一个只跨越 **1–2 个未强调标点、随后强调恢复** 的限定修复，并量测其它保存申报；本方尚未接入或验证该修复，不能把 #47 的新 Result 算作本方已修好。`audit.json` 保存原件、候选、Evidence、Result及旧索引的精确关系，`audit.log` 保存实际执行；本次无新来源／模型请求，原账本和来源日志字节未变，也没有操作 #47 工作树或生产入口。
