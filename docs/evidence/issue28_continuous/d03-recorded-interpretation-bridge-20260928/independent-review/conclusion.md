# D03 录制整组解释桥：限定独立审阅

审阅对象：`8a49b5ab566c755d3d60a9db7bb5ef24f5a55ac0`，基线 `c1e96fe43ddb2a229108ab7bf5e9c325e712b930`。只审新增桥接函数、对应短测试、fast selector，以及本目录提交方证据。结论：**限定通过；未发现本增量的阻断缺陷。** 此结论只认可离线录制包到解释提案的绑定，不认可 D03 业务结论、真实 provider 执行、原生 Candidate/Evidence/Result/Run 或生产使用。

## 核对结果

- 外部指定的 `expected_packet_id` 先进入 `replay_offline_set()`。旧重放器核对包内容哈希、录制用途与零调用标志，逐一核对来源和响应原字节、原请求集合及每组响应内容；随后新增桥接函数核对包 ID、公司、当前重建来源 ID、组数、原请求 ID 完整集合与有效请求 ID 唯一性。缺组或多组不能进入解释。
- 每组响应按当前准备结果的 `original_request_id → effective_request_id` 映射，再交给原 `validate_complete_interpretation()`。它重新准备同一公司的完整输入，检查所有有效请求都有且仅有一份字节；旧来源事实组还用 `validate_candidate_response()`重建并核对后继请求，普通组用原请求校验。错组响应须同时通过这些请求内身份和内容校验；未见仅凭字典键就接受的通路。
- 桥接返回的执行身份和原生结果标志是 `false`，调用数为 `[0,0,0]`；还明确检查解释提案没有 Candidate/Evidence/Result/Run 信用。新增函数没有调用真实请求或原生登记入口。旧 `validate_complete_interpretation()` 函数体和默认返回结构未改；fast runner 只追加一个 selector。所审差异没有修改真实调用权限配置。

## 验证与范围

- 独立运行指定短测试：1 项通过，见 `short-test.log`；`git diff --check` 对本审范围通过。
- 提交方记录显示同模块 3 项通过、fast 135/135 通过；Marriott 保存包 5 组均返回未决且错误外部包 ID 被拒，见上级目录的 `module-test.log`、`fast.log`、`run.log` 和 `receipt.json`。这些长材料和原保存包本次只读收据，未重跑，也未把收据改称独立实测。
- Marriott 的 5 组均无后继请求。新增短测试的“原 ID 不同于有效 ID”分支将包重放器和完整解释器都替换成模拟返回，所以它直接证明桥接映射和缺组/伪信用拒绝，但不构成真实后继录制包的整条冷读验证。代码交叉核对未发现该边界的错误接受；后续若将桥接用于原生执行，需在对应实际后继包和原生链上另验。
- 未运行 fast 全套、保存 Marriott 包、真实 provider/SEC 请求或原生 Run；未修改业务代码、账本、Issue #47/PR #52、分支或权限。独审只写本 `independent-review/` 目录，未打包。

底层工具调用：**35 次**；在 80 次及 90 分钟硬上限内。
