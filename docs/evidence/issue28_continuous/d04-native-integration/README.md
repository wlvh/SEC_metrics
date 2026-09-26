# D04原生接线与原执行身份复验（开发验证）

本增量在f42ea79后继续，同一分支和Draft PR43。D04新增完整保存年报/修订输入的明确原生入口，复用既有WB-3、Candidate/Evidence、来源私有登记、Review、Run及公共行。旧D03/D04可行性入口和51–53原始响应保持原含义，不会自动变成原生记录。

`d04_native_assessment`复用无损字段/样式共享和来源编号表示；保留全部来源单元。类别、主体、时间分别检查，历史疑虑不会因类别名而成为当前疑虑。当前判断须有持续经营语义的必要原文条件，干净审计意见、网络安全无重大影响和估值疑虑反例被拒绝；这个必要条件不是充分语义证明。多种当前分类需要跨请求对齐，不能变成未披露。

完整来源判断经有效Review后，没有当前疑虑陈述时，公共行沿既有TEXT_QUAL显示“未披露持续经营疑虑”并附检查范围。程序判断放在notes和范围证据中，不伪装成原文引文。当前只完成记录响应验证，不声明Enphase真实D04结论或语义资格。直接数值/布尔标签不能单独授予含义。

历史2016/2017控制有单独的新请求身份和PRIMARY/HEADER_ONLY范围。离线接线使用从旧51/53构造的明确记录测试响应，原响应不改；证明新格式可保留原有正向/时间区分，且历史控制不能登记为当前完整输入。它不是新模型复测，不是整份申报缺失证据。

`native_assessment_replay`处理无关消费者版本变化：只接受完全相同的原请求和原来源字节，核对原终态全部文件、捕获的规则、原Requirement及相同预算/传输决定，使用既有只读历史视图重读原计划和原接受收据，再以当前检查器重新验证原文和语义记录。旧代码作为数据读取，不执行归档Python。原计划/响应/接受ID均不改；当前复验另留记录，不构成新调用。请求、模型body、协议、来源或语义记录变化拒绝；旧诊断/失败拒绝；原68仍因税收抵免语义失败而拒绝。

已完成27个f42ea79记录测试请求的原身份复验、重新登记和新版本Run/公共行，新增调用0/0/0。反例包括改请求、改原响应、重签成当前计划和把只读历史视图当执行权限。数据包继续服从原有创建者私有登记/可信安装对边界，不声称抵御同时替换运行代码、输入和执行历史的操作者。

当前D04完整27个记录请求→登记→Evidence/Review→OPEN Run/行/重签攻击通过185.941秒；七项D04接线/原收据复验/正反例30.873秒，108fast95.607秒。共享B13记录原生回归194.110秒及V14原场景131.521秒属于本增量此前未改变各业务逻辑的检查；具体closure按各自保存材料读取，不能混作真实模型资格。

本增量新真实调用为0；本会话此前累计仍33/33/35、剩余207/207/45。B13受影响真实路线因68错误接受暂停；当前新D04/来源复验代码尚缺对应独立模块审阅，不能把本离线结果称为全PR批准。D03的6e5具体模块审阅仍待报告，不重试9月17日前受限旧Codex任务。适用B13完整真实来源和数值配对、D04新版本真实验证、D03、390、正常更新、统一发布/故障恢复及旧生产/补数入口退出仍未完成。总委托与预算不撤回；无Ready、合并、正式采纳、部署、active切换或长期生产权限。

## 入口与验证

```bash
# 只准备新D04原生请求；不会调用模型
python3 tools/vnext_continuous_semantic.py prepare --company enphase_energy --metric D04 --native --output /absolute/new/requests.json
# 已有受信完整原生输入后，创建隔离普通候选
python3 tools/vnext_normal_candidate.py --company enphase_energy --metric D04 --output-root /absolute/new/candidate
PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d04_native_assessment tests.vnext.test_d04_native_wiring tests.vnext.test_native_assessment_replay
D04_NATIVE_RUN_MATERIAL_ROOT=/absolute/new/material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d04_run_material
```

材料索引保存每个文件的SHA256和长度；归档保存完整数据、运行时、原请求/收据及实际Run。真实控制的新调用与当前完整结果仍是后续动作，不把本记录响应替代真实验收。

当前闭包：`sha256:a72021ea3a8c130a76e688df2f71a4f512a25ff143deb403c313611e20c4cb40`。完整归档1945路径/1111唯一对象，XZ约5.6MiB，所有对象已读回且实际解包；复制的D04与原身份复验B13运行时均已Python3.9禁网冷读。解包冷读回执单列。f42ea79 CI为9成功/1取消，不作为本增量CI通过。

完整归档解包后的D04运行时已在Python3.9禁网冷读通过，见extracted-cold-summary.json。
