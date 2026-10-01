# 91cfc9d5 定向独立审阅结论

审阅基线为 `4ac3e1cc3cd5dfb8774d6292116a5f175f16d6eb`，补丁为 `91cfc9d5b744ca8cd52eb78a62fb1e29706bd44f`。仅审阅委托列明的两个模块、两个测试、scalability 例外、V14 baseline manifest 和本目录证据；为核对接线，只读验证了三个现有 wiring receipt 的当前绑定。未发现此范围内阻断**录制版引用形状候选**的缺陷。此结论不授真实调用、B13 数值、完整公司结果或生产信用。

引用全集由还原后的原始 source units 经 `_owners` 枚举，B/F 为文档序号、S 为单位内序号。V2 要求它恰好分成 `candidate_refs`、`excluded_ref_ranges`、程序已核对的引用三组；沿用 V1 的全部单位、引用归属、必评引用、未决引用和 64 个候选上限检查，再拒绝区间越界、跨单位、重复、重叠及遗漏。现有单元测试覆盖缺口、候选重叠、伪造范围、非整数和请求变更；`exercise-current.json` 在原 191 组保存材料上记录 1276 个引用、四段合成排除区间及缺口/错归属/重叠反例。**排除是模型的分类提议，不是程序已证明无关**：把 1276 项全部排除也能通过结构检查，故不能从本检查推出模型读懂来源或不存在容量披露。代码明确返回 `model_relevance_proven=false`、`absence_established=false`、`native_credit=false`。

`scan_request` 的 V1 构造仍为默认；新请求需要显式的 `B13_COMPLETE_REFERENCE_COVERAGE_SCAN_V2`，来源比对、执行期校验和 Candidate/Evidence 建立均按版本分发。录制材料测试用实际保存的 Enphase 来源、合成响应、录制账本和独立磁盘回读，证明 V2 可以保存并重验；回读收据为 `B13_COVERAGE_SCAN_SHAPE_STAGE_V2`，无新 provider 执行。执行返回 `native_result_created=false` 和 `SCAN_SHAPE_ONLY_NO_B13_METRIC_CREDIT`。`execute_capacity_scan` 在进入申领流程前拒绝 live 账本，普通 B13 原生评估入口也拒绝 scan request。现有 `saved_scan_stage`、`interpretation_request` 与注册解释链仍只接受 V1；因此 V2 尚不能导出完整第二阶段 Result/Run。证据 README 已明确此停点，不能把 V2 录制成功提升为真实申领依据。

独立复算当前字节：`capacity_two_stage.py` 为 `df27e2f5…`/63065 字节，`continuous_semantic_calls.py` 为 `07763ef8…`/67268 字节，scalability 配置为 `4da4cbc8…`/2988 字节；均与 V14 执行绑定相符，两个模块还与 `new_rule_files` 相符。当前 V14 requirement closure 为 `sha256:c3964a1cea2611fab6e4aaab2e9ff574c34507c57411b13346df843bfb61aa1c`，execution authority 为 `sha256:9fe96d93b4caead6b943053adaf6279a0d98157afaa2b2e070cfb96d325ad926`。`validate_execution_authority`、`validate_semantic_rule_bindings`、`validate_wiring_receipt` 通过；三个现有 receipt 绑定到该 authority，V13 与父提交相同。核对输出在 `binding-check.log`。

本次实际运行指定短测：`PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_ordinary_scalability_audit`，26/26 通过，输出在 `focused-unit.log`。按委托只核读既有大材料 `material-all.log`（3/3）及 `fast-final.json`（142/142 selector，状态 PASSED），未重跑大材料，也未把这些录制/合成检查当作真实模型效果。未核验 191/192 原调用的服务端结果、完整解释阶段、十公司 B13 接续、390 坐标验收、真实新授权或本范围外 PR/历史；未触碰 #47/PR52。

工具调用计数：18 次 `functions.exec`（含首次 JavaScript 语法失败），其中发起 50 次内层工具调用；合计 68 次。普通对话消息 2 条进度告知加本次最终报告，无提问。未 commit、push 或另起代理。
