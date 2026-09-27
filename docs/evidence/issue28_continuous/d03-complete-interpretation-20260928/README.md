# D03完整响应的来源重验与解释提案

上一增量从保存原件选择了每组有效请求，但其返回字典可变，不能凭一次计算的`input_id`授原生信用。本次新增`d03_complete_interpretation.validate_complete_interpretation()`作为下游**内存校验**：先从当前#28保存来源重新准备完整输入，逐字段比较调用方给出的对象，再要求每个有效请求ID恰有一份原始响应字节。含旧`source_statement_facts`的组只进入已存在的逐候选后继检查器；其它组进入当前D03原响应检查器。返回逐组发现、未决、原响应哈希和完整覆盖的解释提案，不新建响应包或改写原录制包。

分支被刻意保持为提案：有未决时为`UNRESOLVED_REQUIRES_REVIEW`；若有当前本公司调查发现，也只是`CURRENT_DISCLOSURE_REQUIRES_NATIVE_REVIEW`；即使全组无发现、无未决，也只能是`ABSENCE_RULE_NOT_APPROVED`，不能由空输出直接证明无调查。返回值的provider执行身份、Candidate/Evidence、Result/Run及生产权限均为false。响应可来自录制或未绑定字节，必须待后续独立真实执行收据、业务定义、Review和原生Run逐层验收。

`material.log`记录初版在Marriott真实保存来源上用禁网合成响应完成全部组并保持未决（1项/44.132秒）；随后只增加了响应映射的同操作快照，防止调用方在检查期间改变字典。最终`final.log`在该代码下**2项/41.936秒通过**：一项使用相同真实Marriott来源验证完整组响应、缺组拒绝和修改有效请求提示后拒绝；另一项用隔离合成小例确认全组空发现不生成否定结果、非空当前发现仍仅为待原生Review的提案，以及错根拒绝。`final-before-positive.log`保留新增非空小例以前的本地两项通过记录。真实来源测试中的响应是合成内容，不是模型语义正确性证明。`tools/run_fast_tests_v2.py`只在fast列表末尾追加小例selector，不改runner函数体；未重跑不受影响的完整来源分片。

该模块未进入真实调用入口和当前执行权限文件；没有D03 MetricSpec、原生Candidate/Evidence/Result/Run、公司结论或公开行。本轮provider/paid/SEC真实新增调用0/0/0，旧失败、D04十家候选、B13及#47状态不改。
