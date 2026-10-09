# 当前 B03 数值消费者最后一次限定增量复核

结论：**限定增量复核通过，未发现新增阻断项。** 精确对象为 `c56e63354271d9c674bf18bb56856e420ce334cc → f78d7e60e24924c62f78f493e18578ea702713e6`。当前 B03 原件检查已消费先前复核通过的数值表示边界；原错误标签、未声明逗号写法与 nil 不再被错误确认为当前 B03 输入。该结论不授生产、全 B03、完整 D&A 或整 PR67 信用。

## 对象、实质变化与覆盖

- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-fast-feedback/SEC_metrics`；开始及报告时均核对 HEAD 为 `f78d7e60e24924c62f78f493e18578ea702713e6`。
- 只复核 `reported_monetary_literal.py` 的辅助提取、`ordinary_b03_input_scope.py` 数值消费、`ordinary_current_update.py` B03 依赖声明及指定测试。复用原 e349/af660 数值审阅，不重开旧恢复、整 PR67 或指标家族。
- 新 helper 不读取文件；policy 由消费者显式传入。标签/命名空间、nil、已支持数值写法、XML 与 inline 属性边界和正常正规化顺序，与原数值修复保持。
- 当前消费者保留原主体、实际期间、官方概念命名空间、USD、无维度总量筛选和精度比较。无关主体/期间/币种/分部事实不会作为当前总量冲突。
- 对已选范围内的异常数值，保留正常 source_facts，返回 `WITHHOLD / B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN`，why 为 `SOURCE_NUMERIC_VALUES_UNRESOLVED`，附事实 ordinal/concept 和具名原因；nil 不当作零。
- 实际检查 B03 配置含新 helper、数值/上下文 policy 以及其既存 shared normalizer 依赖。改变新 helper 的内容会改变 B03 处理身份；B01 不新增该 helper 依赖。既有公共文件的依赖范围不作为本次重设计对象。

## 独立测试结果

1. 指定小测试命令独立重跑：`CurrentDaScopeTest` 与 `CurrentProcessingConfigurationTest` 共 **16 项通过，0.058 秒，exit 0**，日志为 `current-consumer-small-independent.log`。包含原误接受反例、合法 transform、nil 证据保留、主体/期间/单位/维度/命名空间筛选、原精度/组合行为及 B03/B01 新 helper 依赖隔离。
2. 为确认新接线没有误拒实际当前组合和拒绝路线，独立运行获准的 `CurrentB03SourceOnlyTest`：**5 项通过，5.038 秒，exit 0**，日志为 `current-consumer-real-independent.log`。测试只从仓库保存来源复制到临时 source-only 根，计算/读取临时结果；没有访问业务网络或修改来源现场。
3. 另做 **10 项有限内存实验，全部符合预期**，日志为 `current-consumer-probes.log`：plain 小数/正负号、inline scale/sign、固定零的原合法行为仍 KEEP；不受支持 transform namespace 具名 WITHHOLD；其他主体的异常写法不污染本主体；本主体异常写法保留正常事实并 WITHHOLD；提取 helper 的普通 XML 小数分支保持。最后一项仅检查 helper，不声称为当前 B03 增加 XML 选源路线。

实际 source-only 测试核对：Marriott 当前折旧 145m + 摊销 313m = 458m，保留既有 135m 收入扣减排除关系，B03 ratio 仍为 `0.1756281982738868097456656229`；Salesforce B03 仍按范围冲突具名扣留，其 B01 仍为 `41525000000`。这些是限定离线测试行为，不是生产采纳或全量指标验收。

## 输入证据与限制

阅读所给 numeric-source-scope README、before.log、small-final.log、real-after.log、company-after.json。before.log 中两项真实 API 负例在修改前返回 KEEP、断言失败；本阶段在精确提交上独立运行的相应测试已返回 WITHHOLD。company-after.json 的首次/重复 CLI、禁止重复工厂、结果字节未变等内容仅作为提交证据阅读，本阶段没有另跑 CLI 或核对外部账本 SHA。

原跨页完整段落、全部 D&A 范围、正式结果验收及生产权限边界保持。没有新指标家族或公式改变。此次不重做旧完整来源审阅、不重跑 fast 长材料、不审整 PR67，也不把有限输入 KEEP 当完整业务范围证明。原失败结论和前两次报告均保留。

## 累计资源与执行记录

- 原任务起点：2026-10-08T15:39:05Z；本阶段首次 clock：2026-10-08T16:39:00Z；报告 clock：2026-10-08 16:44:01 UTC；原绝对截止 17:09:05Z 未重置。
- 本阶段工具 **20 次**（7 次 functions.exec 外层、13 次嵌套工具）；此前 60 次，累计 **80/80**。本报告写入后立即停止调用工具；已到硬上限。
- 普通过程消息 0、问题 0；本次最终报告 1，累计普通消息 **3/3**。
- 授权范围已完成，没有因资源上限留下本次必须核验项。未核的整 PR/完整 D&A/生产/外部账本均在委托范围之外。
- 只新增原指定 `independent/` 内本报告和 3 份日志；不覆盖原失败，不打包，不开发/commit/push/spawn，不发业务请求，不修改来源或对方现场。
