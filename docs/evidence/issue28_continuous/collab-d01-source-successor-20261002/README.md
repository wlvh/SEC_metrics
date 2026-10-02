# D01：原文标题的显式后继来源路径

本次固定读取 #47 的 `2b4f571ef18274299145c63b4c355aa97c45d030`；其 D01 来源读取及原生验收思路分别在 `scripts/vnext/historical_text_emphasis.py`、`historical_risk_results.py`。#28 针对当前年度新建 `d01_emphasis_source.py` 和 `d01_emphasis_results.py`，只在 `D01_EMPHASIS_SOURCE_V2` 明示输入绑定下使用；未选此路径的旧 D01、C02/D02 和冻结 V12 文件不改。后继把下划线、加粗字母之间的短标点、以及受限的跨页标题接回原文；仍由原 `risk_factor_headings` 决定标题，原始资产、来源身份、期间、整节范围及每条原始字节 span 仍逐次重建和核验。

直接对 #28 十家当前保存的年报比较：仅 Marriott FY2025 与 Paramount FY2025 的 D01 标题集合改变。Marriott 旧 34 条少了四条原文下划线风险类别标题；Paramount 旧 38 条里一条在 `U.S.` 的第一个句点前截断，新候选为完整原文。其余八家在这项来源规则下的候选标题文本无差异；这不是八家公司全指标的内容验收。`measure-current.json`、`audit-marriott.json` 和先前 `collab-d01-paramount-20261002/audit.json` 保存本方原件及旧 Result 身份。Marriott 旧 Result `sha256:6077181e…` 与 Paramount 旧 Result `sha256:a7a52ae7…` 均仍保留，并从本方当前可信结果统计扣除；两者原有 Run 和390分母不改。本次已核对的撤回范围为12个坐标／18个精确Result身份，包含其他已登记缺陷。

两个受影响公司在禁网私有普通更新中各产生完整新 D01 原生 Run，第二次触发返回 `NO_SOURCE_CONTENT_CHANGE`；各由独立进程回读来源、结果和状态。Paramount 新 Result `sha256:6795449b…`，Marriott 新 Result `sha256:99c76e50…`。它们是原生程序闭环与原文增量证据，尚不是当前390或生产采纳。程序试运行后只调整了新文件的说明文字，导致绑定身份变化；最终绑定下另有 Paramount 原生更新及冷读，结果内容身份相同、Run身份不同。修前后绑定和接线收据均记录，旧包不改签。

测试分层：`test_d01_emphasis_successor.py`四项检查正向标题、普通加粗句不粘正文、跨页只接合符合边界的段落、原始来源篡改拒绝及默认旧路线；fast suite 145/145通过。两家公司在最终V13闭包 `sha256:07704504…` 下各自完成禁网私有更新／冷读，V14闭包 `sha256:499cc1d7…` 及三份接线收据通过。独立限定审阅仍待精确补丁SHA，不将本地测试写成独审。完整390重新汇入及生产操作仍需另行验收和权限；af9旧head主CI成功不覆盖本补丁。本次真实 provider/paid/SEC 调用均为0，原账本保持195槽／143、143、52。共享接口新增参数有默认值；默认 `prepare_case`、`install_normal_inputs`、`create_normal_run`、`prepare_current_source_case` 不选择新路径。D01 的正常更新入口明示选择，#47 自行决定其历史分支接入，本方未操作对方工作树、账本或运行根。
