# C02 共用选择器定向接入：限定独立审阅

**结论：PASS_WITH_BOUNDS。** 审阅对象是 `c6eac2918aabf5227c0559b07a43f2bce4e3fb73` 相对 `9f8b855f803e4a93d79ed1b1c5f98e22d3413bba` 的 #28 普通 C02 后继增量。所指定的单文件接入、分级候选反例、旧默认路径、当前绑定和 Enphase 私有 Run 身份均得到支持；未发现本限定范围内须修复的阻断问题。此结论不授予 48 条完整业务内容、其余公司、#47 历史结果或生产采纳信用。

## 核对依据

- `scripts/vnext/historical_board_composition.py` 在目标提交的 Git blob 为 `a5f238c61c560daf65affd4aaf3a4e43f7020ca6`，与固定的 #47 提交 `60aa9f7b5b12289c74776f2320bc827d71b7c857` 中该路径的 blob 完全相同；两边原始文件 SHA-256 均为 `a514ceffd0855733222526e38c170840d789b07bcef5e82cda096b4942cf4158`。本审阅没有操作 #47 工作树。
- 对本方保存的 Enphase FY2025 治理来源重新读取选择器：完整文档含 `classified board`，48 个候选排除了原 54 条中的 57、210、212、232、243、2338。原文分别为一类董事的选举议案、三年任期的三人提名，以及各类董事的分组或议案标题；它们不独立给出全董事会人数。块 415 的真实委员会主席卡片仍入选。块 294 的股东沟通内容仍排除。直接反例测试确认分级董事会的候选人数不被标作全体人数；合法的全董事会人数语句在分级状态下仍入选，非分级全体候选人数也可入选。Spec 的变化限于将“总人数”和一类候选数的区别写清，受绑定的原文字节身份已更新。
- 同一本方来源核读表明 Macy’s 块 508 明说每名候选人目前都是董事，Lumen 块 864、Marriott 块 520/521 含董事长与 CEO 的实际职责结构；目标选择器均选入。Macy’s、Lumen、Marriott 当前候选数分别为 99、99、98，超过既有 64 条原生界限；此次没有把它们裁剪成结果。Salesforce 保持 63 条，已登记的内容错误不因本补丁消失。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts python3 -m unittest tests.vnext.test_normal_c02_composition` 在目标提交实跑 **8/8 通过**，含旧默认 C02 candidate/Evidence 字节相等和 Review 函数身份检查。`normal_run_v3.text_api('C02')` 虽选用后继适配器，但旧 Spec 经适配器委托回原 candidate/Evidence；普通更新的显式 `c02_selection_policy` 另行选择新 Spec。`git diff --check 9f8b855f c6eac291` 通过。
- 只读重算 `issue_28_v13` closure 为 `sha256:b9207c3b86f9d4a244ad42342db9b6ffc88de81a3492f6d4111cc83f6730851b`，`issue_28_v14` closure 为 `sha256:c739bea9718e82ab365f1cb5f3d211348dada694ff1f18fd2ea991f974018c8d`，V14 execution authority 为 `sha256:e87277fa6015449b00ff673c45c7684bfee8e897673428edebcc15e7a09e25ac`。当前执行 authority、语义规则绑定及 provider/SEC/普通刷新三份 wiring receipt 的仓库验证器均通过。V13/V14 清单中 C02 Spec 与选择器新 SHA/大小，以及 V14 的父 closure/transfer 绑定，与目标文件一致。
- 对 `/private/tmp/issue28-c02-normal-update-enphase-peer60aa-20261001` 作独立只读冷验：首次 terminal 为 `CANDIDATE_READY`，第二次为 `NO_SOURCE_CONTENT_CHANGE`；保存的 Run 为 `run:ordinary-integrated:c3dad8e56028866ca1a7b63f97c9bf0f0be73ad9dff720168ebea32ccb430beb`，48 条 candidate hash 为 `sha256:df51fb0fb48598a03246f7499e62ff7f5027bff7d1ae2e89baff81e3ced71107`，保存和重验的 Result ID 同为 `sha256:8fb7d6e3ee0a8eeefd58b9187c701b11a3b1bb3aa4954dc339da4b704044f234`。私有原生 Result 内部标记 `PUBLISHED/EXACT`，但其 `production_authorized=false`，不能解释为正式发布或内容验收。旧 54 条私有 Result 身份仍在本方缺陷登记中，新的 48 条明确标为待完整内容验收。

## 边界与审阅操作

本次核对了所列受影响来源片段，没有逐条人工判定 48 个候选的全部业务含义；未复核 #47 全历史样本，也未扩大原生 64 条上限。既有 Salesforce 错误和三家超限属于仍需处理的独立缺口。只读探针最初分别因我传入字符串而非 `Path`、误以为记录类型是 `RESULT` 而失败；修正探针后读取成功，均非产品失败，也未更改运行根。没有真实 SEC/provider 请求、commit、push 或生产指针操作。

工具用量：外层 `functions.exec` **11** 次，内层工具 **29** 次，合计 **40** 次；低于本任务 70 次上限。普通消息 3 条（两次进度说明和最终报告）。
