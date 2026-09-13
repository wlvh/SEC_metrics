# 2026-09-13 恢复：审核入口与实际边界

用户已批准累计 provider≤240、paid≤240、SEC≤80，以及限定 Ford/Enphase 的 B13 口径。[真实批准代登记](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5651558538)由 Codex 忠实记录用户对话批准，第一、二节原文见 approved-sections-verbatim.md 和 approval-comment.json；不是用户逐字审核代码或代码 APPROVE。原总委托全文、旧评论、失败与关闭额度保留。

当前实际 provider/paid/SEC=0/0/0。新 issue_28_v14/PROFILE_DRIVEN_V15 绑定该评论、现行 deepseek-flash 和新策略工厂，保留 WB-3、原200000 context/8388608 bytes/120秒与零自动重试；旧 Issue15 默认入口的字节失配不删除、不绕过，旧v8不借权。D-36继续禁用仓库金额预检/预留/上限；100 USD属于用户外部账户安排，本轮未检查、充值或修改账户。未知 token、estimated_cost、actual_cost在新后继保留null，不能写成零。

## 材料

- `review-coverage.json`：ChatGPT review5189571246原文和用户转交 Fable5.1 的模块覆盖。Fable目录的18个索引文件加MANIFEST共19个物理文件，全部SHA核验；报告测试未由Codex重跑。23条RECORDED_TEST_ONLY登记保留。两份审阅都不是全PR批准；新调用控制及其他未覆盖模块仍需独立审阅。
- `offline-wiring.json`、`offline-wiring-summary.json`：实际来源→授权→后继配置/工厂→真实请求→原官方transport及WB-3的离线测试。所有socket/DNS/SEC被阻止，官方opener返回明确测试wire，原生marker为MOCK；只选一个请求验证接线，不宣称整个公司的语义已验证。
- `offline-wiring-material.tar.gz`、`offline-wiring-members.json`：原始失败、修后日志、请求、原生控制器记录和当前测试包。每个成员SHA及大小均读回核验；包内执行规则归档也逐成员核验。真实原件重放仍使用本仓库已保存的源基线，本包不是完整独立业务验收副本。
- `current-gap-index.json`：固定1c9f562的53项历史问题与后续修复对照，其中19项已有后续修复，另列4处展示修复。未把它改写为当前完整340/390结论。Salesforce财年标签的既有修复继续复用。
- `historical-state/`：被替代的旧受阻状态原字节。当前状态只读上层execution-state.json和continuation.md。

## 实际检查

统一计数/批准负例及已有后继WB-3共18测试通过；99组快速套件通过80秒左右，精确时长在原日志。新源材料测试走真实保存SEC来源和实际DeepSeek请求构造，验证无私有令牌及请求变造拒绝、未知usage保留、原样请求去重、原父V14=e1ac4b08/351不变。语义、公司字面量与单一出口检查分别保存结果。所有这些是执行者自查及离线测试，不计独立审阅或真实语义资格。

原失败不隐藏：初次MOCK响应误用usage=None而非字段对象；初次来源请求重读后JSON键顺序不稳定；首次计数claim多写空行；并发测试子进程缺显式PYTHONPATH；文档路径中的批准日期触发公司字面量检查，路径现移入绑定配置。这些修正不改变业务语义或扩展资源。错误工具文件名/首次断言预期错误属于运行助手错误，不冒充产品反例。

## 当前依赖与下一动作

模型密钥在当前执行环境中不可用，已向用户请求本机配置位置，尚未消费真实slot。它只影响真实模型调用；B13、主体/修订/Company Facts、JPM/Ford范围及D03来源事实等离线工作继续。JPM融资租赁与Ford工业归母权益缺证仍必须形成非数值结果，不能用范围接线或小计替代完整B06。

固定总账 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13` 使用目录锁、初始化锚、追加claim、slot意图及原WB-3终态。失去终态按可能调用计账并停止该通道；先核对原件再补封同一终态，不重新发请求。不得删锚、claim或slot恢复预算。每次执行保留确切规则与配置字节，后续代码变化不能改写本次调用。SEC份额已绑定但真实获取接线尚待完成，声明路径/接口不等于已经调用。

`tools/vnext_continuous_semantic.py prepare --company <公司ID> --output <新外部JSON>`离线列出真实请求及资源限制；`execute`还要求确切request-id、绑定接线材料、模型凭据和有效总账。可行性输出保留原始响应，但未生成原生Evidence时控制器终态明确标记FEASIBILITY_ONLY_NO_NATIVE_EVIDENCE；这不等于语义失败，也绝不是原生成功。核心语义必须按真实来源和关键反例另外判断。

完成后继续B13、必要SEC新获取、完整390、普通更新与发布/回退/旧入口退出准备。最终开发验收就绪才集中请求生产确认。本增量不Ready、不合并、不采纳、不部署、不切active、不提前关闭Issue；同一Draft PR43连续推进。
