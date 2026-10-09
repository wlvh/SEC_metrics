# B03 概念 URI 修后限定复核：2bbd769

范围仅为 `7bb17621c45545449f9dce390a41f39ec4bd0208` → `2bbd76945b20c1739c4878715f3de03973cd4b21` 的增量；原 [NEEDS_FIX](conclusion.md) 仍记录初版真实审阅结果，不改签。**本次结论：PASS_WITH_BOUNDS**，此前报告的所选折旧／无形资产摊销概念 URI 误接受已由最小差异关闭；未发现这段修补的新阻断。

`_selected_original_facts()` 现在对当前期间、同一主体、无维度的每项所选原文事实，额外核对解析得到的概念 URI 为 FASB US-GAAP 年份 URI、本地名称与所选概念一致。它不再只信 `us-gaap:` 文本前缀。新增回归在真实 Marriott 主 HTML 的当前折旧事实中局部重绑定该前缀到 `https://example.invalid/not-us-gaap`，并同步隔离来源哈希，要求 `B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NAMESPACE_MISMATCH:depreciation`；未修改的真实原件正例仍验证145/313百万美元及收入减项关系。指定完整测试类我独立执行，3项通过。

V14只更新被修模块的执行文件身份；当前执行权限、语义规则绑定及三份禁网接线收据，我独立调用验证器均通过，修后闭包 `sha256:e3f0eabc5ed50b7b5ecd79b7c407927ef888383d6983dc16619c38a863288b1d`。V13 manifest、`normal_run_v3.py` 及 B03 正常更新控制器相对此增量未变。

修后私有演练的 `exercise-repair.json` 记录模块 SHA `acc01df28a45c56c89d0c9c280487434b25efd0ac0ee60d8f659ce25a2b8429f` 与当前文件相符，V14 manifest SHA 也相符；禁网 B03 `CANDIDATE_READY`，值及 Result ID 保持不变，零真实调用。`cold-repair.json` 对应同一 Result/值、原生 Run ID及当前来源关系，选择依据 `NATIVE_PUBLISHED_RESULT`，监视文件字节未变、无正式采纳。运行脚本、JSON及日志已核对；我没有重跑私有完整更新、异进程冷读或 fast 全套，因此这些是执行方的修后执行证据，不是本次独立重跑的长链。

此结论只关闭上述 URI 差异。原用户选择的1.35亿美元合同取得成本收入减项、另有未量化履约成本摊销的解释边界，沿原审阅和证据保持；本次不重新判断业务口径，不授正式采纳、完整390或生产信用。没有模型／SEC请求、提交、推送或 #47/PR52 工作。命令与精确范围见 `followup-2bbd769.log`。
