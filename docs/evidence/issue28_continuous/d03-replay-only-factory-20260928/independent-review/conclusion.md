# D03 回放专用请求工厂：限定独立审阅

**结论：NEEDS_FIX。** 审阅对象为 `23243375ddf9143eb2f25405b16527ead330a0cb` 相对 `f6e9e8863f2f25f9955f512e035da1fe7db1618a` 的指定增量。当前保存来源上的正向结果、旧事实降级、原入口兼容和现有真实批次 D03 拒绝均有依据；但“回放对象不能录制执行”和“后继生成规则由 V14 执行闭包绑定”两项主张尚不能成立。此结论不改业务代码，不授权真实调用或原生结果信用。

## 阻断问题

1. **`replay_only` 是可改写的数据字段，后继请求的录制执行没有结构性禁令。** `prepare_d03_replay_only_requests()` 在 `continuous_semantic_calls.py:395-398` 设 `replay_only=True`；`_execute_semantic()` 在第 807 行只检查这个字段。`SemanticRequest` 是 dataclass，仓库自身在同一文件第 505、519 行使用 `dataclasses.replace()` 保留 `_factory` 身份并替换字段。因而调用者可对本次后继对象执行 `replace(selected, replay_only=False)`；第 263-272 行的后继验证仍会按来源重建并接受相同请求，而第 807 行的禁令失效。随后录制入口可进入普通计划和账本路径，是否完成仍取决于其余计划、响应和账本条件。新增测试只对原对象以 `ledger=object()` 断言禁令，未覆盖这一变体或真实录制账本。当前**真实**路径另有 `RECOVERY110_FOLLOWING_METRIC_FORBIDDEN` 和 Batch33 D03 禁令，不能据此声称真实调用已可发生。最小修复是在请求验证及执行入口按 `source_fact_review_contract` 的请求形状强制禁止执行，直到另有明确 D03 授权；补一个 `replace(..., replay_only=False)` 负例，在任何 claim 前拒绝。

2. **用于认证后继请求的代码没有进入 V14 执行绑定。** 新增的第 265、382 行直接调用 `regulatory_fact_review.candidate_request()`，其逻辑决定旧事实是否被移除、来源锚点、请求 ID 和响应协议；但 `scripts/vnext/regulatory_fact_review.py` 既不在 `SEMANTIC_RULE_PATHS`，也不在 `requirements/issue_28_v14/baseline_manifest.json` 的 `new_rule_files` 或 `execution_authority.files`。独立只读重验当前 V14 闭包 `sha256:2731935de44d0f123a76f301a1744cc9fb7f83a08e4e89f44f654004207c4168` 与三份接线收据及其引用证据均通过，同时确认该模块的执行绑定为 `False`。所以这些成功校验只覆盖已列文件；`candidate_request()` 字节改变不会使这条 V14 校验失效，也不会收入执行规则归档。应把此直接依赖纳入 V14 执行和语义规则绑定，重算闭包及三份收据，再做只读核验。不要把当前接线日志的 PASS 扩展为该模块已绑定。

## 其他边界与已核对事实

- 第 264-269 行直接对 `request['source_fact_review_contract']` 调 `.get()`。若该字段被改为列表、字符串或 `null`，会抛 `AttributeError`，而不是项目的 `ValueError` 拒绝原因；它在请求申领前失败，未发现错误接受。建议先严格检查 `type(contract) is dict`，补错误类型负例。
- `prepare_requests()` 原函数签名与主体未变；有效 B13/D04 请求不带 D03 的新字段，新分支不会改变其正常验证。新工厂复用 D03 当前来源分组，`r6_regulatory_semantics.requests_from_source()` 已按 `required_unit_ids` 核对原分组，第 390-402 行又核对每组单元与必评集合及全量单元顺序。`candidate_request()` 在确有旧事实的组移除 `source_statement_facts`，只保留锚点供逐候选审阅；它不产生事实结论。此判断限于该提交的实际代码与已保存来源，不是模型语义证明。
- 只读检查提交方 `targeted.log`/`.exit`：JPMorgan 保存来源 38 组、唯一后继组、前驱 ID 篡改拒绝和原对象执行拒绝，1 项 168.866 秒通过；没有重跑。`fast.log`/`.exit` 为 135/135 selector、201.743 秒、退出 0；它是本地测试而非新 head 远端 CI。独立重跑获准的短反例 1 项通过，见 `short-negative.log`。三份当前收据的执行权限哈希与 V14 闭包匹配；SEC、普通刷新引用证据哈希也只读核对通过。
- 原账本和真实 provider/SEC 没有在本次审阅中操作。D03 仍无真实请求、Candidate/Evidence、Review/Result/Run 或公司结论信用。`#47`/PR52 不在本次审阅或写入范围。
