# Pfizer FY2025：同一正常入口的36项私有运行与冷读

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认的 `tools/vnext_normal_update.py --process --company pfizer`，没有逐项指定数值、单元格或申报文件。私有状态根为 `/private/tmp/issue28-pfizer-current-36-cli-20260929`，与真实累计账本及正式active隔离。

实际普通CLI为 **`UPDATES_PARTIAL`，返回码2**：36项中35项`CANDIDATE_READY`，B06一项`CANDIDATE_WITHHELD`。外层验收脚本的`run.exit=0`只表示它如实保存并核对了这一部分完成状态，不能代替正常CLI的返回码。B06没有成功指针；其保存原生Result为`WITHHELD/null/B06_SOURCE_RELATIONSHIP_UNRESOLVED`，没有因金额较小或概念名称被改判通过。完整逐项状态见`result.json`，原始标准输出末尾见`run.log`。

`cold.py`在另一个 Python 进程中重新认证同一来源快照，在同样的禁网、禁旧导出条件下重放35条成功Run的Result及公开行，并单独核验B06最新扣留Run、原始输入描述、Result/行字节和没有成功指针。`cold.exit=0`，**36/36**保存状态重验通过，调用记录为0/0/0（`cold.json`、`cold.log`）。原#28 `claims.jsonl`、来源请求日志和正式active三者在创建及冷读前后哈希均保持不变。

随后`compare.py`只把当前私有结果的业务字段与保留的390索引同36坐标比较：值、单位、理由、实际期间、质量和适用性 **36/36相同**；Result ID有33项相同、3项不同（`comparison.json`）。B10/B11的旧索引来自更早需求闭包下的非住宿结构适用状态；当前C04由正常入口自动选择`C04_REGISTRATION_FOUR_FORM_UPDATE_V1`，旧索引来自较早普通批次。这里只陈述可见身份和路线差异，不据此把旧索引重新签成当前版本或宣称所有历史输入字节等同。

第一次将`nohup`命令脱离终端的启动没有留下活进程或退出收据，空`run-first.log`、`launch-first.log`和`launch-first.pid`原样保留；随后由可追踪会话启动并完成。它们不是一次业务失败或真实模型请求。此次实际 provider/paid/SEC 新调用 **0/0/0**。这是已保存FY2025来源的私有正常更新与冷读，不是新财年在线发现/获取、全部十家公司390坐标验收、完整39指标公司结果、正式采纳或旧入口全面退出；B13/D03/D04另有独立责任。#47分支、账本、快照、Run根及PR均未操作。
