未应用的输出范围修复建议

基于真实执行 head fce015270de0cc4a265ce0fb0d2179ef11ef98a7；补丁只保存在外部，未修改仓库、已激活 Requirement、原报告、原响应或 Run。

问题：年度检查子步骤的零调用与 NOT_EXECUTED 被复制到 run_once 顶层；成功分支未覆写 execution，失败分支虽然覆写 execution，却仍保留零 provider_paid_sec_calls。真实 WB-3 计数没有归零，本轮实际为1/1/0。

最小建议：把这两个检查事实明确置于 inspection。run_once 顶层 execution 专指本次调用中的候选计算/模型步骤：真实尝试成功或失败由原 outcome决定，正常成功明确EXECUTED；只有发布待办/恢复或无新输入则NOT_EXECUTED。counts继续保留现有整个阶段累计原生计数，不引入另一套预算，也不把累计计数冒称本次增量。本补丁未推导新的每次调用计数。

这只是未来受审版本的源代码候选，已经用ast.parse检查语法，未执行补丁版本、未取得其测试或真实运行信用。应用时必须按治理要求绑定新的受审实现/Requirement，不重写已执行v8，不把fce0152的真实失败证据标成新代码成功。当前模型退役/返回身份问题和错组内容失败都不在此补丁范围内。

必要回归：真实工作流I/O模拟成功时execution=EXECUTED、inspection零调用、counts=1/1；失败时原终态仍失败且inspection零调用不混淆实际counts；同输入重入、pending-only、recovery-only不新增模型；missing-source检查循环后的输出仍有正确inspection范围。原始JSON保留不变，以新的派生审计说明旧字段含义。
