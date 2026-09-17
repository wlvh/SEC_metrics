# 5207290213修复差异独立审阅：发现阻断，首次修复未完成

审阅者为独立工程子任务，未实施受测D04修复。范围仅989c564之后的疑虑关系分句/修饰语归属差异、相应测试，以及本轮before/after复现材料。不是用户本人审阅、全PR批准或真实路线解禁；不覆盖6e5 D03、计数/分组增量、共享来源/账本、真实模型或生产。

本次直接导入完整仓库的`request_for`、`response_for`、`validate_response`，使用合法合成来源、固定2025、相同引用只改变分类；通过既有`text_arguments`继续调用真实`build_acceptance`、Candidate/Evidence/Review/Result及公共行投影。结果见`result.json`，不是转录隔离函数。工厂替代了真实来源/登记及调用收据，因此未执行完整来源准入、完整磁盘Run或生产误发布。

## P1：原因/关系从句中的历史日期仍抹去当前疑虑

以下三种语法都明确说过去亏损现在引发疑虑，日期应属于亏损事件：

1. `In 2024 we incurred losses that now raise substantial doubt about our ability to continue as a going concern.`
2. `Because we incurred losses in 2024, these conditions now raise substantial doubt about our ability to continue as a going concern.`
3. `The losses that arose in 2024 now raise substantial doubt about our ability to continue as a going concern.`

实际三例均：正确DOUBT_DISCLOSED/CURRENT_REPORT拒绝；错误HISTORICAL_STATEMENT/HISTORICAL接受，unresolved=[]、current_target_findings=[]；`build_acceptance`返回PASS；原生文字Result形成`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`、value=None；公共投影实际返回“未披露持续经营疑虑”。只修and/but/分号边界未覆盖日期修饰不同事实的关系。此为可重复错误接受，不是合法披露缺失或单纯保守未决。

## P1：分句新增边界丢失前置条件的共同作用域

额外完整仓库探针：`If financing fails, cash is insufficient and these conditions raise substantial doubt about our ability to continue as a going concern.`

`_assertion_clauses`把and these之后切成独立断言，丢失共同前置条件。实际DOUBT_DISCLOSED/CURRENT_REPORT被接受且unresolved=[]，CONDITIONAL_OR_BOILERPLATE/CONDITIONAL被拒绝。此例仅验证到validate_response；未把其错误当前状态升级成已经执行的最终Run结果。需要保留前置条件对其协调谓语的范围，或在范围未证明时标记实现不支持，不能从被切掉的上下文断定当前。

## 已观察到的有效进展与测试边界

原审阅的even-if、for-example及and-these三个反例已有针对性修复，并新添成功/错误排除及公共行测试；关系类新例揭示上述仍未覆盖的真实风险。新增磁盘Run方法源码显式替代来源准备/准入/登记，在正确输入上创建结果和公共行，并检查改分类后的重放拒绝；这是合适的受影响链路测试设计，但当前`native-scope.log`实际因并行修改`continuous_semantic_calls.py`未同步执行绑定而失败，不能把该日志记为PASS。应在固定版本绑定后完成实际执行，保留首次失败。

## 版本绑定

`reviewed-functions.json`保存所审五函数的完整文本和SHA256，并在探针前后确认这些函数未变化；这样同文件并行的requests_from_source计数修改不冒充已审范围。

- `_assertion_clauses`: b2d8e8bb1fcf1bf9e4662927f03534f535921a202d38caf929420c495ae83a1f
- `_assertion_scope`: 8ba33cbae04a6f5bf7811f127ce79164ddc3ad9bdaae376d70957e2da31105bb
- `source_statement_relations`: f73fe2d4e98aa043a0e54a085270b71f2ae89f6dada3c7017f64d855d1af4772
- `check_source_classifications`: 0fcd40e229f1e8829dae0fdfbc7cab759fbdf25722ba9ec7e896ad7cca0edb7e
- `_specific_continuation_activity`（所依赖原函数，未变）: b02ea4a0d8783eea5e3d041d7fad7c62944025185ec1eac8dfa49182b0ed2b77

结论：**发现阻断，修复责任继续**。已回报实施者；不得只登记“独立审阅待办”。本次真实调用0/0/0，未改受测代码或旧审阅记录。后续同范围修后复核应保存新结果，不能改写本记录的首次错误。

补充：初次报告送达后，实施者已开始修改。随后重复条件例已正确拒绝当前标签、接受条件标签，见`conditional-repair-observation.json`及其新函数哈希；这是执行中观察，尚不替代整个新版本的同范围复核。
