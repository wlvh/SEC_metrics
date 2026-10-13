# 检查版本不触发未变业务重算：comparison helper

在完成 Macy’s D04 公司链后，发现只合入E01的比较辅助代码也使D04失去复用条件。用原17文件任务的本方独立副本、真实D04 producer/Calculator code guard在 actualmain d661验证，报告 `INPUT_OR_EXECUTION_FAILED: UNCHANGED_D04_PROCESSING_FORBIDDEN`。这是构造的禁止处理控制，证明它尝试重算；不是新模型或财报语义失败。原Source/账本/回答/成功结果不改。

实际配置差异只有 controller 和 `ordinary_update_compatibility.py`。controller本来已经从业务比较剔除，触发项为比较helper；它不选来源、不解释或计算指标，且 D04 根本不走其E01转换。旧版本仍保存在原配置，不能把“文件变了”一律等同于该指标业务输入变了。

最小修补沿已有 `_same_processing_configuration` 的 checking 集合，将该helper与 controller/request_bindings 一样只记录检查版本。每次复用仍走当前Source检查/读取/坐标及已知缺陷检查；producer/parser/Calculator/Spec/prompt、实体/期间/注册关系、实际来源及处理输入全部比较。真实业务版本改变必须处理。原configuration/Result/旧程序标记不改签；返回原 `source_check_versions` 映射保两旧key并加comparison helper当前版本，便于排错。

小状态回归先红：仅helper版本变化会进入factory。修后119控制/8.681s/零失败错误skip：未变输入复用同id，current source检查仍执行；仅Calculator版本变化仍正常产生新结果。复用原Source/不同坐标/恢复/失败/未决及E01范围负例，不重整家公司。

实际Macy’s原副本修后正式CLI **0.348s**（精确值见actual-after.json），返回 `PREVIOUS_INPUT_WITHHELD`、同a2a0…D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE，真实处理函数被禁止仍未调用。结果层9个文件保持（原成功7文件加保留的前红失败2文件）；额外结果读取不写state，FY2025起2025-02-02末2026-01-31、TEXT_QUAL/null保持。此处额外read为同进程CLI边界，跨进程读取复用此前 [Macy’s主记录](https://github.com/wlvh/SEC_metrics/blob/6feda9962bf7eb94aafc3843da7691a95ec15320/docs/evidence/issue28_macys_d04_company_20261013/README.md) 的独立进程验证，未冒称又执行一次新进程。

原before控制失败保留，修后使用同副本自然恢复，没有删failed check或手工修改pointer。只本方测试副本新增检查，不动原Macy’s成功task。首次提取配置差异脚本未设PYTHONPATH而import失败，随后按真实配置重新读取；它不是业务执行失败，也不以import错误授通过。配置差异和实际生产字节见相应JSON，实测d661加明确工作树差异，最终SHA不伪称已重跑。

新增SEC/provider/paid0/0/0。只是少一次无意义完整D04重建，不能因此宣称财报健康、模型遗漏已证明或390完成。无Ready/合并/正式采纳/部署/active；按现有接收处理。与source-material skip worker PR252无代码重叠，不混入其审查范围。
