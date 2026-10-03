# Macy’s FY2025：正常入口36项正向候选与异进程冷读

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认的 `tools/vnext_normal_update.py --process --company macys`。没有逐项指定申报文件、单元格或答案。私有状态根 `/private/tmp/issue28-macys-current-36-cli-20260929` 与原累计账本、其他公司及正式active隔离。

实际正常CLI返回码0、公司状态 **`UPDATES_READY`**，36/36项为`CANDIDATE_READY`（`run.exit=0`、`result.json`、`run.log`）。另一 Python 进程在同样的禁网、禁旧导出条件下重新认证来源，从磁盘逐项重放原生Run、Result及公开行：`cold.exit=0`，**36/36**通过（`cold.json`、`cold.log`）。其中20项理由`PASS`、16项为经规则确认的`TRAIT_NOT_APPLICABLE`；B06是有数值的正向结果，C04由普通入口自动选择`C04_REGISTRATION_FOUR_FORM_UPDATE_V1`。这证明资料充分时该公司36条普通路线能在固定实现下完成，不是通过普遍扣留制造通过。

`compare.py`只读对照保留的390索引同36坐标：值、单位、理由、实际期间、质量和适用性 **36/36相同**，Result ID有33项相同、B10/B11/C04三项不同（`comparison.json`）。B10/B11原索引来自较早需求闭包下的结构不适用结果；C04旧索引来自较早普通批次，而此次走显式四形式后继。没有用业务字段相同重新签署旧结果，或把当前私有Result算成额外390坐标。E01仍按现行Item代码规则计数；其“并购公告”内容含义和8.01召回另待验收。

创建及冷读前后，#28真实 `claims.jsonl`、来源请求日志及正式active指针的字节哈希均不变；新增真实 provider/paid/SEC 调用 **0/0/0**。此项是**已保存FY2025来源的私有正常更新**，不是新财年在线发现/获取、完整39指标公司结果、全部十公司390验收或正式旧入口退出。B13/D03/D04仍独立。未操作#47分支、账本、快照、Run根、PR或生产。
