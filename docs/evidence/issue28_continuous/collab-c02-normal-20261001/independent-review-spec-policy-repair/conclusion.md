# C02 Spec／选源策略配对：限定独立审阅

**结论：PASS_LIMITED。** 本次仅审阅 `ad83fcbcd12d1ebf26e3cf3741591e4c91c9568c` 相对 `f4e4c4f62a1536b8bd265ced3ddf00962aaee9b6` 的 C02 API 配对修复、相应测试、可变 V13/V14 绑定及三份接线收据。前一补丁的 `NEEDS_FIX` 记录保留原义；本结论只覆盖其指出的 Spec／策略交叉调用，不把 C02 分组的业务内容或正式 390 坐标判为已验收。

## 修复核验

- 新 `_require_spec_policy_pair()` 将 `c02_composition_facts_v1` 只配 `COMPOSITION_FACTS_V1`、`c02_composition_grouped_v2` 只配 `COMPOSITION_GROUPED_V2`。候选创建、Evidence 构造和 Result 重放在进入分组来源处理前调用同一检查。`reviewed_text_observations()` 通过 Evidence 重建进入该检查，`verify_text_result()` 通过重放进入；不能再用旧 V2 Spec 加 V3 分组策略得到缺少原始块映射的 Result。反向交叉也从原来的 `KeyError` 变成明确的 `C02_COMPOSITION_SPEC_POLICY_MISMATCH` 拒绝。
- 我实际运行了 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts python3 -m unittest tests.vnext.test_normal_c02_composition.C02CompositionFastTest`，**5/5 通过**（`short-tests.log`）。其中新增测试对两个交叉方向分别检查候选、Evidence、Result 重放的拒绝，并检查匹配策略的候选和 Evidence `PASS`；旧 V1 默认候选／Evidence 字节相等测试也通过。这些是短单元测试，不是长材料或真实业务验收。
- `git show ad83fcb:<path>` 对照提交方预提交测试树记录：两份代码／测试、V13/V14 三个 manifest 和三份收据的 SHA-256 全部相等；审阅时上述工作树路径与 `ad83fcb` 无差异。V13、V14 Snapshot 在当前树可加载，`validate_execution_authority` 均通过；V14 `validate_semantic_rule_bindings` 和正式 `validate_wiring_receipt` 通过。当前 V13 closure 为 `sha256:5d75a1a0297b162d5238f9d1569c3677fb89e844b67a127192d2682b3df83d50`，V14 closure 为 `sha256:7e469c866f3b2978f947fe0724f11306480fa9426d522da94b8aabced8777baf`，V14 execution authority 为 `sha256:592f7d3049273bdd2b3b59bbe9a54f02de2cb72c41339a1182328ad686a7be9d`。另两份收据的绑定 hash 与该 authority 一致；本审阅没有把它们各自当作新业务请求已获授权。
- 提交方的定向日志记载 **10/10**，固定 `tokenizers==0.22.2` 环境的快速选择器日志记载 **144/144**；本审阅检查了退出码和逐项返回码，没有重新运行这些较大测试。提交方最终代码的 Macy's 私有无网络更新／冷读日志均退出码 0，同一 Result `sha256:d7eaa03ec66abaf95cb885642145ad9f1687e90f7aa26ab1ffe28ff0f50a38ae` 与同一新 Run ID、Candidate hash 在两份收据相符，首次 `CANDIDATE_READY`、重复输入 `NO_SOURCE_CONTENT_CHANGE`、冷读 `PUBLISHED/EXACT`。这是对提交证据的一致性核对，**不是我重跑的长链**；其业务内容字段仍为 `business_content_acceptance: false`。

## 边界

旧 V1 默认路径及匹配的 V2/V3 入口没有因本差异改变；旧已安装 Run 仍按原安装代码和 Snapshot 读取，不能被新 closure 改签。未独立核读 Macy's 29 个分组内全部董事会事实、其他九家业务含义或当前 390 坐标；未运行真实 SEC／provider 调用，未接触 #47 工作树、账本、PR52。`f4e4c4f` 的原审阅仍是 `NEEDS_FIX`，本次只说明 `ad83fcb` 的限定 API 缺陷已关闭。

工具使用：`functions.exec` 外层 **13** 次、其中嵌套工具 **35** 次，合计 **48** 次；未超出 70 次、90 分钟或消息上限。除本目录的结论与短测日志外，未修改产品代码、执行状态或历史原件。
