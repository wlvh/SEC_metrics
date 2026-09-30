# 5f8d372a 独立限域审阅

审阅对象：5f8d372a36936646fa5ae2732a920ee98aa12118，相对父提交 e646f9cdac3fa2b57096892eb7f4fbd1deebb805。结论：**NEEDS_FIX（P2）**。原第192次的 F450 美元金额现被 V4 和 V5 拒绝，且同一 finding 中同时引用 F449/F450 也被拒绝；但新检查对另一种合法的货币单位声明仍会错误接受正向物理产能判断。

## 发现

scripts/vnext/capacity_reference_contract.py:76-85 从单位节点开始处保存的 namespace environment 解析 measure 内容的前缀，未读取 measure 节点自身的 namespace 声明。合法 XML 可以把货币前缀声明在 measure 上：

    <xbrli:unit id="credit"><xbrli:measure xmlns:money="http://www.xbrl.org/2003/iso4217">money:USD</xbrli:measure></xbrli:unit>

现有原生来源解析器 _NativeObjects 把该单位的外层 namespace environment 记为仅含 xbrli，而 _FactAttributes 正确将实际 measure 解析为 ISO 4217 USD。独立构造的最小来源经同一 B13 request/response 验证链运行时，_currency_numeric_native_refs 返回空集；模型仅引用这一货币事实 F450 并将其标为 physical_capacity_context，**V4 与 V5 均返回 CAPACITY_QUALITATIVE 且 unresolved=[]**。因此 scripts/vnext/capacity_reference_contract.py:230-238 的防线没有覆盖全部原生货币事实。此反例是合成材料，不声称原第192次使用了这种命名空间写法。

建议复用已有的原生单位解析方式，在 measure 节点实际生效的 namespace 中解析 QName，再对 ISO 货币作拒绝；新增 V4/V5 各一条局部 namespace 负例，并保留无货币单位文字事实正例及原190响应回放。当前补丁不宜以“ISO 货币事实已通用拒绝”作为审阅通过结论。

## 已核实的边界

- 原第192次保存来源中的 F450，以及 F449 与 F450 同组引用，V4/V5 离线重放均触发 B13_NATIVE_CURRENCY_FACT_IS_NOT_PHYSICAL_CAPACITY_EVIDENCE。这证明本次具体美元事实的误接受已被堵住；没有新增模型或 SEC 调用。
- 原190保存的 assistant-output.bin 在当前代码下重验为 5 条 finding、0 个 unresolved，响应 SHA-256 与原日志一致；190、191、192 请求均从各自基底重新生成相同结构和请求字节身份。V1/V2/V3 三项定向回归通过；新增拒绝分支只适用于显式 V4/V5。
- V13 baseline_manifest.json 与父提交逐字节一致；V14 manifest 的内容差异仅为新规则文件的两处绑定及可扩展性豁免文件的一处绑定。当前 V14 Requirement、执行规则与三份原有离线接线收据通过只读校验。
- 两处 F 字面量精确豁免仍分别在 181、301 行，AST 语法均为原生事实引用前缀，配置没有增加豁免类型或条目。

独立执行：指定单项测试 1/1 通过；V1/V2/V3 定向测试 3/3 通过；原190只读回放、原192 V4/V5 引用反例、局部 namespace V4/V5 反例及绑定检查结果见 review.log。提交者附带的 fast.log 声称 142 入口通过、directed.log 声称 45 项通过；本审阅没有重跑这些套件，也没有把提交者日志当成独立执行结果。未运行真实模型、SEC、生产操作或长材料测试；未修改规则、历史请求、账本或接线。
