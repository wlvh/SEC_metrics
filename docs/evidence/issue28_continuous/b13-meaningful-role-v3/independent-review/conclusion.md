# B13 V3 限定差异独立审阅

Verdict：PASS_LIMITED_OFFLINE_DIFF。在指定差异及本次允许的验证范围内，未发现新增阻断项。该结论只支持 V3 作为离线请求表达候选继续研究，不批准真实申领、全 PR、完整 B13 结果或生产切换。

受审 SHA：`78779bf34ccae4ea076f391e790c264f6eebd964`。基线：`ec311e2d8829ec6f7dd3440713a454aebe6b50ba`。日期：2026-09-23。实际工作区 HEAD 为 `ed1634c5b4acb4c3c0e97b782ce8b0bc62f00bfd`，五个受审文件的当前字节均与受审 SHA 相同；目标至当前 HEAD 的 scripts/catalog/config/requirements/tests 差异为空。因此本次短测试覆盖受审实现，不能把当前工作区 HEAD 写成受审 SHA。文件身份与三处实现的 V14 绑定核对见 `identity-and-bindings.log`。

## 检查结论

1. **类别映射与原定义一致。** 新 ROLE_LABELS 的九个角色逐一映射原九类，无数值产量/产能类别被重新开放。`_compact_protocol` 核对原 kind 集合，V3 只把类别数字替换为显式字符串；主体、期间编码继续沿用原 codebooks。原 category_definitions、system_prompt、program_quantity_contract 均保留。新增“融资/股权等计划不是物理产能、成本分摊设施利用率不是产品容量”的说明与对应原类别边界一致，不构成计算口径变更。定位：capacity_reference_contract.py:13-24、192-211。

2. **完整来源与必评集合没有被新协议删除。** upgrade_request 对 base 做深拷贝，只变更 response_protocol 和新合同身份；还原再按原 policy 重建 base，并与重新构造的新请求做全对象相等检查。原 units、来源字典、必评项和原数量合同继续进入 capacity_semantic_review；该验证器仍要求 required 集合被 accounted 覆盖。V3 提示只允许省略“无关且非必评”块的 finding，所有单元仍必须返回 reviewed 状态。定位：capacity_reference_contract.py:60-100、104-118；必要依赖 capacity_semantic_review.py:251-259、332-338。本次独立短测的 V3 必评相等断言使用空必评集合，不能单独证明实际六组非空集合；实际六组材料只读取执行端摘要，未冒称亲自重跑。

3. **旧版本默认与历史读取路径保留。** 新 role_labels/semantic_role_labels 默认 False，V1/V2 分支继续按原选项构造；重建入口增加显式 ROLE_VERSION 分派，不把旧请求自动转换成 V3。restore_base_request 必须匹配请求哈希和原基线，旧版只进入其原分支。选择器仍先重放已有 SUCCEEDED 请求，当前语义复验失败会抛错，没有回退为新的 V3 替代请求；失败终态也不能满足成功复用。定位：continuous_semantic_calls.py:351-395、401-432；native_unit_index.py:112-143；必要依赖 native_assessment_replay.py:118-154。未直接重新验证 111/170 的真实原包或旧账本终态。

4. **已覆盖的重复与错误类别仍拒绝。** V3 未知标签或数字 kind 被严格拒绝；physical_capacity_context 正例还原为 CAPACITY_QUALITATIVE。同一来源误写 planned_physical_capacity/product_or_installed_capacity 会产生 unresolved；原 build_acceptance 第 31-33 行据此阻止成功 Evidence。这与“解析器抛异常”不同，不能笼统声称所有错误类别都当场抛错。完全重复 finding 经原归属还原层拒绝。提示更清楚不等于已证明模型分类更准确；现有重复门检查的是完整规范化 finding 身份，未证明可以识别任意换措辞的语义重复。

5. **V3 真实申领前阻断位置正确。** `_execute_semantic` 第 666-670 行读取 metric 与合同版本，在 build_plan（689）、凭据检查（718-721）、账本 claim（726-729）和执行（736）之前拒绝 live V3。新增单元测试只提供最小 prepared/request_bytes 和 ledger.live=True，准确取得 B13_ROLE_V3_LIVE_VALIDATION_NOT_AUTHORIZED，证明该路径不需要先完成其余执行字段或申领。记录模式仍可走原原生验收链。新摘要或离线接线收据不能自行解除这一硬阻断。

## 独立执行与证据区分

只运行获准命令：
`PYTHONPATH=scripts:. /tmp/sec_metrics_ci_20260922_venv/bin/python -m unittest tests.vnext.test_capacity_reference_contract tests.vnext.test_native_unit_index -q`

结果为 17 项通过、0 失败、0 跳过，0.121 秒；见 `unit-tests.log`。读取了实际测试断言、上述实现及必要调用依赖。除此之外只做静态源码和文件字节/绑定核对，没有追加测试命令。

`offline-candidate-summary.json`、`role-short-wiring-summary.json`、`final-wiring-validation.json` 和 README 是执行端材料：其中实际六组、token 计数、原 170 机械换标签仍拒绝、原 111 当前 unresolved、禁网 opener/controller 录制桥接及收据校验，均未由本审阅者重跑。其报告已明确不授模型准确率或完整公司结果信用，本结论不将这些记录转成独立执行证明。

## 未验证边界与资源

未运行大材料、完整公司/Run/冷读、真实请求或长期测试；没有读取凭据、操作账本、改业务代码、commit/push、触碰 #47/PR52、生成压缩包或启动其他代理。未复核外部 ec311e2d P2 结案材料的全部事实，未审阅本任务五个文件以外的代码改动。所有新增文件仅在本 independent-review 目录。

本次新增工具调用 12 次：4 次 functions.exec 编排、8 次 exec_command 叶子调用；加此前 51 次，累计 63 次，低于 80 次上限。本次只发一份最终报告，无问题或进度消息。
