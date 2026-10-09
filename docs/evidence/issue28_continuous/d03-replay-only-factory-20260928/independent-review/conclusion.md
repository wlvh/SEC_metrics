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

## `1d017b8f1f4b712aa93c068519a54e4a09e002b4` 增量复审

**结论：PASS_WITH_BOUNDS。** 只复核该提交相对已审 `23243375ddf9143eb2f25405b16527ead330a0cb` 的修补；首轮两个阻断点及错误类型问题在本增量内关闭，首轮其余结论保留原范围。此处 PASS 不授 D03 真实调用、模型语义、原生结果或生产信用。

1. `_execute_semantic()` 现于请求解析后、`build_plan()` 和 `ledger.claim()` 前，按请求本身含有 `source_fact_review_contract` 拒绝执行（`continuous_semantic_calls.py:814-815`），与可复制的 `replay_only` 标志分开。新增真实保存 JPM 来源测试对 `replace(selected, replay_only=False)` 使用隔离录制账本，断言 `D03_SOURCE_ANCHOR_EXECUTION_NOT_AUTHORIZED` 及账本 `[0,0,0]`。独立短检查以录制/真实两种轻量 ledger 对象验证同一拒绝在读取其余账本状态前发生，见 `followup-short.log`；它是控制流检查，不冒充真实账本试验。既有真实批次 D03 禁令仍生效。
2. `SemanticRequest.validate()` 对新合同先要求字典和字符串前驱 ID（第 267-270 行），再按原来源唯一前驱重建完整后继。非字典合同现在得到明确 `ValueError: D03_SOURCE_ANCHOR_REQUEST_NOT_IN_CURRENT_SOURCE`；新增 JPM 测试覆盖 `null`，代码的严格类型判断同样覆盖列表和字符串。它在申领前拒绝，不把旧事实转成确定结论。
3. `regulatory_fact_review.py` 的当前 12,338 字节、SHA-256 `5e65082202f443a3e62b4aa51cb2941dcc5d236bacbde49037f1850afa09d3bf` 已加入 V14 `execution_authority.files`，且 `SEMANTIC_RULE_PATHS` 逐字节核验它。独立只读重验 V14 执行权限、语义文件、provider 接线以及 SEC/普通刷新收据和引用证据，闭包为 `sha256:9563d906e54e5f5cdd9e1dda138c5db49db204cb69de6f4eac680b6f5169a4f1`。首次把此模块加进 `new_rule_files` 的尝试因已批准 `rule_paths` 精确集合而失败，错误留在 `followup-binding-first-failure.log`；最终没有扩大 `new_rule_files`。首轮结论中“也加入 `new_rule_files`”的具体建议过宽，本次执行绑定与语义核验已满足该依赖的可追溯性。V13、批准配置和 `regulatory_fact_review.py` 本身相对已审提交均无差异。
4. `prepare_requests()` 默认签名与主体没有增量变化；新执行禁令只匹配 D03 后继合同，有效 B13/D04 请求不含此字段。本地提交方 `followup-targeted.log`/`.exit` 报 JPM 1 项 188.363 秒成功，`followup-fast.log`/`.exit` 报固定树 135/135 selector、200.057 秒通过；均只读采纳，未重跑长测试。新 SHA 远端 CI、D03 原生 Candidate/Review/Result/Run、真实调用资源及公司级结论仍须分别验证。

本轮只追加本段和 `followup-short.log`；未改业务代码、原账本、历史授权或 `#47`/PR52。
