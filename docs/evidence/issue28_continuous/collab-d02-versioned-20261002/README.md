# D02 Item 8 类别提及：固定共享规则接入本方普通后继

固定读取 #47 已推送的 `36c64ab6`：它把先前 `104876d6` 的类别提及规则接入历史实际选择入口。GitHub 精确内容 API 核对这两个提交中的规则、词表 Git blob 未变，分别是 `7c02380e…` 和 `03e35435…`。本机 Git HTTPS fetch 在 remote-helper 阶段超时，故本次远端增量使用服务器 compare/内容 API 固定读取，不能说本机跟踪引用已更新。`verify_peer_copy.py`证明本方 `d02_item8_category_28_v1.py` 与词表仅把相互引用路径改为本方专用、版本化文件；正则和判定算法字节一致。本方未导入 #47 历史选择器、Requirement 或运行根。

已冻结的 `text_results_v2.py` 起初被错误尝试直接增加参数，V12 父级身份校验立即拒绝，原失败见 `binding.log`。**该文件已逐字节恢复**；正式后继使用新的 `d02_text_results_v3.py`，原正常入口未显式选择时的候选字节仍等于 V2。V13/V14 仅重绑本任务未冻结需求及必要父子依赖，三份现有接线收据只更新匹配的完整执行身份；它们不替代下一次真实业务调用前所需的禁网工厂／控制器实跑。旧包、旧 D02 Run/Result 和共享函数默认参数不改。

本方普通 CLI 对新 D02 更新明确选择 `metrics/D02-item8-v1`。禁网、禁旧语义生产、独立状态根的 Lumen FY2025 运行生成新私有 Result `sha256:da6c0000c7c45b04c2dec00927bcbf94de959d8270199a07c2bc89704a68411c`：已选摘录由15减至14，原 Item 8 块1670不再入选，原生 Evidence `PASS`，公开行由当前 Run 渲染。另一进程从安装副本重读后报告 `NO_SOURCE_CONTENT_CHANGE`，不创建第二个 Run；原账本 claims、来源日志和 active 指针哈希均未变化，真实调用0/0/0。创建和冷读分别见 `run.json`、`cold.json`，状态为私有 `OPEN/NOT_RUN`，不是正式采纳。

定向真实保存来源测试覆盖 Lumen1670、Pfizer2175/2240、Paramount2257 的精确移除、Paramount2108真实诉讼收益保留、Enphase755 Item 3 页脚**仍未修复**、旧默认候选相等、旧候选在新证据合同下拒绝、D03同一来源提案不变。首次增加D03断言时误把 `compiled_spec` 传给内部来源函数，日志 `directed-final.log` 保留；修正测试调用后 `directed-repair.log` 2/2通过。Lumen私有Run只是程序重放和来源字节一致；14条内容及完整漏选方向尚未独立验收，其他三家公司也未产生新原生 Result。#47 自己的留出阅读仍留下许多非披露误纳，本方不能把这次部分排除当成完整 D02 能力。四个旧错误 Result 在 `known_result_defects.json` 继续按精确身份扣留，新私有 Result 不领取390或生产信用。

停用前代码树的 fast 选择器146/146通过（`fast.log`，59.274秒），并仅在实际新来源材料上跑了上述2项定向测试；未重跑未受改动的旧大材料。停用后的绑定、短测、受影响快测和新增差异独审分别记录，不能把旧快测或先前私有Run写成最终树验收。

**独审后的安全停点：**精确补丁 `de22326d` 的[限定独审](independent-review/conclusion.md)发现共用规则本身的 P2 误删反例：`We face litigation, which could result in a significant loss.` 中关键词后的单个逗号被当成列表证据，`left_out=True`，尽管它是对本公司诉讼的实际陈述。此句是合成反例，不在已核的四份原件中；四处原件排除仍正确，但**通用选择规则不能因此取得验收**。旧独审结论保留，复现已直接通知 #47 共用修复负责人（[评论](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5948676381)）。本方没有另写一套竞争的词法核心。

修后只在普通新 Run 与更新入口加停用门：`d02_category=True` 在写 Run 或更新状态前明确拒绝；`_create_case_run` 也拒绝直接绕过。`guard-existing.py` 对先前的 Lumen 私有成功指针重入返回 `UPDATE_BLOCKED`，指针哈希不变、没有新尝试/Result；之前的私有Run/记录仍可独立读取，**其 `PUBLISHED/EXACT` 只是当时程序通过，不转为当前内容信用**。冻结 V2、旧默认和其它指标路径不受此门影响。`binding-before-gate.json`/`binding-after-gate.json`分开保存停用前后V13/V14身份，不能把停用后的闭包写成此前 Lumen Run 的创建身份。修后新增短测和受影响快测/独审分别登记，不重做上述保存原件长链。

停用门后的单项短测 `guard-short.log` 1/1 及最终树 fast `fast-gate.log` 146/146（57.748秒）均通过；先前保存来源定向2/2和Lumen创建/冷读只对停用前源码成立。[`0ccf5363`限定独审](independent-review-gate-0ccf536/conclusion.md)只对停用门给出 `PASS_GATE_ONLY`，原 `de22326d NEEDS_FIX` 不变。审阅者独立检查旧成功指针重入、三处前置拒绝和V13/V14身份；没有重新运行长链、完整读取14项业务内容或核验最终head CI。最终head CI仍待远端终态。

本次没有改变 D02 业务定义、模型／SEC预算或生产权限。后继接收若规则字节改变，需要重新核对本方固定副本的实际差异与来源；不自动追平对方历史分支。
