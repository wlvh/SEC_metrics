# 7d903ba 限定差异独立审阅结论

结论：发现 1 项 P1 阻断，当前补丁不能作为完整 B13 来源引用接线已完成的依据。未发现本次限定差异将旧失败升级成功的证据。本报告只计限定差异独立审阅，不是全 PR 批准、真实调用解禁、语义正确性认证或生产许可。

受审 SHA：`7d903ba27a5586569029349e6433f85a0f0054da`；父提交：`0e2d9a8969fda1ae79b6598029f259336a5c115c`。审阅日期：2026-09-22。开始时 HEAD 与受审 SHA 一致，源码未修改。实时只读获取了 Issue #28；本任务仍遵守更窄的审阅授权。

## P1：来源索引并非全部为文档内唯一，正常补充 XML 单元导致新合同无法构造

定位：`scripts/vnext/capacity_reference_contract.py:26-30`，通过该文件第 44 行以及 `continuous_semantic_calls.py:352-355` 触发。

新 `_owners()` 把 `(kind, source_index)` 当成整个请求内唯一键。但依赖 `r6_semantic_review._source_items()` 第 72 行对 `NATIVE_SUPPLEMENTS` 使用 `enumerate(unit.payload.objects)`：每个独立来源单元都从 0 开始。`r6_semantic_source.py:94-119,169-173` 正常按大小拆分这些对象，所以同一文档的两个合法补充 XML 单元自然会同时有 `('NATIVE_SUPPLEMENT', 0)`，并不表示原文有错误或来源归属未证明。

独立小反例已实际执行：一个可见正文单元加两个不同补充 XML 单元，旧嵌套请求的原生 `build_acceptance` 返回 PASS；同一合法来源传入新 `upgrade_request` 即抛出 `B13_REFERENCE_AMBIGUOUS_SOURCE`。完整输出见 `adversarial-tests.log`。这证明是新引用表示不能表达现有合法来源，不应归类为披露不足。当前新增测试只用 VISIBLE_TEXT 构造正例，人工复制该类单元的歧义负例没有覆盖补充 XML 的合法局部索引。

实际影响已有执行端材料佐证：本次 `offline-material-corrected.log` 在第一家 Enphase 的 `select_native_request_variants(..., source_references=True)` 中因同一原因退出。选择器先升级全部原请求，单个补充单元组失败即使整个选择停止，无法交付完整六请求及后续 Run。我没有重跑或改动执行端完整材料脚本，该日志是执行端证据；上述小反例由本审阅者独立运行。另独立只读检查原 109 的完整 source.json，确有 12 个 NATIVE_SUPPLEMENTS 单元，各自包含索引 0；这项清点本身不冒充当前完整分组执行。

修复应为新合同保留足够的来源身份，例如程序生成并严格重建的引用映射；所有引用必须仍能还原到唯一原单元和原索引。不能删除碰撞检查、猜测 owner、丢弃补充单元或改写旧请求/响应来获得 PASS。需要补一个合法多补充单元正例及对应错归属负例，然后重新完成受影响的完整离线接线。

## 独立完成的检查

- 指定命令实际通过：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts /tmp/sec_metrics_ci_20260922_venv/bin/python -m unittest -v tests.vnext.test_capacity_reference_contract tests.vnext.test_native_unit_index tests.vnext.test_native_request_variants`。16 项、0 失败、0 跳过，0.163 秒；见 `unit-tests.log`。包含未知引用、类型错误、跨单元、重复、漏答、未审阅、协议篡改、旧嵌套失败以及请求版本重建。
- 对原 109 实际保存请求、source.json 和 assistant-output.bin 调用当前 `validate_response`，仍拒绝 `B13_REFERENCE_OUTSIDE_SUPPLIED_SOURCE`；请求、来源、响应和 terminal 四文件前后 SHA256 一致，见 `adversarial-tests.log`。没有对原响应重新分配引用或赋予成功信用。
- 静态跟踪了新请求还原、`SemanticRequest.validate`、选择器成功重放、原生 Candidate/Evidence、assessment 版本字段、注册读取和文本/数量 Run 的请求重建链。新版本经 `native_request_variants` 保留；默认 BASE/INDEXED 行为及成功后按原始收据重验的限制仍在。没有把这些静态结果或合成测试写成当前完整 Run 通过。
- 当前 V14 snapshot、execution authority 和 semantic rule bindings 实际校验通过。baseline JSON 的大量移动属于键排序：实际仅增加新合同文件及更新相关文件绑定，没有额外删除或改写旧绑定。Requirement closure 为 `sha256:8c0afdaf0d147532700bfa029c0c7a2ee8ec39ff565b7981cff7d2d0ae4794bf`；见 `binding-check.log`。独立检查脚本首次导入函数路径错误，原失败保留，改正为已有 requirement_profile 的函数后通过；不是仓库实现错误。

## 未验证与停点

配置指向的新 `offline-wiring.json` 在检查时不存在；结合完整材料失败，尚不具备完整后继接线收据。未验证新模型实际输出、真实请求成功、Ford 全组、当前完整 B13 Run、注册冷读及最终 390 坐标。本次没有运行完整材料脚本、长期演练、真实 provider/paid/SEC 请求、生产操作或凭据读取；新增业务调用 0/0/0。没有修改源码、commit、push、触碰 #47/PR52、生成压缩包或 MANIFEST。

审阅范围为指定五个实现文件（capacity_reference_contract、capacity_semantic_review、native_unit_index、continuous_semantic_calls、capacity_native_assessment，以及其必要依赖）、指定测试、config/issue28_continuous_calls_v1.json 与 requirements/issue_28_v14 的父子差异；必要依赖只读。另读取指定原 109 与本次证据入口。其他并发任务的 execution-state 和材料改动未触碰。

工具计数：本子任务共 16 次 functions.exec 编排调用；内部实际 27 次叶子工具调用（25 次 exec_command，2 次 write_stdin）；若编排和叶子均计，共 43 次，低于 80 次上限。包含本报告落盘及最终 HEAD 核验调用；未使用子代理。用户可见消息只有一次开工说明及一次最终报告。
