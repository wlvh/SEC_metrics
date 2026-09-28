# D03整组录制包接入完整解释提案

此前D03已经有两项分开的离线能力：`d03_recorded_response_set`保存并冷读一家公司的**全部**原始响应，`d03_complete_interpretation`则要求当前有效请求每组都有原字节回答。旧来源事实组的原请求ID与后继有效请求ID不同，直接把录制包字典交给解释入口会丢失这一映射。本增量只接通这道边界，不发真实模型请求，不生成Candidate、Evidence、Result或Run。

新增的`replay_recorded_complete_interpretation()`先以外部提供的精确包ID重放完整录制包，重新验证原来源、请求和原响应字节；再重建当前每组有效请求，要求公司、来源ID、请求组数与原请求集合一致。它将录制包里的`original_request_id`逐组映射到当前`effective_request_id`，交给已有`validate_complete_interpretation()`再次核对全部单元与语义检查。返回的记录含显式`request_mapping`、包ID、当前输入ID和解释提案ID；执行身份与原生结果标志保持false，调用计数`0/0/0`。旧`validate_complete_interpretation()`的默认返回结构、历史录制包字节及旧成功/失败均未改。

在#28已保存Marriott真实来源构造的原五组录制包 `/private/tmp/issue28-d03-complete-recorded-20260927` 上，`run-recorded.py`禁网重放并连接新入口：五组全部仍为`UNRESOLVED_REQUIRES_REVIEW`，新桥接记录ID为`sha256:598ab808a7027b26456a1dd568cf5fbe8e420462d7365f80ff7c6eff87c6c9b6`；错误的外部包ID被拒。运行前后原#28账本均为143/143/52、195行，录制包`packet.json`哈希不变。`receipt.json`只保存身份、映射与未决摘要，不把合成录制回答写成实际调查结论。此包保存在当前主机临时根，未随Git提交；异机不能仅靠本目录独立重做长链。

定向回归以一个原请求与有效请求同ID、另一个后继请求不同ID作对照，核对字节被送到正确的有效ID、缺组拒绝及伪造原生结果信用拒绝。`module-test.log`记录同模块3项通过；`run.log`记录真实保存包接线37.45秒通过。`tools/run_fast_tests_v2.py`只在FAST_TESTS列表末尾追加这个短回归，函数体与来源材料列表未改。最终`fast.log`为135/135选择器通过（229.959秒）；当前未冻结V14执行权限及provider接线核验仍通过，闭包`sha256:6372c5dbd59d2127227eb3c1ad1f34cd4a6742ba62d1cbd691f04cece8a3cf45`，本次新增D03离线模块未写入真实调用权限集合。远端CI仍须按最终推送head独立读取。

此记录**不是D03原生链完成**：仍缺真实执行收据、完整业务Review、后继MetricSpec、Candidate/Evidence/Result/Run、十家公司真实语义验收与调用资源许可。返回“未决”也不等于完成监管调查判断。它仅使已有可冷读录制包能按当前请求映射进入完整解释提案，为后续原生保存/真实执行接线提供一个不会改签旧响应的输入。
