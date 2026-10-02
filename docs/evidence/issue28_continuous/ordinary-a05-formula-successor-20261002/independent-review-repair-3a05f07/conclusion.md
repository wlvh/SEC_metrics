# A05 结构性不适用回修：限定独立审阅

**结论：PASS_LIMITED。** `3a05f07ce49cb640f8a1155a16aba40b47abbfdd` 相对父提交的差异修复了首审指出的合法 `PUBLISHED/N_A_STRUCTURAL` 误拦截。原 `489659e5` 首审的 `NEEDS_FIX` 保留原义；本结论只覆盖此次回修及其必要接口，不批准整个 A05、390 坐标或生产发布。

`ordinary_projection.render_ordinary_run()` 现在把两种已发布结果分开：结构性不适用须为 `NONE`、空值、`TRAIT_NOT_APPLICABLE` 且无选中观测，不写数值公式；有数值结果仍须 `APPLICABLE/EXACT`、唯一 `average_assets` 观测。该严格性与当前 A05 目录的唯一 `average_assets`、`EXACT` 分支一致。默认 `presentation_policy=None` 路径在本补丁中没有变化，旧 `_binding()` 的逐字节对照和旧安装代码回读继续适用。错选数值分支的定向负例仍得到 `ORDINARY_A05_SELECTED_BRANCH_CHANGED`；注入结构性不适用的假观测得到 `ORDINARY_A05_STRUCTURAL_RESULT_CHANGED`。后者是隔离注入验证，不是对一个真实篡改 Run 的重放。

我亲自运行了 `python3 -m unittest tests.vnext.test_a05_formula_successor`，2/2 通过；亲自加载并验证当前 V13/V14 执行权限，闭包分别为 `sha256:bedb8ed3…`、`sha256:aba2bdaa…`，当前投影文件 SHA256 为 `fa9643e8…`，与提交及运行记录一致。亲自读取私有原生 Run/行文件：Marriott 的 `N_A_STRUCTURAL` Result `b603a640…` 为 `PUBLISHED/NONE/null`，公开值和公式均空；JPMorgan 的 `APPLICABLE/EXACT` Result `b4af4d3b…` 保留 `0.01353819078340816975991354239`，新行展示批准公式；两份 Run 的 `validation.json` 均为 `NOT_RUN`。

我检查了提交方的保存来源材料测试日志：2/2 通过，23.318 秒的单项选择器低于其 240 秒限时；没有重复执行这份材料。正常 CLI 的禁网脚本实际调用 `vnext_normal_update.main --process`，保存记录显示 Marriott 初次 `CANDIDATE_READY`、重复运行 `NO_SOURCE_CONTENT_CHANGE`、Result 与行身份不变、无第二个 Run。JPMorgan 当前数值路径、错分支拒绝及旧 Run 冷读依据提交方既有原始日志与本次记录核对，并未由我重新跑长链。三份收据在本提交只随父子闭包重绑；哈希有效不等于在此树上重做 provider/SEC 工厂到控制器的禁网接线，下次真实请求仍要按最终绑定检查。

本补丁只修改 `ordinary_projection.py` 的显式 A05 投影分支；V13/V14 的未冻结执行绑定及父级身份相应更新，`tools/run_fast_tests_v2.py` 只在选择器列表末尾加入材料测试。历史 Result/Run 不改签。本次无真实 provider、付费或 SEC 调用；私有 `OPEN/NOT_RUN` 候选不取得正式 390、完整自动更新或生产信用。更多指标、整个 PR 及业务值原件语义不在本次增量独审范围。

审阅工具调用：9 次外层 `functions.exec`，30 次内层工具，合计 39 次；普通消息 3 条（两条进度、一份最终）。没有子代理、commit、push或操作 #47。
