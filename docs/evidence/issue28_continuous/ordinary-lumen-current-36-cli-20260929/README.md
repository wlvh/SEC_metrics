# Lumen FY2025：正常入口36项候选与异进程冷读

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认 `tools/vnext_normal_update.py --process --company lumen_technologies`，没有逐项指定申报、金额或答案。私有根 `/private/tmp/issue28-lumen_technologies-current-36-cli-20260929` 不与其他公司、原累计账本或生产active共用。

实际CLI返回码0、状态 **`UPDATES_READY`**、36/36项`CANDIDATE_READY`（`run.exit=0`、`result.json`、`run.log`）。另一个Python进程从盘重新认证同一来源并重放原生Run、Result及公开行：`cold.exit=0`、**36/36**通过（`cold.json`、`cold.log`）。细分为18项`PASS`、16项规则不适用、B06一项`DENOMINATOR_NONPOSITIVE`、另一比率一项`RATIO_NUMERATOR_NOT_POSITIVE`。后两项是同一输入下的有证据状态，不是假造数值或实现失败；C04由普通入口自动选择`C04_REGISTRATION_FOUR_FORM_UPDATE_V1`。

`compare.py`只读对照保留的390索引同36坐标：值、单位、理由、实际期间、质量及适用性 **36/36一致**，Result ID33项相同，B10/B11/C04三项不同（`comparison.json`）。前两项属于较早需求闭包身份，C04此轮走显式后继；旧Result ID与Run未改签。Lumen E01值7符合现行直接Item代码规则，但先前原文核查发现七个计入引用中六个为融资，故“并购公告”的内容解释仍待产品口径决定；这次正常Run不解决该决定。

创建和冷读前后，#28真实`claims.jsonl`、来源请求日志及正式active三者的字节哈希均未改变；新增真实provider/paid/SEC调用 **0/0/0**。这是已保存FY2025来源的私有36项普通更新，不是新财年在线发现、完整39指标公司结果、全部390验收、正式旧入口退出或生产采纳。B13/D03/D04仍为独立责任，未操作#47分支、账本、快照、Run根或PR52。
