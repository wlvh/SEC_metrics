# B13 V7 已知反例的有限离线回修

基线为已推送的 `227182efe31b7ce6364c866753ae1332afb41ea2`。原 V7 限定独审对语义给出 `NEEDS_FIX`，同时确认申领及原生接受仍关闭。本次只改显式 V7 的离线断言划分和矛盾诊断；原 V5/V6 请求及检查、V7 请求字节、原190及所有失败原件均不改。`B13_CLAIM_CONTEXT_VALIDATION_SUSPENDED` 保留，**不授真实调用或原生结果信用**。

具体已知错误与处理：

- `and` 连接两处各自有明确谓语的物理产能陈述时，允许两个不重叠断言范围共享整句背景；只有两个产能名词共享一个谓语时仍为一个范围。
- 代词借用的整句前文含两个不同词面主体时，返回明确的 `B13_CLAIM_ANTECEDENT_AMBIGUOUS`，不从“最近出现的词”强选主体；单一明确先行词仍可服务第二断言。
- 对已报告的 `can provide` 被错标历史、明确 `have` 被错标条件、`If ... could` 被错标当前提供具体未决。没有把 `can/could` 一律归为同一时态，也没有取消统一暂停。

`targeted-tests-final.log`：32项定向测试通过，新增测试经过完整 `validate_interpretation()` 响应入口，包含并列双结果与单谓语双名词、错误与不确定主体、当前／历史／条件正反例。`legacy-requests.log` 与 `v7-request-identity.log`：旧V5/V6固定请求和V7固定请求字节不变，不能据此宣称所有来源已被验证。`rebind-corrected.log` 与 `current-identity.log`：只更新未冻结的 V14 `capacity_two_stage.py` 字节绑定及三份当前接线收据，当前代码根上的V14闭包与执行权限校验通过；V13默认代码未改。第一次 `rebind.log` 失败仅因脚本试图在代码尚未重绑定前加载旧完整身份，未写入绑定；修正后先与推送基线逐字节比较再重绑定。

精确补丁 `9d04d654af7649aa0ab90719d6c8f2ca7a94efaa` 的限定独审见`independent-review/conclusion.md`：**V7语义仍为`NEEDS_FIX`，暂停门和当前绑定`PASS_WITH_BOUNDS`。** 审阅新增连续两个`and`误切、句尾`if`漏诊及关系从句`we`导致清楚的`they`先行词误拦。随后本机仅有一次未提交的有限试验，`followup-targeted-tests.log`明确显示原V4把`plan to add more production capacity`合法规划句判为角色未证明；该试验改动的源码和测试已恢复到上述已审SHA，没有混入最终执行绑定，也没有给旧失败成功信用。此处按有界停止处理，不继续用表面词条扩张换取离线通过。

测试仅证明原先有限反例的程序行为；没有新模型响应、原生双阶段公司链、190混合公司结果或新请求授权。对其它自然语言指代、条件与漏报不作普遍正确性主张。V7继续停用，不能靠删除暂停码起跑。该次审阅代理的普通消息数超出原限制，父会话已在`execution-state.json`如实登记，不再调用该代理。
