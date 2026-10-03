# 第三次同范围独立复核：本轮已报告作用域阻断修复通过

范围延续前两次：989c564以后D04疑虑断言的分句/条件/原因/时间/否定/缓解归属，以及本轮新增测试。未实施受测代码。前两次报告和失败结果保持原字节；本次只说明新函数版本的有限复核。不是用户本人审阅、全PR批准、计数模块审阅或真实路线解禁，不覆盖6e5 D03及旧受限Codex任务。

## 实际执行

- 独立运行`probe.py`：原ChatGPT三例及前两次独立审阅五条原因/关系/分词修饰例，共8例。每例保持同一合法合成来源、相同引用，只改变分类。
- 全部8例正确当前标签经完整仓库`validate_response`及`build_acceptance`通过，生成正确原生Candidate/Evidence/Review/Result；错误排除标签在这三层及最终公共未披露投影全部拒绝。机器输出在`result.json`，已逐项断言核对。
- 独立运行原有`D04NativeProtocolTest`与`D04NativeTextRecordsTest`，17个测试方法通过，0.282秒。包含明确当前、真条件、历史与当前并存、否定、已缓解/预计缓解、普通活动延续、主体及未决保留等对照；日志为`matrix-tests.log`。
- `controls.py`单独重验两种已发现条件作用域：if内部and协调前提、前置if之后and协调后果。两者都正确接受条件标签、拒绝当前标签，unresolved为空。
- 同一有限控制检查历史reporting verb+now的嵌套评估及跨分号条件作用域未证明：两种标签均保留`D04_SOURCE_RELATION_IMPLEMENTATION_UNSUPPORTED`，`build_acceptance`都实际拒绝为`D04_SOURCE_ASSESSMENT_UNRESOLVED`，没有直接采纳模型分类。见`controls.json`。

## 发现状态

第一次及第二次报告中的四个具体作用域问题均已在所绑定函数下复验修复。此次没有发现新的阻断；停止扩展语言样例，避免将本轮定向修复扩大为任意英文语法工程。有限语法之外仍可能存在未支持关系，必须沿具体未决/开发责任处理，不能把本复核当成任意表述的语义正确性保证。

## 执行与版本边界

`reviewed-functions.json`保存所审六函数完整文本/哈希，探针开始结束一致；`controls.json`再次记录相关函数哈希。核心版本如下：

- `_assertion_clauses`: d3072159422cde14dad764981bc961b22fbddfce8b425e48c54f3ca316274d5a
- `_assertion_scope`: bf8885df05b557924a0c29211c4315473f7e5af5c718dedacb3d9412c06e9fa4
- `_assessment_time_prefix`: 9d5abe1cb32b5bfd32001675dd573aa2c50a2409dccc67d22a33c63fcb460998
- `source_statement_relations`: e45e856face02be3749d4df6a04870b66fe3dfe2778712302eea4d31ce52c495
- `check_source_classifications`: 0fcd40e229f1e8829dae0fdfbc7cab759fbdf25722ba9ec7e896ad7cca0edb7e

`reviewed-tests.json`另存当时测试文件及新增测试方法哈希。阅读了磁盘Run新增方法的设计，但**本次未执行完整磁盘Run方法**；实施者尚需在计数/共享改动固定、当前执行绑定同步后完成该测试。之前的绑定失败日志不是通过证据。本次原生结果/投影使用合法合成工厂与登记替身，不能赋予真实来源获取、真实收据、完整公司D04或生产信用。

真实调用0/0/0；无代码改动、账本修改、独立调用批准或发布动作。
