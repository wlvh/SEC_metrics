# D04 公司闭环增量限定独审

结论：发现一项需要修复的 P2，当前 patch 不建议按“当前 D04 实际依赖已完整接入”交付。其余已检查的新增接入未发现阻断问题。此结论仅针对本次增量，不重新审查 PR106 已交付能力或旧解阻。

审查对象：base `cf8e997be3bd0bad77349496ae7e3bf596892d43` → patch `d8c36ca4ab6b0b3d38151bb47f07660f32ceeab9`。开始与最终核对的 HEAD 均为该 patch；源码和 tests 未改动，新增持久文件仅在本 independent-review 目录。

[P2] D04 当前更新漏记实际使用的来源与解释规则，修正这些规则后可能继续复用旧判定。位置：`scripts/vnext/ordinary_current_update.py:67-76`。新增配置虽记录 current_d04_result、r6_semantic_source 和 d04_native_assessment，却遗漏其实际使用的 `going_concern_source.py`、`catalog/r6/going_concern_source_rules_v1.json`、`catalog/r6/semantic_source_v1.json`，以及来源文本覆盖、引用解析、单元恢复等实际执行依赖。`continuous_semantic_calls.prepare_requests()` 调用 `prepare_d04_semantic_source()`；后者在 r6_semantic_source.py:181-185 读取该来源政策并调用 going_concern_source。going_concern_source.py:23-31 使用候选抽取、text_coverage 和语言规则。它们不是未执行的历史权限证明。若这些来源构建或解释规则修正而 SEC 文件不变，configuration 仍完全相等，run_once:234-247 直接返回 PREVIOUS_INPUT_WITHHELD 或 NO_SOURCE_CONTENT_CHANGE，跳过新来源构建和当前语义重验。

复现不修改源码、测试或真实来源，只给哈希读取函数注入单个文件已改变的返回值。dependency-control.json 表明上述来源模块/规则以及 regulatory_investigation_candidates.py、text_coverage.py、capacity_semantic_review.py、invocation_control.py 均未进入 D04 processing_files，单独改变其哈希时配置不变；已列入的 d04_native_assessment.py 则能改变配置。进一步使用真实 _configuration/run_once、显式模拟来源观察和保存记录，得到：首次 CANDIDATE_WITHHELD；改变 going_concern_source.py 的哈希后仍 PREVIOUS_INPUT_WITHHELD、calculation_performed=false、沿用旧 result_id；改变已列入的 d04_native_assessment.py 后才生成新版本。证据见 logs/dependency-control.json 与 logs/dependency-controller-control.json。建议补入本 D04 路线实际执行的来源、解释、重放与政策文件，并加一个“来源构建规则变化会触发一次处理，下一次不变输入又停止重算”的小控制测试。无需重建递归权限树或改变旧调用/失败身份。

本次自行运行的验证：

- 指定 required_unittests 四模块：71 tests、0 failures、0 errors、0 skips，退出 0；进程实测 7.714428901672363 秒，unittest 自报 7.387 秒。日志 logs/required-short-tests.log，命令及进程耗时 logs/required-short-tests-summary.json。
- 11 个有限 replay adapter 合成情形，共 0.016055417014285922 秒：保持原 plan/receipt 身份的正例及仅 validator hash 改变的正例通过；source/request/body 改变、失败 terminal、intent 不一致、plan evidence 改变、retry/reuse 政策改变和语义记录改变均拒绝。真实外层 replay 检查与 revalidation_receipt 执行；底层原响应读取器、语义 acceptor 和 authority context 明确使用替身。这不是完整原执行证明重放。证据 logs/replay-adapter-controls.json。
- 实际配置/更新控制复现耗时 0.03947704192250967 秒；只使用临时合成状态，未读取或写入真实总账。原源码哈希不改。git diff --check 通过。

代码检查边界与已确认行为：current_d04_result 先重建当前完整来源并执行 source_equivalence，再按原 source id 和分组分区选择保存响应；require_complete_assessment 拒绝缺组、失败组、顺序不符、未决分类和冲突汇总。新 replay_original_d04_response 保留原 plan、源/request/body 与接受收据身份，当前语义重验独立登记且 new_provider_execution=false；没有 claim 或 provider 执行动作。collect_native_assessments 的新增选项默认 False，旧路径不改，并限定新选项为 CURRENT_REQUEST_CONFIGURATION_V1 的 D04。D04 普通写入沿既有文本汇总、Evidence、Calculator；SYSTEM 记录明确为机械审阅，不声称 HUMAN 或正式采纳。SecureGPT usage 只读已报告非负整数，缺失/非法计数及费用维持未知，未新增实际 SDK/账户/网络执行。CI 分别纳入新增门禁及响应形状控制。

他人证据边界：本次只读父执行者提交的 README、verified-company-summary.json、independent-results.json、公司 CLI 与单条原响应读回日志等材料。父材料显示 Enphase FY2025 原 173–178 六组、完整 29-unit 范围、Result 7bf9ea83…f99b、原 source/body 等价和新调用 0/0/0；第一次 CLI 为 119.89453425002284 秒、退出 2，底层 WITHHELD/null/D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE，公共行 TEXT_QUAL；重复为 0.163161916192621 秒、PREVIOUS_INPUT_WITHHELD 且不处理，独立 results 读回保存一行及来源范围证据且六个文件未变。这些是父执行者的材料，未在本独审中再次运行真实公司闭环或独立逐字核验真实账本/原件。

父历史驱动最初错期待 exit 0、重复错期待 NO_SOURCE_CONTENT_CHANGE 的断言失败均按历史保留，不能将正确 WITHHELD/退出 2 归为本程序失败。原 helper keyword 及旧 policy view 的失败日志同样保留，不改旧输出。父真实 CLI 记录 commit 6e51f416… 和 dirty=true，发生在当前 base 合入前；它证明当时实际路径，不能冒称 patch exact-SHA 的公司执行或 post-merge 不重算验收。当前 patch 的短测试是本独审自行运行的证据。

未覆盖与限制：按委托跳过 116 秒聚合、120 秒公司完整处理、长材料及完整 CI；未重验全部十公司 D04、原六响应逐字内容、实际账本计数、生产采纳、OpenShift/SDK 网络/认证/费用，也未执行 SEC/model/account 操作。本次结论不授 Ready、merge、生产权限或 390 指标全量信用。

时间与资源：开始 2026-10-09 18:40:31 UTC；结束 2026-10-09 18:47:02 UTC。完整任务 44 次工具调用（19 个 functions.exec 包装及 25 个嵌套工具调用，包含最后状态核对），普通消息 3（开场、一次进度、最终；无问题）。未达到 80 工具/90 分钟上限，未访问 peer 树、未 spawn、commit、push 或修改他人状态。
