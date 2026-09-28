# D03整组录制包接入完整解释提案

此前D03已经有两项分开的离线能力：`d03_recorded_response_set`保存并冷读一家公司的**全部**原始响应，`d03_complete_interpretation`则要求当前有效请求每组都有原字节回答。旧来源事实组的原请求ID与后继有效请求ID不同，直接把录制包字典交给解释入口会丢失这一映射。本增量只接通这道边界，不发真实模型请求，不生成Candidate、Evidence、Result或Run。

新增的`replay_recorded_complete_interpretation()`先以外部提供的精确包ID重放完整录制包，重新验证原来源、请求和原响应字节；再重建当前每组有效请求，要求公司、来源ID、请求组数与原请求集合一致。它将录制包里的`original_request_id`逐组映射到当前`effective_request_id`，交给已有`validate_complete_interpretation()`再次核对全部单元与语义检查。返回的记录含显式`request_mapping`、包ID、当前输入ID和解释提案ID；执行身份与原生结果标志保持false，调用计数`0/0/0`。旧`validate_complete_interpretation()`的默认返回结构、历史录制包字节及旧成功/失败均未改。

在#28已保存Marriott真实来源构造的原五组录制包 `/private/tmp/issue28-d03-complete-recorded-20260927` 上，`run-recorded.py`禁网重放并连接新入口：五组全部仍为`UNRESOLVED_REQUIRES_REVIEW`，新桥接记录ID为`sha256:598ab808a7027b26456a1dd568cf5fbe8e420462d7365f80ff7c6eff87c6c9b6`；错误的外部包ID被拒。运行前后原#28账本均为143/143/52、195行，录制包`packet.json`哈希不变。`receipt.json`只保存身份、映射与未决摘要，不把合成录制回答写成实际调查结论。此包保存在当前主机临时根，未随Git提交；异机不能仅靠本目录独立重做长链。

定向回归以一个原请求与有效请求同ID、另一个后继请求不同ID作对照，核对字节被送到正确的有效ID、缺组拒绝及伪造原生结果信用拒绝。`module-test.log`记录同模块3项通过；`run.log`记录真实保存包接线37.45秒通过。`tools/run_fast_tests_v2.py`只在FAST_TESTS列表末尾追加这个短回归，函数体与来源材料列表未改。最终`fast.log`为135/135选择器通过（229.959秒）；当前未冻结V14执行权限及provider接线核验仍通过，闭包`sha256:6372c5dbd59d2127227eb3c1ad1f34cd4a6742ba62d1cbd691f04cece8a3cf45`，本次新增D03离线模块未写入真实调用权限集合。远端CI仍须按最终推送head独立读取。

此记录**不是D03原生链完成**：仍缺真实执行收据、完整业务Review、后继MetricSpec、Candidate/Evidence/Result/Run、十家公司真实语义验收与调用资源许可。返回“未决”也不等于完成监管调查判断。它仅使已有可冷读录制包能按当前请求映射进入完整解释提案，为后续原生保存/真实执行接线提供一个不会改签旧响应的输入。

精确补丁`8a49b5ab`的[限定独立审阅](independent-review/conclusion.md)通过，审阅者实跑新增短测、联读旧整包重放器与当前解释器，未见在此范围把录制内容授予真实请求或原生结果信用的通路。审阅边界同样清楚：Marriott保存包五组均没有原请求ID与有效后继ID不同的情况；这一映射由短测试和代码核对覆盖，**真实后继包的整条冷读仍待后续验证**。审阅者只读本次长材料与fast日志，没有独立重跑。

**后继组保存原件补验：**在不改变上述代码的前提下，`run-jpm-recorded.py`从#28已保存的JPMorgan真实年报/修订原件重建完整38组，给每组构造明确标为**合成且未决**的响应；其中恰有1组按原来源事实候选使用不同的后继有效请求ID。当前整组录制包保存、逐组验收及桥接完成，`jpm-recorded-summary.json`的包ID为`sha256:72536bbb...`、桥接记录ID为`sha256:bd5eaf87...`，38组全部仍为`UNRESOLVED_REQUIRES_REVIEW`，无原生结果。首次完整执行812.504秒，不加入CI短/材料选择器以避免把新的长材料与已通过的大套件重复叠跑。

`cold-jpm.py`另起独立进程，直接从前述私有包重放完整来源、原响应与当前有效请求映射；`jpm-cold-result.json`为`PASS_INDEPENDENT_PROCESS_SAME_PACKET_AND_PROPOSAL`，包ID与桥接记录ID和首次完全相同，含38组及1组后继映射。包的40个文件前后哈希一致，原账本前后仍143/143/52、195行，真实调用0/0/0；这次重读507.22秒。短`reconcile-jpm.py`从保存包逐文件检查尺寸/哈希、外部包ID、原/冷读记录ID与零信用，`jpm-reconciliation.json`通过。私有包路径为`/private/tmp/issue28-d03-jpm-recorded-bridge-20260928`，不随Git提交，不能说异机只凭本目录已重现。两次时间是本机一组实测，不能外推全部公司，但说明未来真实D03运行前还需核算逐组验收耗时。

这项增量补上了初次限定审阅指出的**真实来源后继请求映射与独立冷读**证据空白；响应内容仍由本脚本合成，不能证明模型会正确理解JPMorgan调查披露，更不能因38组都未决就推断原年报未披露监管调查。它也没有得到执行收据、D03 MetricSpec/Review/Result/Run、真实调用或生产资格；初次限定审阅仅覆盖`8a49b5ab`原差异，新增JPM原件补验须另按实际新增差异复核。
