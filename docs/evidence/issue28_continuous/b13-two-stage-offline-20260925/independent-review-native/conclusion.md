# B13 两阶段原生接线限定独审

- 补丁：`7cde5ae02b176d768fc6ea078f5f310211d2923e`，比较基线 `1e05850b`。
- 范围：仅本次 B13 扫描／判断合同、原生录制与重读、混合请求分组、所列定向测试和证据；不审全 PR、旧 P2、D03/C04 或真实模型表现。
- 结论：**NEEDS_FIX（P2）**。扫描误选后按原文排除的正向分支已接通，双阶段保存和录制整公司冷读有相应证据；但一个明确相关的扫描候选仍能借错误主体或时间标签通过判断阶段。这一缺口应在将两阶段候选用于真实执行决定前限定修复。

## P2：错误主体／时间可绕过新增的错误排除护栏

`capacity_two_stage.validate_interpretation()` 的新护栏仅在 `finding.kind` 是背景类、**且** `subject == TARGET_REGISTRANT`、**且** `timing == CURRENT_REPORT` 时检查原文中的 `manufacturing/production capacity`（第 506–516 行）。本次测试夹具的原文是：

> Our contract manufacturers have sufficient production capacity for anticipated demand.

请求自带的 `OTHER_ENTITY` 定义明确说不得把注册人已识别的合同制造安排归为其他主体。在该夹具中，正确主体／当前期加 `other_context` 会被 `B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW` 拒绝；仅将主体改为 `OTHER_ENTITY`，同一 `other_context` 判断却被接受。改为 `other_entity` 类别并同时给 `OTHER_ENTITY` 主体也被接受；将 `other_context` 的期间改为 `HISTORICAL` 同样被接受。隔离执行见 `adversarial.log`。这些是同一条来源、同一扫描候选和完整第二阶段响应，未篡改原文、扫描集合或类别定义。

`capacity_reference_contract.restore_response()` 第 184–195 行在 V5 确保发现引用属于扫描集合，也允许扫描候选作为背景排除；它不验证这种主体／期间解释与引用原文是否冲突。因此该响应的 `unresolved` 为空时，后续原生接受可以使用它。**这不是已经观察到真实模型犯错或生产结果误收**，而是已复现的离线错误接受路径。旧 V4 的语义验证也不是本次可重写对象；建议只在显式两阶段后继检查中收住已知的主体／期间绕过，同时保留合法的其他主体与历史陈述。

## 已核对的成立范围

- 扫描候选和原必评集合分别保存。非必评发货背景被扫描后，V5 可据原文排除；同一响应由旧 V4 拒绝，旧合同未被全局放宽。遗漏原必评、扫描外发现、扫描未决丢失和超 64 候选的定向保护存在。指定短测实际执行 **29 项通过**，日志 `short-tests.log`；所审源码工作树字节与指定 SHA 无差异。
- 扫描与判断使用各自原始请求／响应。判断的原生 Candidate/Evidence 带扫描终态、验收收据、输出哈希和前驱编号；无保存扫描证明不能走通用 B13 接受入口。新两阶段 live 入口仍拒绝，单独扫描只形成形状检查、没有指标结果。登记输入含两阶段记录，安装副本的普通 Run 重读会重新走登记校验。
- 只读检查了已有 `native-chain` 和 `final-native-replay` 日志／摘要：六组 Enphase 的模拟混合 V4/V5 链形成录制 Result/Run 与公开行，独立进程冷读相同，最终绑定重放不新增录制申领。原 190 的只读重放日志支持旧组按原请求身份保留。上述长链由执行方运行，**本独审没有重跑**；模拟输出不构成真实 B13 公司结果。
- 已读资源压力日志：剩余组的扫描和至多 64 候选／全未决判断输入按固定保存来源测量在 200,000 上下文内，最紧项仅余 352 token。它不证明 4096 输出一定完整，也不证明扫描召回、分类正确、32 次真实执行已获授权或两家公司可完成。

本次未发模型／SEC 请求，未操作原账本、#47/PR52、生产指针或其他分支；未 commit/push。除本目录的 `conclusion.md`、`short-tests.log`、`adversarial.log` 外没有写入审阅产物。
