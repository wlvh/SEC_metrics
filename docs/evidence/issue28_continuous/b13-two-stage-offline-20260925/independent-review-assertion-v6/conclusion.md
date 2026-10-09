# B13 显式断言片段 V6：限定独立审阅

- 精确对象：`151ce51f2217a2b1bd4e5b71492d47d67c2e9242`，相对父提交 `9552226d09f9fa5999218644b7a4e72bf387d513`。仅审本次 V6 差异及其经过的 B13 输入、原生接受、保存重读和入口；不复审整个 PR、旧 V5 语义或真实模型准确率。
- 结论：**NEEDS_FIX**。V6 新增一条可接受错误排除的路径，也会拦住一种明确的正确来源。两项均由完整的合成原文、扫描、V6 判断和原 V4 来源验证复现；V5 同输入作为差异对照。复现见 `adversarial.log`。这不表示模型已经实际给出该错误响应，也不授真实请求或生产信用。

## P2：分号后指代本公司制造商的产能被错误排除

原文：`Our contract manufacturers operate plants; they have sufficient production capacity for current demand.` 扫描选中该可见块 B0；V6 响应把分号后的完整片段 `[43,103]` 标成 `other_entity / OTHER_ENTITY / CURRENT_REPORT`。`validate_interpretation()` 返回 `unresolved=[]`，因此当前原生接受函数的“没有未决”门（`capacity_native_assessment.py:36-38`）不能挡住这个错误标签。相同标签走 V5 对完整原文的检查会报 `B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW`。

原因是 `capacity_two_stage.py:559-573` 把分号后半句机械地当作独立片段，允许以 `they` 开头、没有明确主体的区间；`:705-715` 只把这个区间传给目标主体检查。旧完整原文检查能够把 `they` 接到紧邻的 `our contract manufacturers`，新检查失去这一先行词。提示文字要求区间“包含主体”，但程序只验证字符边界，未验证主体是否能从区间内确定。`:717-718` 保存的原响应仍有区间，然而规范化的 `findings` 只含整个 B0 原文，后续文字路线（`capacity_text_results.py:67-70,86-105`）没有片段主体信息来纠正错误排除。应让需跨片段确定主体/期间的情况保留未决，或给区间绑定可验证的先行词；修复后需走原生接受及保存重读的反例。

## P2：同一断言的两个等义产能短语被当成两条声明

原文：`Our contract manufacturers have manufacturing capacity, including production capacity, for current demand.` 只有一个以 `Our contract manufacturers` 为主体的当前产能断言。V6 对整句给出正确的 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`，但 `capacity_two_stage.py:626-629` 仅按 `manufacturing capacity` 和 `production capacity` 的出现次数大于一，加入 `B13_ASSERTION_MULTIPLE_PHYSICAL_CLAIMS:B0`；原生“没有未决”门会拒绝。V5 同输入 `unresolved=[]`。应区分两个独立断言与同一断言的重复措辞；如果确实不能证明关系，可保留未决，但不能把短语次数当作两条声明的证明。现有保存来源的“双匹配块”计数本身不证明其语义，不能据此推断实际影响比例。

## 身份、入口和证据边界

- `binding-check.log` 只读核对了 `assertion-binding-after.json` 列出的 10 个改动文件：当前字节的 SHA-256/大小均与 V14 manifest 一致；provider 收据列出的 52 项及 SEC 收据列出的 15 项证据哈希均仍匹配。收据分别记录 `[0,0,0]` 新调用及禁网录制/模拟检查。这证明收据与当前文件的有限绑定，不证明上述语义正确、真实模型输出或整家公司 Run。
- V6 需要显式 `assertion_scopes=True`。`continuous_semantic_calls.py:681-718` 的普通 B13 原生入口拒绝 V5/V6，双阶段入口拒绝 `ledger.live`；`capacity_two_stage.py:316-465` 和 `native_assessment_replay.py:20-35` 对保存的扫描证明、序号和响应作重读。本次差异未找到阶段身份绕过或 V6 真实入口意外开放。V5 默认分支的请求构造未改；三套短测合计 32 项通过（`short-tests.log`）。
- 已存 `assertion-scoped-native.log` 记录一项 125.290 秒禁网录制与重读通过，本审阅按要求只读取，未重跑。两份默认完整 Run 日志是在没有设置该 CI 作业的 `B13_REFERENCE_CONTEXT=1` 时失败，不能称本补丁的默认完整 Run 通过，也不能把这一失败直接归咎于 V6。当前提交的完整 CI 和真实模型语义未在本审阅验证。
- 本审阅仅运行短测、内存合成反例和只读哈希核对；未调用 provider/SEC、未修改账本、未执行超过 120 秒的测试，也未触碰 #47/PR52。
