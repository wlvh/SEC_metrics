# D03完整后继请求进入当前受控工厂，执行仍关闭

已知实现缺口：`d03_native_preparation.prepare_native_input()`能从完整保存来源选择有效请求，但旧`source_statement_facts`组的逐候选后继只存在于普通字典里；`SemanticRequest.validate()`不承认它，因而不能进入现有请求身份/传输正文检查。此增量新增**显式**`prepare_d03_replay_only_requests()`：由原`prepare_requests(..., metric_id='D03', reference_context=True)`重建全部原单元及原请求，仅对确有旧来源事实的组用已有限定审阅的`candidate_request()`构造后继；37个不需替换的JPMorgan组保留原请求，唯一后继组保留原请求ID作前驱并更换有效请求ID。所有返回的`SemanticRequest`都标`replay_only=True`，不能用录制或真实通道申领。原`prepare_requests`函数体及默认参数不改。

`SemanticRequest.validate()`只在请求不属于原完整请求集、且带`source_fact_review_contract`时增加受限核对：必须是D03，前驱必须是当前来源中唯一确有旧事实的原请求，并由当前已认证来源重新生成**逐项相同**的后继请求。请求单元、程序必评集合、完整响应协议及发送正文仍由原工厂核对；只改一个前驱ID就拒绝。没有对任意旧失败开放自动替代，也没有改变B13/D04默认选择或真实调用授权。

`red.log`记录新正向入口在实现前不存在。固定最终树的`targeted.log`/`.exit`对真实保存JPMorgan年报及修订来源运行1项/168.866秒通过：完整38组单元顺序不丢，恰好1组后继，后继当前工厂身份检查通过，错误前驱拒绝，`execute_feasibility()`在申领前以`CONTINUOUS_REPLAY_OBJECT_CANNOT_EXECUTE`拒绝。`short-negative.log`复用旧后继不得丢单元/必评的短反例，1项通过。`fast.log`/`.exit`为当前六文件哈希`fast-tree-before.json`下单作业 **135/135 selector、201.743秒、本地通过**；它不代替新head远端CI。没有重跑先前812秒/507秒的JPM录制整包与冷读。

当前未冻结V14只对`continuous_semantic_calls.py`更新执行绑定，`binding-before.json`/`binding-after.json`及`binding.log`核验当前V14执行权限与provider、SEC、普通刷新三份离线接线；闭包为`sha256:2731935de44d0f123a76f301a1744cc9fb7f83a08e4e89f44f654004207c4168`。V13历史包不重签；旧请求、原响应及计数不改。真实账本保持195槽、143/143/52，新增provider/paid/SEC为0/0/0；D03仍无真实请求许可、Candidate/Evidence、Review/Result/Run或完整公司结论。后续要接原生正向路径，必须另外证明真实执行身份、完整跨组语义和有效Review，不能把本次`replay_only`对象或旧合成未决包升级为成功。
