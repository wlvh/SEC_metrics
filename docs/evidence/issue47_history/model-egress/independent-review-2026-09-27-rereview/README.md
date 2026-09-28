# 独立安全复审（2026-09-27，对 133a7bd6 + 两个补丁）与逐条处理

**复审是什么**：一个全新上下文的同族子代理（不是人）对上一轮修复与 E01/D02 扩展做的复审，原文见 `report.md`（未改动，只加了抬头）。结论 **PASS_WITH_FINDINGS**，仅限补丁应用在 #47 运行树；明确写了**只凭所有者决定 M3 不能授予真实调用**：先在代码里修 N1、N2，M1 残余、N3、N4 修掉或由所有者明确接受，再重跑 `verify.py` 重新封存。

**这里是什么**：执行者对每一条的处理。每条都先在隔离副本里自己复现（审阅是线索，复现才是事实），修好后配一个具名用例，并在 `verify.py` 里加一个"破坏这一条、应被该用例抓到"的注错。四条需要所有者选择或只能如实说明的限制，单列在最后。

| 编号 | 问题（大白话） | 修法 | 用例 | 注错 |
|---|---|---|---|---|
| N1（高） | 三个公开登记函数接受 `mode="LIVE"`，一次函数调用、没有任何模型调用就能写出"LIVE"登记，默认批次会读它（E01 把扣留窗口发布成 3） | LIVE 登记必须携带回答它的计数调用记录（每个请求一份：意向、终态、线路日志，三者互相点名、终态按字节哈希过它们，调用成功无停止、输出就是登记里的输出、请求就是消费方自己重建的请求的精确字节）；消费方还要求这些调用记在**所有者登记过的批准所授予的账本**里——这份记录只由 `register_model_approval` 从 GitHub 读回批准后写（`granted-model-ledger.json`），测试从不写。新模块 `scripts/vnext/historical_counted_calls.py`，第 45 个规则文件 | 补丁侧：`test_a_live_confirmation_needs_the_counted_call_that_answered_it`、`test_a_live_review_needs_…`、`test_a_live_assessment_needs_…`，运行器用例里的 `check_the_live_registration`；**仓库侧**（CI 跑得到，修复本身就在仓库里）：`tests/vnext/test_historical_counted_calls.py` 7 例（E01/D02 登记与直接写进日志的记录、共享检查的缺块、封印、模式、账本与授予），D04 在 `test_historical_semantic_routes` 的 `test_a_live_record_without_the_calls_that_answered_it_is_refused` | 补丁侧：`A_LIVE_CONFIRMATION_NEEDS_NO_CALLS` 等 3 个、`A_COUNTED_CALL_NEED_NOT_BE_LIVE`、`A_COUNTED_CALL_NEED_NOT_HAVE_ANSWERED_WITH_THIS_OUTPUT`、`A_LIVE_REGISTRATION_NEEDS_NO_REGISTERED_APPROVAL`；仓库侧 13 个，全部被抓（`repository_injections.py` → `repository-injections.json`，同 D02 注错脚本的机制，不写检出） |
| N2（中） | 调用方传进来的许可映射只按三个决策哈希核对，账本根不在其中：换一个根、配一本新账本，就绕过了上限、停止和禁止重抽 | 映射必须与许可文件逐字段相同；账本根和验证收据编号并入控制器绑定的决策哈希；**实时账本**在加锁（写任何东西之前）和每次认领时都从许可文件重新推导绑定并要求就在文件指定的根上 | `AMappingIsNotAnAllowanceAndALedgerIsNotAGrant` 全类 | `A_MAPPING_IS_NOT_HELD_TO_THE_FILE`、`A_LEDGER_A_MAPPING_DESCRIBED_MAY_CLAIM`、`A_CALLERS_ALLOWANCE_IS_TRUSTED`（两道检查一起去掉才算破坏） |
| N3（中） | 所有绑定都哈希 `.py` 源码，而 Python 会运行 `__pycache__` 里按时间戳校验的 `.pyc`：篡改字节码、源码不动，批准外的请求照样发出 | 运行器在导入任何检出代码之前把 `sys.pycache_prefix` 设到本进程新建的私有目录；插座之前（认领前一次、送出时一次）要求每个从检出加载的模块都编译进这个私有缓存，从未读过检出自己的 `__pycache__` | `test_code_read_from_the_checkout_s_bytecode_is_refused` | `CHECKOUT_BYTECODE_MAY_RUN`、`NO_PRIVATE_BYTECODE_CACHE_IS_REQUIRED` |
| N4（中低） | `scripts/` 下新放一个未绑定的 `tokenizers.py`，就把固定分词器遮蔽了：约 42.3 万 token 的请求被规划成 4,097 并发出，所有哈希都还对 | 同一处检查：插座之前，本进程从检出加载的每个模块都必须是控制器授权绑定的文件（测试包除外，运行器从不导入它）。为此把 D04 合成答案挪进独立的测试辅助模块，套件不再顺带加载未绑定的 `historical_model_session.py` | `test_an_unbound_checkout_module_is_refused_before_a_claim` | `UNBOUND_CHECKOUT_CODE_MAY_RUN` |
| N5（低） | D04 批准点名的摘要是 #28 的语义摘要，漏掉了实际发送的若干字段 | 三种合同的摘要统一为**实际发送的请求体字节**的 SHA-256；批准点名什么，发出去的就是什么 | `test_a_digest_covers_every_byte_a_call_sends` | `THE_DIGEST_IS_ISSUE_28_S_SEMANTIC_ONE` |
| N6（低） | 嵌套过深的回答让 `RecursionError` 逃出调用路径，槽位留着没终态、通道被当成"未知"停下 | 回答嵌套过深算合同外的回答（失败终态、计数、不停）；**响应包装**嵌套过深记为 `RESPONSE_UNPARSEABLE`，用量未知按既有规则停止，有终态 | `test_an_answer_nested_past_the_parser_…`、`test_a_response_nested_past_the_parser_…` | `A_NESTED_ANSWER_ESCAPES_THE_CALL_PATH`、`A_NESTED_RESPONSE_ESCAPES_THE_CALL_PATH` |
| N7（低） | 已计费调用之后传输自述与发送字节不符时直接抛错，已付费的原始响应丢失 | 记为 `TRANSPORT_OBSERVATION_CHANGED` 并保留响应，加入停止集合 | `test_a_transport_account_that_disagrees_stops_with_the_response_kept` | `AN_OBSERVATION_MISMATCH_IS_RAISED_PAST_THE_RESPONSE`、`AN_OBSERVATION_MISMATCH_DOES_NOT_STOP` |
| M1 残余 | 同时删掉 `calls/` 和 `claims.jsonl`、保留绑定与锚点，账本读作未用过（2 次上限下认领了 4 次）；截掉最后一个槽位和最后一行日志，停止被解除 | 每次认领先追加（并同步）到**根目录旁边**的日志副本，再写根内日志；根内日志必须与副本逐行相同。SEC 账本同样处理，导出时也核对 | 模型：`test_emptying_the_root_…`、`test_truncating_the_last_claim_…`、`test_removing_the_copy_beside_the_root_refuses`；SEC：`test_an_emptied_root_…`、`test_a_truncated_last_claim_…`、`test_a_claim_log_that_is_not_its_copy_is_not_exported` | `THE_CLAIM_LOG_HAS_NO_COPY_BESIDE_THE_ROOT`；SEC 两个记在 `../../acquisition-wiring/fault-injections.json` |
| M1 未测子检查 | 前驱链、`binding.json` 比较、锚点比较各自去掉时没有用例失败 | 各补一个只违反这一条的用例 | `test_the_claims_must_name_each_other_in_order`、`test_an_edited_binding_or_anchor_is_refused` | `THE_CLAIMS_NEED_NOT_CHAIN`、`AN_EDITED_BINDING_IS_ACCEPTED`、`AN_EDITED_ANCHOR_IS_ACCEPTED` |
| M2 | 严格 JSON 的两个用例只"按消息"失败（复述检查本来就会拒） | 重做成第一轮复审的原场景：后出现的重复值恰好与其余文件一致，只有严格读取能拒 | 两个单元用例与两个出口用例 | 原有 `THE_POLICY_IS_READ_LAST_KEY_WINS`、`THE_APPROVAL_IS_READ_LAST_KEY_WINS` 现在是承重的 |
| L2 | 只在发送点修了；直接构造适配器传输仍能把 #47 请求送到连接器，无槽位、无 WB-3 | 适配器的载荷钩子只在**本线程正在进行的计数发送**持有该请求、槽位仍开着、WB-3 标记已写时才交出字节，无论谁调用传输 | `test_the_adapter_releases_no_bytes_outside_a_counted_send` | `THE_HOOK_RELEASES_BYTES_WITHOUT_A_COUNTED_SEND` |
| 发送点子条件 | 除标记数外的五个子条件一起去掉，实时类全绿 | 抽成函数，每个子条件各有一个只违反它的断言 | `test_the_send_holds_each_part_of_the_reservation_on_its_own` | 六个 `THE_SEND_…` |
| L3（E01/D02） | `_validate_single` 的两个比较各自去掉时用例全绿 | 补一个编辑请求、一个编辑来源的用例 | `test_an_edited_request_or_source_is_refused_before_a_slot` | `AN_E01_OR_D02_SOURCE_IS_NOT_REBUILT`、`AN_E01_OR_D02_REQUEST_IS_NOT_COMPARED` |
| L4 | 单元用例遍历 `STOPS` 本身，删掉一个原因它看不出来 | 用例改为显式列出期望集合并先比对 | `test_every_stop_reason_stops` | — |
| L6（日志） | 套件把 LIVE 登记写进真实日志，被 SIGTERM 中断后残留并被默认读取 | 根本修复是 N1：夹具账本永远不是登记过的批准所授予的账本，残留读不进 Run。另外 SIGTERM 现在像中断一样展开栈，`finally` 与退出钩子清掉夹具；只剩 SIGKILL 会留下，而下次运行会拒绝启动 | 运行器用例断言默认读取拒绝它 | `A_LIVE_REGISTRATION_NEEDS_NO_REGISTERED_APPROVAL` |
| M3 可由代码承担的部分 | 批准只读登录名；应用代发、`author_association`、数字账号、账号类型都不看 | 共享检查加上数字账号 30534800、类型 `User`、关联 `OWNER`（SEC 与模型都适用）；**模型批准**另要求不是经 GitHub App 代发（本环境的代理经 Claude GitHub App 发评论；这是按本环境说明推断的——经 MCP 读回的评论去掉了 `performed_via_github_app` 字段，这里没能直接看到它的值；已直接核对的是：代理发的与所有者本人发的评论，登录名、数字账号与关联字段完全相同）。保存的批准记录带上该字段，离线也能核对 | `test_the_approval_is_the_approver_s_own_post`、SEC 的 `test_the_approver_s_login_alone_is_not_the_approver` | `THE_APPROVER_IS_A_LOGIN_ONLY`、`A_MODEL_APPROVAL_MAY_BE_POSTED_THROUGH_AN_APP` |

**只能如实说明、或交给所有者的**：

1. **M3 其余部分**：任何持有 wlvh 凭据（例如个人令牌）的人都能发出批准；`gh` 取自 PATH 及其配置、代理和 CA 环境；批准点名的收据是否真由验证脚本产生，靠所有者审阅已提交的收据；上限只按次数、不按金额（#28 的 D-36 决定）。这些不是代码能关掉的，需要所有者在调用申请里接受或另选批准方式。
2. **L5（既有，#28 的设计）**：出口门禁按名字静态扫描，`getattr` 拼名能绕过扫描。对 #47 的请求类型，上面的 L2 修法已在钩子处按运行时状态拦住；对 #28 自己的请求类型是 #28 的范围，这里不改也不评论。
3. **能写运行树或账本父目录的人**：日志副本把"清空根目录"变成要同时改两处，但两处一起截断仍然能重置——任何本地账本都做不到防住有写权限的人，外部兜底是服务商账户本身。
4. **#28 的 `CallLedger` 形状相同**（复审顺带指出）：那是 #28 的代码，记录在此供整合时参考，#47 不改。

**修复后的验证自身又查出的四处**（都在封存之前、由测试或注错跑出来）：

1. **验证脚本让一个不是运行器的进程去发请求**。`verify.py` 把 SEC 获取套件里的 GH 读取测试类与出口测试放在同一个进程；那个测试模块导入了来源发现模块（`normal_source_requirements.py`）等调用路径从不导入的检出代码，于是每个实时用例都以 `ISSUE_47_MODEL_UNBOUND_CODE_LOADED` 被拒。检查做对了——它检查的正是发请求的那个进程——错在验证脚本。另测：生产的审批回读导入链（`historical_source_acquisition`）不加载它。改为每个测试模块一个进程（`verify._by_module`），这也是每个套件各自作为自己的运行器。
2. **测试进程的导入顺序与所有者的不同**。运行器在加载时把 `sys.pycache_prefix` 换成本进程新建的目录；测试模块却先导入 `tests.vnext.common` 与一批检出模块、后加载运行器，先导入的模块编译在旧目录，16 个实时用例以 `ISSUE_47_MODEL_CODE_READ_FROM_THE_CHECKOUT_S_BYTECODE` 被拒。生产里运行器是入口、最先执行，不受影响；测试改为第一件事加载运行器，已有检出代码被别的模块带进本进程时以 `ISSUE_47_EGRESS_SUITE_NEEDS_A_PROCESS_OF_ITS_OWN` 具名拒绝，而不是冒出一串误导性的字节码错误。于是"运行器在导入任何检出代码之前设好私有缓存"由套件本身担保，新增注错 `THE_RUNNER_IMPORTS_THE_CHECKOUT_BEFORE_ITS_CACHE`（把设缓存那行挪到导入之后）应被 socket 类抓到。
3. **一个位置跑完之后，下一个位置的发送会再检查同一个进程**：运行器用例在调用、登记、读回一个位置之后再调一次 `loaded_code_holds`，登记与读回途中加载的代码若未绑定，两个位置的运行会在第二个位置被拒，这里先抓到。
4. **L2 修复之后有两个旧用例没跟上**：`test_the_adapter_hands_bytes_only_to_the_named_type` 仍断言直接调用钩子能拿到字节，`test_the_transport_refuses_outside_wb3` 仍断言先碰到 #28 适配器自己的出口令牌检查；修复后钩子在计数发送之外先按 `ISSUE_47_MODEL_TRANSPORT_WITHOUT_A_COUNTED_SEND` 拒绝。修 L2 之后我只按类跑了与它直接相关的几类，恰好没跑这两个用例所在的类；是完整运行的第一步（全量套件）查出来的，而"套件不全绿就停"让这次只花了套件的时间、没有带着两个红用例跑几个小时的注错。用例改为 L2 之后的真实行为：类型不符仍返回 `None` 或按名拒绝，#47 的类型只在计数发送里拿到字节——那由实时用例看着字节到达连接器来证明。

**尚未完成**：修后的完整离线验证（`verify.py`）需要在应用了新补丁的运行树里从头跑一遍并封存，完成后本文件补上结果；在那之前已提交的 `offline-verification.json` 是旧的，实时路径会因为它不绑定当前代码而拒绝（失败即关闭）。
