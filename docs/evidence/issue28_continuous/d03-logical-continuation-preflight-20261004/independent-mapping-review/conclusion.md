# 限定独立增量审阅：PASS

精确补丁 `14f74c3e313180d6c4d4e5c48ecf499ca72d4dae`，基线 `f661962f7939e7eeaed92491e8ad74473215f782`，分支 `task/b06-new-source`。UTC 开始 `2026-10-04T15:44:00.229024+00:00`；结束 `2026-10-04T15:52:03.503590+00:00`。工具保守累计 **26**（8 次 functions.exec 包装、18 次内部 exec_command）；普通消息 3 条（开场、有限进度、最终），均在指定上限内。未发现阻断本离线输入映射交付的 P1/P2。

## 范围与身份

审阅指定七文件 task_mapping.py、mapping-prompt.txt、test_task_mapping.py、measure_mapping.py、replay_mapping.py、task-mapping.md、actual-task-mapping.json；全部工作区字节与精确补丁一致。沿用本目录 logical_source.py 和 independent-review/conclusion.md 的既有完整 XML 续链限定边界，按需核对既有 _source、共享 codec 和 context measurement 的调用行为。这些依赖相对基线未变，不重复旧语义、旧八位置合同、旧原答或完整续链审阅。

实时只读 Issue #28 正文（updatedAt 2026-10-04T15:08:54Z），确认第5.8节开发任务与最终目标模型验收的边界。本审阅是独立上下文子代理的源码/合同增量检查，不是独立人工、D03 语义批准、DeepSeek 验收或公司信用。

## 已核对的行为

- census 先用外部固定来源摘要和原 Source/Unit 身份检查完整输入；原始三元组只能使用精确整数位置与 VISIBLE_BLOCK / NATIVE_FACT / NATIVE_SUPPLEMENT。prepare 从原源重新构建 census，拒绝变更的映射；重复、缺失、bool/float 位置和单元种类冒充引用种类均被拒绝。每个原始来源项仅拥有一次责任，共享 context 不增加所有权。
- native_partial_views 无旧 unit_id，明确保留 parent_source_unit_id、original_indices 与原单元描述。还原后每个部分 payload 与原源完整 payload 保持一致，只有事实/外层 root 列表按原始索引选择；事实 wrapper、context、measurement-unit、namespace 字典、原始 XML 及其中表格/脚注均保留。可逆共享 codec 没有把片段升级为旧整单元。全部请求的完整可见文字和 quotation-context 标记逐项与原源一致；原 span/hash 保留在摘要绑定的 host Source，不伪造模型坐标。
- 实际五组 fact-footnote 关系的全部端点和27条完整续链/72物理段均进入相关任务的 context；每个相对 XML 子串与原 root 精确一致，完整 root 仍在输入中。关系依赖收敛至固定点，未拥有的 anchor 明确标记 anchor_is_owned=false。实际共享36次 native context 出现，没有重复所有权。内容同义/同事件跨来源去重仍是后续语义责任，本机制只证明输入责任划分。
- 分组只在完整责任 bundle 之间拆分；同一事实的完整链和所需 root/context 不因资源拆分被裁。完整 visible 责任无法容纳时全方法停止；native 责任不可再分且超限时保留停止项，拟执行公司计数为 null。150000 是分组余量，固定200000上下文上限和4096输出预留未提高。
- 原 prompt 明确发现必须引用至少一项拥有责任，context 不授重复责任；空 findings 不证明零，scan_complete 不证明公司/语义完成，会计期间不可替代调查事件日期。此处没有响应接收器或原生公司路线，因此这些要求尚未由新模型响应证明或获正式接受。

## 有限验证与真实保存材料

指定 5 个短测试退出0，测试时间0.034秒。只执行一次 replay_mapping.py：16个 Marriott 保存请求逐字重建、各自完整测量记录相等，3259项责任完整且唯一；重建阶段7.950秒，整子进程8.419秒。原源摘要 `5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b` 保持。

另执行23组有限断言，覆盖全部16份保存 wire 的原始部分/字典/完整文字/描述符/关系/链映射对照、源与映射篡改、引用类型、输出深复制和不可拆 native 资源停止。第一次反例脚本把原本空的 root_owner 替换为同样空字典，没有构造出篡改，因而断言失败；这属于审阅脚本错误，已改用不同的非空哨兵并重跑23组通过。第一次失败原因仍保存在 finite-controls-first-attempt.log，不算源码缺陷。

Marriott 精确覆盖1965 visible blocks、1229 facts、65 roots，共3259项/16请求；每个任务均含全 visible context，最大149722 context tokens（含4096输出预留），全部低于200000。JPM 保存报告为 STOP_SHARED_VISIBLE_CONTEXT_RESOURCE，整请求473727 context tokens、11146完整 visible 责任，零 executable requests，拟公司计数 null。文档对两样本的结果与代码/保存记录一致。本次未执行 measure_mapping.py、重新分组 JPM 或重算其旧342306估计；473727只核对已保存整请求记录及停止分支，未赋予 hosted usage 信用。

## 信用与未覆盖范围

PASS 仅覆盖这份新增离线输入映射、保存 wire 重建和有限资源合同，不授来源新获取、模型正确性、语义接受、公司 Result/Run、真实调用、CI或生产信用。模型能否正确执行分配后的任务、完整公司输出合并/引用校验、实际业务用途/机会/调用接线和通用新来源适用性仍需后续各自证据。

只写本 independent-mapping-review 目录的 conclusion.md 与日志。未改源码、原数据、原回答或账本，未 spawn、commit/push、打包、操作 #47/PR52 现场或做模型/SEC业务调用；新增业务调用 **0/0/0**。开始时已有的 execution-state.json 未提交改动属于父工作，不作为本审阅输入或信用。

日志：unit-tests.log、actual-source-replay.log、finite-controls.log、finite-controls-first-attempt.log；精确文件摘要、依赖未变检查、工具数与 UTC 起止见 scope.log。
