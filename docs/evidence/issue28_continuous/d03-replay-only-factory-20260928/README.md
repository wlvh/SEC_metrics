# D03完整后继请求进入当前受控工厂，执行仍关闭

已知实现缺口：`d03_native_preparation.prepare_native_input()`能从完整保存来源选择有效请求，但旧`source_statement_facts`组的逐候选后继只存在于普通字典里；`SemanticRequest.validate()`不承认它，因而不能进入现有请求身份/传输正文检查。此增量新增**显式**`prepare_d03_replay_only_requests()`：由原`prepare_requests(..., metric_id='D03', reference_context=True)`重建全部原单元及原请求，仅对确有旧来源事实的组用已有限定审阅的`candidate_request()`构造后继；37个不需替换的JPMorgan组保留原请求，唯一后继组保留原请求ID作前驱并更换有效请求ID。返回对象标`replay_only=True`；初版仅凭这个可复制字段阻止执行的主张被独审推翻，最终在控制器里按请求合同本身拒绝，见下节。原`prepare_requests`函数体及默认参数不改。

`SemanticRequest.validate()`只在请求不属于原完整请求集、且带`source_fact_review_contract`时增加受限核对：必须是D03，前驱必须是当前来源中唯一确有旧事实的原请求，并由当前已认证来源重新生成**逐项相同**的后继请求。请求单元、程序必评集合、完整响应协议及发送正文仍由原工厂核对；只改一个前驱ID就拒绝。没有对任意旧失败开放自动替代，也没有改变B13/D04默认选择或真实调用授权。

`red.log`记录新正向入口在实现前不存在。固定最终树的`targeted.log`/`.exit`对真实保存JPMorgan年报及修订来源运行1项/168.866秒通过：完整38组单元顺序不丢，恰好1组后继，后继当前工厂身份检查通过，错误前驱拒绝，`execute_feasibility()`在申领前以`CONTINUOUS_REPLAY_OBJECT_CANNOT_EXECUTE`拒绝。`short-negative.log`复用旧后继不得丢单元/必评的短反例，1项通过。`fast.log`/`.exit`为当前六文件哈希`fast-tree-before.json`下单作业 **135/135 selector、201.743秒、本地通过**；它不代替新head远端CI。没有重跑先前812秒/507秒的JPM录制整包与冷读。

首次提交`23243375`只对`continuous_semantic_calls.py`更新未冻结V14绑定，`binding-before.json`/`binding-after.json`及`binding.log`当时通过，闭包为`sha256:2731935de44d0f123a76f301a1744cc9fb7f83a08e4e89f44f654004207c4168`；独审后来指出这份成功记录没有覆盖实际调用的`regulatory_fact_review.py`。V13历史包不重签；旧请求、原响应及计数不改。D03仍无真实请求许可、Candidate/Evidence、Review/Result/Run或完整公司结论，不能把本次回放专用对象或旧合成未决包升级为成功。

## 首次限定审阅后的执行禁令与绑定回修

精确`23243375`的[独审原结论](independent-review/conclusion.md)为`NEEDS_FIX`：调用者可用`dataclasses.replace`清掉`replay_only`进入录制申领；实际生成后继请求的`regulatory_fact_review.py`不在V14执行闭包，最初的接线PASS不覆盖它。本次回修在 `_execute_semantic()` 的申领前按请求内`source_fact_review_contract`强制拒绝执行，不再只信可改写对象标志；错误类型的合同字段也以显式拒绝码返回。真实JPM保存来源的修后`followup-targeted.log`/`.exit`为1项/188.363秒通过，包含复制对象、隔离录制账本**0/0/0未申领**、错误前驱及非字典合同拒绝。

执行绑定方面，`SEMANTIC_RULE_PATHS`现在要求`regulatory_fact_review.py`哈希，当前V14 `execution_authority.files`也新增该模块。第一次尝试把它加进`new_rule_files`，在`followup-binding-first-failure.log`被已批准策略的精确`rule_paths`集合检查拒绝；该失败保留。最终只在执行文件集合加入依赖，`new_rule_files`、`config/issue28_continuous_calls_v1.json`、V13父级及旧授权字节不变。`followup-binding.log`核验当前V14、语义文件和三份离线接线，闭包`sha256:9563d906e54e5f5cdd9e1dda138c5db49db204cb69de6f4eac680b6f5169a4f1`。固定六文件哈希`followup-fast-tree-before.json`下，本地单作业fast **135/135 selector、200.057秒通过**。它仍不替代新head远端CI。

真实账本仍为195槽、provider/paid/SEC **143/143/52**，本轮新调用0/0/0；V13与历史包不改签，#47分支与运行根未操作。精确`1d017b8f`的[限定增量复审](independent-review/conclusion.md)为`PASS_WITH_BOUNDS`，仅确认上述控制器禁令、显式错误和当前执行/语义绑定；首轮`NEEDS_FIX`原结论保留，两轮累计70次底层工具调用。下一阶段要接D03原生正向路径，仍须证明实际执行身份、完整跨组语义、有效Review及公司Result/Run；这项回修没有授予这些信用。
