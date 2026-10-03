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


## 58e85b1 增量独立复核：原 P1 在限定代码范围内关闭

受审 SHA：`58e85b1a7de7dded2a7befb9f3519f8d42a7b66d`；父 SHA：`7d903ba27a5586569029349e6433f85a0f0054da`。本次仅复核 `capacity_reference_contract.py`、对应测试和 V14 baseline 的增量，没有重开独立代理或扩大审阅范围。原报告及失败日志完整保留。

原 P1 修复成立：补充 XML 引用现在明确带 `source_unit_index`，以 `(kind, source_unit_index, source_index)` 在当前请求的原单元数组中定位；可见文本和原生 fact 仍使用其原文档索引。还原时先校验所属单元，再移除仅属于新传输协议的范围字段，交给原完整内容验证器；没有对旧嵌套响应自动移动引用。

我独立重建原 P1 的有效小反例，一个可见正文单元及两个各有局部索引 0 的补充 XML 单元。本次旧嵌套验收、新请求构造、新格式完整 `validate_response` 和原生 `build_acceptance` 均通过。分别引用两个补充单元时，核对了最终 `unit_id` 和恢复的原始 XML 字节，二者没有混用。该检查比新增仓库测试中的单纯格式还原更深入，但仍是合成来源的小范围验证。

对应错误归属边界实际执行 13 个反例：遗漏范围、布尔范围、负数或越界单元、把补充引用指向可见正文单元、负数或越界来源索引、错误 kind、单个 finding 混合两个所属单元、重复引用、重复 finding、未审阅及缺少单元，全部拒绝。状态行顺序调换后恢复结果字节一致。见 `supplement-repair-adversarial-tests.log`。

指定三模块命令重新独立运行：17 项通过、0 失败、0 跳过，0.195 秒；见 `supplement-repair-unit-tests.log`。执行端 `supplement-repair-tests.log` 已读取，但未以执行端测试替代本次独立执行。两处 V14 新文件绑定与实际文件 SHA256/8512 bytes 一致。复核及测试时 HEAD 与上述 SHA 一致。

结论为“原 P1 的实现及相应限定反例复核通过，未发现这三个文件增量中的新增阻断”，不撤销前版确实失败的事实。来源定位可靠不等于模型给出的业务分类正确；补充单元的选择仍是显式模型输出，程序只验证其范围和原始内容。没有重跑完整材料、Ford/Enphase 全请求、注册冷读或完整 Run，没有真实调用，不为尚未取得的完整离线接线收据或生产信用背书。是否完成下一阶段完整材料应另按实际新输出记录。

本次追加共 3 次 functions.exec、5 次 exec_command，即新增 8 次工具调用；同代理累计 19 次编排、32 次叶子工具调用，合计 51 次，未重置原限额。累计用户可见消息为 3 条（原开工说明、原最终报告、本次最终报告）。仅追加本结论和两份独立测试日志，源码、旧证据及其他工作区改动未触碰。
