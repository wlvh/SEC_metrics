# Enphase FY2025：正常入口36项正向候选与异进程冷读

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认的 `tools/vnext_normal_update.py --process --company enphase_energy`。它没有逐项输入财报、单元格、关系或答案，私有根 `/private/tmp/issue28-enphase_energy-current-36-cli-20260929` 与其他公司、原累计账本及生产active隔离。

实际正常CLI返回码0、公司状态 **`UPDATES_READY`**，36/36项为`CANDIDATE_READY`（`run.exit=0`、`result.json`、`run.log`）。另一个 Python 进程从盘重新认证来源与每项原生Run、Result和公开行：`cold.exit=0`，**36/36**通过（`cold.json`、`cold.log`）。20项理由`PASS`，16项有规则依据的`TRAIT_NOT_APPLICABLE`；B06有数值，C04由正常入口自动选择`C04_REGISTRATION_FOUR_FORM_UPDATE_V1`。E01值0仅按现行Item代码路线成立，8.01内容召回仍是独立缺口。

`compare.py`只读对照旧390索引同36坐标：值、单位、理由、实际期间、质量、适用性 **36/36一致**，Result ID33项相同，B10/B11/C04三项不同（`comparison.json`）。B10/B11旧索引属于较早闭包；C04此轮是显式四形式后继，旧索引保留旧身份，不因值相同改签。原#28 `claims.jsonl`、来源请求日志和正式active在创建及冷读前后哈希不变；新增真实 provider/paid/SEC 调用 **0/0/0**。

首次launcher因证据目录写成`ordinary-enphase_energy-...`而在Python启动前失败，没有创建私有根或业务结果；原`launcher.log`保留。修正路径后同一业务计划从尚未执行状态启动，成功日志在`launcher-retry.log`、`run.log`。这不是一次模型或SEC失败。

该证据证明**当前保存FY2025来源的普通36项**可由固定正常入口完成并独立冷读，不是新财年在线来源到达、完整39指标Enphase结果、全部390坐标、正式旧入口退出或生产采纳。尤其 Enphase B13尚无完整真实结果，D03尚无真实公司验收；D04十家候选属于另一条链。未操作#47分支、账本、快照、Run根或PR52。
