# Ford FY2025：正常入口34项继续完成，B03失败与B06扣留保持

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认的 `tools/vnext_normal_update.py --process --company ford_motor_company`。私有状态根 `/private/tmp/issue28-ford_motor_company-current-36-cli-20260929` 与原累计账本、其他公司和正式active隔离。

实际普通CLI返回码2、公司状态 **`UPDATES_PARTIAL`**：36项中34项`CANDIDATE_READY`；B03为`EXECUTION_FAILED`，确切错误`B03_CURRENT_SOURCE_SCOPE_UNRESOLVED:SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT`；B06为`CANDIDATE_WITHHELD`（`run.exit=0`、`result.json`、`run.log`）。封装脚本退出0只表示它如实保存了这些状态，不能把部分完成称为全通过。B03保存的原生Result仍是历史ID `sha256:1829d73dac66a195a590ab84ea1f1d1800a77fae60d828b6f37d5cbeec2abd30`，但当前成功指针为空；B06原生Result为`WITHHELD/null/B06_SOURCE_RELATIONSHIP_UNRESOLVED`，同样没有成功指针。Ford原年报中所选折旧总额含减值相关折旧的限定原件证明见[先前来源审计](../b03-ford-impairment-scope-20260929/README.md)，本轮没有用约数倒减、重标旧成功或猜工业权益。

`cold.py`在另一进程重新认证同一来源快照并核对保存的36个终态：34条成功Run的Result和公开行、B06扣留Run/行字节及无成功指针、B03已保存历史Result的原身份和原行字节，以及**重新从保存原件**计算的`SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT`来源冲突。`cold.exit=0`，36/36状态重验通过（`cold.json`、`cold.log`）。B03重放到历史Result并不恢复当前业务信用；其终态仍为失败、成功指针仍空。创建和冷读都禁止116个旧语义生产导出。

`compare.py`只读对照保留390索引：35个有当前Result的坐标，其值、单位、理由、期间、质量和适用性 **35/35相同**；B03旧索引数值故意不作为当前可比成功结果，`noncomparable_status_count=1`。Result ID32项相同；B03因当前拒绝无成功Result，B10/B11来自较早闭包，C04此次自动选四形式后继，均不改签旧身份（`comparison.json`）。

原#28 `claims.jsonl`、来源请求日志及正式active在创建及冷读前后哈希均未改变，新增真实provider/paid/SEC调用 **0/0/0**。此项证明固定正常入口能够把一个指标的已知错误接受局部阻断，同时独立交付其他34项；**不**证明Ford B03/B06已解决、新财年在线更新、完整39指标公司结果、全部390坐标或旧入口正式退出。B13/D03/D04另验。未操作#47分支、账本、快照、Run根、PR52或生产。
