# PR43 review5205267507 修复与复验

审阅绑定 a56e0ae99056cdab7061751d6718afc6490a4e5d，由 ChatGPT 经用户连接登记，仅覆盖明列模块。原 Issue #28 总委托、预算和无生产权限保持；不是全 PR 批准。修复前状态原字节见 before-continuation.md、before-execution-state.json。

## CI 回归

34891672471 已结束：9 成功、1 失败、1 取消。保存来源作业实际67个入口中只有 capacity_text_results 失败，KeyError: metric_id 见 ci-source-failure.json。夹具现显式带 B13 身份，再由原工厂重算来源和请求哈希；共享指标一致性检查保留。contract-tests.log 的18项通过包含不可得、无Review、缺覆盖和共享D04。

取消作业的 GitHub 注释明确为整体超过30分钟，见 ci-cancel-annotations.json；不能把它混成上述代码失败。1960bac 把原 B13 完整步骤移到独立15分钟作业，原普通作业30分钟时限和所有步骤保留。b13-fixed.log 是补足的完整实际记录响应 Run/公共行及重签输入反例（176.776秒）。首次本地补验期间执行者修改了共享运行文件，后半段被版本绑定拒绝，b13-native.log 保留该失败；随后固定实现、全新目录的补验才计通过。

## D04 分类与原句

原 a56e0ae 的同源引用反例已在仓库复现（d04-before.log）。当前检查从原句独立读取有限关系，复用已有句界、原件注册人别名及引语判断：疑虑必须直接指向持续经营能力，肯定/否定/已缓解分开，主体和明确历史期间分开。对每个源项检查被选中与被排除的事实，模型改类别、时间或主体不能抹掉已证明的关系。

额外反例发现“资产估值疑虑”与“持续经营能力”同句、以及预计未来缓解曾被初版修复错误接受（relation-before.log）；已收紧直接关系和未来语态，不能把词语同现当作关系。无法确定的相关原句，以及缺定义的原生持续经营标志，保留原索引、原文及具体未决，不进入原生成功或最终未披露。

最终单元检查12项、0.107秒（relations-final-unit.log），覆盖正负极性、排除标签、其他主体、历史/当前、条件句、已缓解/未缓解、关系归属、具体未决、原生接受函数及最终公共行攻击。旧测试“只把当前原句标签改成历史即可输出未披露”已改为拒绝；新的历史正例必须在原句中明确2024，目标为2025。另保留当前正确疑虑/无疑虑/缓解，以及无相关披露的合成原件正例。

这不是对任意自然语言的证明，也不是新模型资格。当前完整来源仍需必要真实验证；超出已实现关系的具体未决不能由人工改标签放行。

## 完整记录链与原身份复验

最终未冻结开发 Requirement 闭包：392abc9cd4c6cead38552bf661ca2cd8607e0cff7ff1a7a95d3bc8af496243a6。只更新本草案执行文件绑定，历史快照与原执行记录不改。

- B13/D04 在2ee85dee版本完成各27请求的完整记录响应链、原生 Run、公共行、重签遗漏/改LIVE反例；分别176.776秒和177.736秒。B13实现不受后续仅D04关系增量影响。
- D04随后保留原27份请求、计划和接受编号，经最终392abc9检查进入新消费者 Run；登记前后记录账均为27/27/0，没有重新请求模型，详见 d04-delivery-reuse-summary.json。原失败、诊断、原68业务内容拒绝均不升级。
- 最终6项来源/工厂/WB-3/原身份反例33.238秒通过（source-delivery.log）；108个fast入口84.929秒通过（fast-delivery.log）。语义审计与公司特例检查通过。测试不是390或生产验收。
- 原两份复制包和最终D04复制包均在Python3.9、禁止网络和子进程条件下冷读，见各 cold.json。完整归档包含2953路径、1424唯一对象，5815500字节；每个成员已按哈希/长度检查，随后实际解包。历史中间状态的日志不冒充最终版本通过。

重建命令（输出目录必须全新）：

```sh
python3 docs/evidence/issue28_continuous/review-5205267507/restore_native_material.py /absolute/new/root
python3.9 docs/evidence/issue28_continuous/review-5205267507/cold_read.py /absolute/new/root/d04-delivery-reuse /absolute/new/cold.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d04_native_assessment tests.vnext.test_capacity_text_results
```

固定真实总账本轮只读复核仍33/33/35，68槽封存、无停用通道，剩余207/207/45；新增0/0/0。当前真实调用接线材料仍是旧版本，不据此发新请求。B13受影响路线暂停；修复增量尚缺独立审阅，不由执行者自查替代。八家结构性不适用成果保留；适用B13数值分支、完整真实B13/D04、D03、390、正常更新、统一发布/恢复及旧入口退出仍是同一委托的剩余责任，不设新的局部批准关口。无Ready、合并、正式采纳、部署、active切换或长期运行权限。
