# B13 双阶段护栏回修限定独审

- 审阅提交：`99d868f52cf94d42966c28175d840e5a10917a2e`；直接前驱：`7cde5ae02b176d768fc6ea078f5f310211d2923e`。
- 范围：本次 `capacity_two_stage.py`、`test_capacity_two_stage.py` 和 V14 `baseline_manifest.json` 差异；继承 `../independent-review-native/conclusion.md` 的旧 P2，读取最终录制重放摘要和日志。不审全 PR 或真实模型准确率。
- 结论：**NEEDS_FIX（P2）**。直白的当前合同制造产能句子被错误 `OTHER_ENTITY`／`HISTORICAL` 标签排除时，回修已拒绝；但同一句中出现旧期间对照时，错误标签仍可通过完整的第二阶段离线验证。现有 30 项短测通过，不覆盖这一反例。

## P2：历史对照词使当前产能断言逃过护栏

新 `_direct_current_target_capacity()` 在整句内搜索 `previously`、`prior years` 等词；只要命中，就跳过整句（`capacity_two_stage.py:84-92`）。被排除的句子可以同时含有清楚的当前断言。限定复现使用原测试的来源构造、V4→V5 请求、完整扫描候选和第二阶段验证；未改原文、候选集合或源码。

| 可见块原文 | 错误第二阶段标签 | 实际结果 |
| --- | --- | --- |
| `Our contract manufacturers have sufficient production capacity for anticipated demand.` | `other_context` + `OTHER_ENTITY`／`HISTORICAL` | 均拒绝，符合修复目标 |
| `Unlike prior years, our contract manufacturers have sufficient production capacity for anticipated demand.` | `other_context` + `OTHER_ENTITY`、`other_entity` + `OTHER_ENTITY`、`other_context` + `HISTORICAL` | 均 **ACCEPTED**，`unresolved=[]` |
| `Our contract manufacturers previously had limited output, but they have sufficient production capacity for anticipated demand.` | 同上三种错误标签 | 均 **ACCEPTED**，`unresolved=[]` |

详见本目录 `adversarial.log`。被接纳的两句都明确说合同制造商**现在有**足够生产能力；过去年度或过去限制只是对照，不应让当前断言归到其他主体或旧期间。`validate_interpretation()` 在原验证器之后只依赖该辅助判断拦截错误标签（`capacity_two_stage.py:530-548`），因此上述响应走到无未决的返回值。这里证明的是离线错误接受路径，并未观察真实模型作出这种判断，也没有发布真实结果。

建议只在显式两阶段路径内修正整句历史词一票否决：判断同一句中的当前断言及其局部时间／条件限定，并加入上述两条混合句反例。修复须同时保留真正旧期间与其他主体的通过边界，不能全局放宽旧 V4 或把不确定来源当成当前产能。

## 已核对边界

- 直接当前合同制造产能的四种错误类别／主体／时间组合均被新测试拒绝（`test_capacity_two_stage.py:114-134`）。真正其他主体样本被接受；旧期间样本没有被新护栏错判为当前，但原验证器另外返回 `B13_TWO_STAGE_UNRESOLVED`（`test_capacity_two_stage.py:136-187`）。独立复现与此一致。短测命令 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_capacity_reference_contract tests.vnext.test_native_unit_index -q`：**30 项通过**，见 `short-tests.log`。
- 本次生产代码差异仅改 `capacity_two_stage.py` 的新辅助判断及 V5 `validate_interpretation()` 护栏。V14 manifest 的两处哈希／大小均等于当前目标文件实际字节：`1d593fd203bd899a6a5639551cf6bf58ac39f66955769b10eeae1891bc139530`、`30236`。工作树中三份受审文件与指定提交无差异。V4 请求选择和双阶段扫描／判断的完整来源与身份接线未在本补丁改动；旧 V4 非必评背景仍由短测证明拒绝，显式 V5 仍区分扫描和判断阶段，两个真实执行入口仍有 `ledger.live` 关闭条件。这是静态差异与短测结论，不是长链重跑。
- 只读核对 `repair-native-replay-summary.json`、`repair-native-replay.log` 和 `repair-native-cold.log`：提交材料报告模拟 Enphase 六组混合 V4/V5 终态重放、一个扫描阶段、保存 Run／Result 与安装环境冷读公共行相同，新增录制请求及真实请求均为 0。该长链由执行方运行，本独审未重跑。它验证所用录制样本的绑定，不覆盖上述错误标签的混合句反例；也不构成真实 B13 公司结果或生产许可。旧 190 只读重放日志另报告请求身份保持且新 provider 请求为 0，本独审未重放它。

本独审没有真实 provider／SEC 请求、长测、commit/push、原账本或生产操作，也未操作 #47／PR52。只新增本目录的 `conclusion.md`、`short-tests.log`、`adversarial.log`。
