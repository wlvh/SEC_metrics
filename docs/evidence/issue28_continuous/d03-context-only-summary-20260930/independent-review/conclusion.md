# D03 公司级上下文汇总：限定独立审阅

**结论：PASS_WITH_BOUNDS。** 审阅对象为补丁 `2e687740b202f6713f7e92e88034b3176dd413cc`，父提交 `43d0445f8f2a326a73ac0f50f359a49e5e9d657e`。代码结论只覆盖 `scripts/vnext/d03_complete_interpretation.py`、`tests/vnext/test_d03_complete_interpretation.py`、`tools/run_fast_tests_v2.py` 的增量；未发现该增量错误授予 D03 公司结果或执行信用。

补丁先按原有路径重建完整来源和有效请求，再逐组调用 `validate_response()` 或 `validate_candidate_response()`。新增汇总只从**已验证的原响应** `provider_response.units[].context_only_source_indices` 提取 `(unit_id, source_index)`；仅对同组、同单元、单一原文引用、`OTHER_MEANING` 且 `NOT_AN_ACTION_STATEMENT` 的派生背景 finding 忽略其占位 `UNRESOLVED` 主体/期间。V6 逐请求验证器先核对引用属于该单元的原文，并拒绝显式 finding 与 context-only 索引重叠；因此同一索引上的显式 finding 不能借该例外被排除。`row.unresolved`、`kind=UNRESOLVED` 以及其他主体或期间未知的 finding 继续进入 `unresolved_group_indices`。现有显式 `OTHER_MEANING` 且主体/期间为 `UNRESOLVED` 的路径也继续阻断；补丁没有改写原先对主体与期间均已确定的显式 `OTHER_MEANING` 的处理口径。

返回的 `group_rows` 字段、`proposed_current_findings`、分支名称与录制桥接入口保持原结构；本补丁仅改变上述假未决场景的分支和随之改变的 `proposal_id`。空提案仍为 `ABSENCE_RULE_NOT_APPROVED`，不是“未披露”或“没有调查”。验证函数仍固定返回 `provider_execution_identity_verified=False`、`native_candidate_or_evidence_created=False`、`native_result_or_run_created=False`、`production_authorized=False`；录制桥接继续要求零调用并固定返回零调用、无 Result/Run 和无生产授权。搜索该 API 的调用点仅发现本模块的桥接与测试；没有新增原生 Result/Run 写入入口。

**独立执行：** 使用指定 Python 环境、`PYTHONPATH=.:scripts`，在补丁 SHA 工作树上运行两项指定测试，`2/2 OK`，耗时 23.613 秒；原始输出见 `targeted.log`。`git diff --check` 对三份受审文件通过。第一项检查空、合成当前 finding、原响应背景占位、显式 `OTHER_MEANING` 和未知主体；第二项使用 Marriott 已保存的来源构造五组合成背景答复，禁网络，验证无假未决、无结果信用，加入真实 `unit.unresolved` 后仍为未决。这些测试没有调用模型或 SEC。

**只读材料：** 读取了同目录的 `README.md`、`reproduce.py`、`reproduction.json`、`fast.json`、`fast.exit`、`fast.stderr`、`source-selector.json`，没有独立重跑 `reproduce.py` 或完整快测。执行方保存的 `fast.json`/`fast.exit` 报告 142/142 个快速 selector 通过、退出码 0；`source-selector.json` 报告新增保存来源 selector 1/1 通过。这些日志仅作旁证，不是本审阅亲跑的测试，也不证明真实模型会正确判定背景、十家公司 D03 完成、原生公司 Run、远端 CI 或生产采纳。

本审阅未改产品代码、账本、Issue 或其他证据；未执行真实请求，未操作 #47/PR52。结论不扩大为 D03 业务语义正确、真实调用许可、未披露结论或 Issue #28 完成。
