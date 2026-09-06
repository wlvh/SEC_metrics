# R4 标签修复：正式版本接线

Owner 已批准同一已验证单元格的 raw_text/text 精确接受规则。
当前修复使用 issue_28_v3；正常 acceptance、Run freeze 和磁盘 replay
从记录绑定的 Requirement 选择相同规则，不由模型、CLI 参数或环境变量选择。
caption、来源/几何、数值、单位、期间、scope、跨表及歧义规则不变。

- 失败 finalizer 仍只删除原非法 error_class 字段；通用 schema 不扩大。
- 新规则从来源恢复 raw_text，不修改模型原始响应和 Candidate。
- 请求明确携带规则并同步字段说明；acceptance 使用 v2 语义身份。
- v2 的原请求和证书目录保持原样，历史记录仍使用 exact-raw。
- 新证书只生成到 docs/r4_v3/qualified_cases，未重新获取 SEC 来源。

版本绑定沿用五文件 Requirement、Decision、transfer 和 engine registry。
V4 是保留 V1–V3 后增加的单项标签政策扩展，不是通用版本框架。
719 个父政策片段不变。Owner 的当前任务原话按聊天来源保存；记录中的时间
是观察/捕获时间，不是虚构的 GitHub 发布时间，也不是激活或调用授权收据。

正常路径回归只使用一个新请求的 recorded fixture，通过实际控制器
acceptance、成功收尾、FROZEN 和新进程独立 replay；没有 Checker 开关、
版本校验绕过或把 Python 换回旧版本。新请求与旧请求哈希不同；历史付费
响应单独保留为 OFFLINE_REGRESSION，不伪装成新请求的实际响应。
发布侧只核对新 Requirement/ReleasePlan/Spec 身份读取，不执行 stage/publish。

本目录 candidate_review.json、validation.json 和原日志保留上一轮
离线候选 eaead91 的历史证据；它们不表示当前 source head 已通过。
本轮正常接线、复跑范围和最终身份见 bound_execution_validation.json。

当前 source revision 的 policy-content 已批准，exact-head transition
activation 仍需既有流程。PR32 集中提供最终 head/tree/closure；在完成
激活/合并后，由既有 CLI 创建新 live plan 和精确授权文本。
拟保持九个 base 加三个 stability，retry=0、reuse=false、SEC=false、
publication=false；旧计划和授权不沿用。历史失败一次保留，active 仍为 R3。
WB-7/R5/R6/Rf 未加入此次修复。
