# 1457e99a 限定独立审阅

结论：**NEEDS_FIX（仅针对新跨页合并规则）**。Marriott 与 Paramount FY2025 的已保存来源正例、D01 默认分派和 V13/V14 当前执行绑定在本次限定检查中成立；但新规则能把没有分页证据的两个标题合成一条，因此暂不能把这份补丁认作一般新财报 D01 自动更新的无条件正确实现。这个问题不推翻上述两家公司已核对的来源增量，也不授予当前 390 坐标或生产采纳信用。

**[P2] 只有一个数字块也会触发跨页标题合并。** `scripts/vnext/d01_emphasis_source.py:215-218` 把任意 1–3 位数字块视作分页附属内容；`:254-259` 只要求中间至少有一个这类块，不要求注释所描述的“页码后接带链接的 Table of Contents”，也不验证实际翻页。独立反例将 Item 1A 内的 `<b>Regulatory Risks</b>`、普通数字块 `1`、`<b>other market risks</b>` 放在连续三个段落。程序给出 `headings_joined_across_a_page=[{first_block:3,second_block:5,furniture_blocks:[4]}]` 和唯一标题 `Regulatory Risks other market risks`，而这份输入没有目录链接或分页标记。结果会继续经过原有候选、Evidence 和 Review 重放，因为错误由来源选择器自身稳定生成。见 `page-join-counterexample.log`。建议至少把本次声称支持的页码＋链接目录行顺序作为合并条件，并增加“只有数字块”的拒绝反例；如果需要接受其他分页形式，应提供对应的来源结构证据。

跨页合并还把首、尾标题之间的整段原始字节记作一个 `raw_start_byte`–`raw_end_byte`，其中包含页码和目录行，而展示文本只拼接两个标题。哈希能证明该覆盖区域来自原件，不能证明展示文本是这一个连续原始片段的逐字摘录。现有 `TEXT_EXACT_EXCERPT` 名称与 `catalog/r6/D01_risk_factor_headings.md` 的原文标题合同应据此限定解释；若跨页标题需要逐段精确定位，应保存两个原始片段。此点与上述误合并同属新跨页规则的来源语义边界。

本次亲自执行的核验：指定的 `tests.vnext.test_d01_emphasis_successor` 为 **4/4 OK**（`unittest.log`）；只读加载 V13/V14 后执行 `validate_execution_authority`、V14 `validate_semantic_rule_bindings` 和 `validate_wiring_receipt` 均通过，闭包分别为 `sha256:07704504…`、`sha256:499cc1d7…`（`binding.log`）。V12 冻结快照可加载且该提交未改其文件及 V12 分派代码（`frozen-v12-binding.log`）；没有重跑旧冻结 Run。对 Marriott/Paramount 的保存原件独立重建，默认包装器候选与冻结 `text_results` 候选相等；显式路径分别为 **34→38**（仅增四条原文下划线类别标题）与 **38→38**（将 `U` 截断标题替换为完整 `U.S.` 标题），新增主张的原始片段哈希逐一相符（`source-differential.log`）。原件追加字节和候选文本篡改的拒绝由上述四项测试覆盖。

已阅读提交内最终 Marriott/Paramount 私有普通更新及独立进程冷读记录：两者均记载首次 `CANDIDATE_READY`、重复输入 `NO_SOURCE_CONTENT_CHANGE`，结果身份分别为 `sha256:99c76e50…`、`sha256:6795449b…`，并明确 `current_390_credit=false`、`production_authorized=false`。这些是提交者保存的运行记录；本审阅未重跑大材料、fast145、完整私有更新、旧冻结 Run 或正式 390 汇入，也未发真实业务请求。fast145 的 `PASSED` 只按现有日志读取，不能替代对上述新反例的处理。三份接线收据中，本审阅亲自调用了 V14 `validate_wiring_receipt`；另外两份只检查其所载执行哈希与 V14 一致，不扩大为业务调用许可。

范围：只审 `1457e99a5a00d390d58183ddc3d244f2ab1f82af` 指定新差异及其现有证据；未改源码、未 commit/push、未操作 #47/PR52。`tool_calls=26`（直接工具调用；含 72 次嵌套调用），`message_count=2`（开工告知及最终报告）。
