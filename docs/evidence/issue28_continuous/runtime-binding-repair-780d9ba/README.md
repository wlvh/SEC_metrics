# 780d9ba 原生运行回归修复与 B13 开发材料

这是同一 Draft PR43 的后续增量，不是全 Issue 验收。真实 provider/paid/SEC仍0/0/0，模型密钥当前不可用；获批额度、D-36及生产权限边界不变。没有Ready、合并、采纳、部署或active切换。

## 原始失败与修复

[CI34745889888](https://github.com/wlvh/SEC_metrics/actions/runs/34745889888)的fast通过，但多个原生Run作业失败。确切780d9ba树中，普通V14未冻结草案的4个执行文件已经变化而baseline仍保存旧指纹：ai_adapter、invocation_control、requirement_profile及check_provider_egress，详见ci780d9ba-exact-head-binding-mismatches.json。原生Run报“Run Requirement Snapshot is invalid”；本地单坐标复现保留异常链，实际先拒绝ai_adapter字节。该复现含随后未提交的B13草案，但上述四处冲突另外从确切780d9ba Git对象逐byte核对，未以工作树推测CI原因。

当前只更新未冻结V14的执行文件绑定，未改它的业务rule文件；B13新增Spec方法使compiler另外成为第5项执行差异。原e1ac/6341530的五文件快照在historical-v14-e1ac/，重新计算原闭包仍为e1ac。原Run、失败、审阅和冻结V12/V13/Issue15不重签。新V15重绑当前父闭包及自己的代码、规则与批准；新策略引擎和新请求类型只在被选中时导入，旧普通运行包不强制携带未使用的调用组件。

单坐标修后PASS；5个真实基线B03/B12/D01/B08/E03及10个原生反例PASS115.607秒。复制运行包在无Git/无网络新进程回读B03（14 records）和Python3.9 D01（45 records）通过。100组fast PASS83.921秒。语义/公司字面量/出口检查通过；精确当前调用接线结果见offline-wiring-summary.json。原99组通过和旧8个失败作业均按原head保留，不升级为新head CI结果。

## B13实际做到哪里

新增数值、文本两份后继Spec，历史catalog/metrics/B13_capacity_utilization.md不改。可比数量开发检查复用现有Calculator，验证80/100、零产量、超名义产能数值，拒绝销量/出货/装机/规划量、错单位/主体/期间/产品设施、错误目标口径和非正产能。角色赋义仍须从来源独立证明，计算测试不授来源或原生信用。

Ford和Enphase原件分别产生11/5条相关定性披露，以及8/0个可能产量线索。Enphase明确披露每季度约500万台微型逆变器制造产能；Ford有EV制造产能调整说明。候选保持完整段落和原件定位，不能据此推断利用率或证明无数值对。当前没有B13原生Review/Run，没有已完成数值提取或NOT_AVAILABLE_SEC判定；不能把源候选或关键词未命中当成最终B13结果。下一步仍需完成自动来源赋义、定性/数值/真实缺失的可靠选择与普通入口接线。

## 审核与重放

native-repair-and-b13-material.tar.gz保存原始CI日志、复现与修后目录、全部5个基线/10个反例、两份新调用接线材料、B13源材料及失败日志；archive-members.json逐成员SHA/大小核验。包内执行规则归档亦已在接线测试中逐成员核验。保留的助手错误包括两个检查脚本名、B13检查的原生字段名和模块导入名、计算测试漏传来源绑定；它们与产品回归分开记录，不冒充业务反例。

原780d9ba恢复包在相邻resume-2026-09-13/，包括两份用户转交审阅、批准原文和旧接线；不覆盖该历史包。ChatGPT/Fable的634范围不自动扩展到本次变化。独立审阅、D03/D04真实语义、必要SEC获取、剩余主体债务缺口、完整390、更新/发布/回退与旧入口退出仍保留责任。当前未因缺模型凭据暂停安全离线开发。
