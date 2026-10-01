# Lumen FY2025 D02：共用缺陷的本方精确归属

在固定读取的 #47 登记 `1f3f446c` 中，`D02_LUMEN_2025_KEYWORD_PROXY_ADMITS_LEGAL_FEE_POLICY` 指出年报 Item 8 的原块 1670 只是外部法律顾问费用的会计政策，却因列出“litigation”而被当作诉讼披露。本方没有拿对方的 Result、Run 或验收身份来登记。

`audit.py` 直接从 #28 已保存的 Lumen FY2025 正常更新 Run 重读 Candidate、Evidence、Result、SourceReference 和 10-K 原始字节。原始资产、块 1670 的 byte span 和选中原文的 SHA-256 全部一致；它确实作为 `excerpt_1` 落在本方 **15 项** D02 摘录和 Result 全文中。本方精确 Result 是 `sha256:7e2d21f0…`、Run 是 `run:ordinary-integrated:82b8dbb8…`，并非 #47 的 41 项历史文本集合。保留的 390 索引与这次私有正常更新读取到**同一 Result ID**，见 `audit.json` 的两身份对照。原文只讲法律顾问为财务、监管、诉讼等事项提供咨询时如何费用化，不报告本公司某项诉讼、争议或索赔；现行 `catalog/r6/D02_legal_disclosures_v1.md` 的对象是诉讼来源披露。这个误纳足以使该集合不能获得当前 D02 内容信用。

因此仅扣留 `lumen_technologies|D02|2025-12-31` 这一坐标的上述精确 Result 身份；其他 14 项摘录没有在本次被宣告错误，其他公司的 D02 也不因指标相同而撤回。旧 Run、Result、原件及既有 390 分母不改写。`audit.json` 和 `audit.log` 是执行者定点原件核对，不冒充对本公司所有法律披露的独立完整审阅，也未形成修后新 Result。实际账本和来源日志前后哈希不变，真实 provider/paid/SEC 调用 0/0/0；#47 分支、工作树、运行根与权限未操作。
