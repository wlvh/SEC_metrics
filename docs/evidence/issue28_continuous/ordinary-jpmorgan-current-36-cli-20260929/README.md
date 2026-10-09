# JPMorgan FY2025：正常入口35项继续完成，银行B06扣留保持

在产品代码 `c88ed896`、当前 V14 需求闭包和已认证的 #28 来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228` 下，`run.py` 禁网、禁116个旧语义生产导出，调用默认的 `tools/vnext_normal_update.py --process --company jpmorgan_chase`。它与先前JPM单项来源材料测试不同，是同一正常入口处理36项的独立私有状态根 `/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929`；没有重跑此前已通过的大材料作业。

实际正常CLI返回码2、状态 **`UPDATES_PARTIAL`**：35项`CANDIDATE_READY`，银行B06一项`CANDIDATE_WITHHELD`；外层`run.exit=0`只表示它如实保存了该部分完成状态（`result.json`、`run.log`）。B06原生Result为`WITHHELD/null/B06_SOURCE_RELATIONSHIP_UNRESOLVED`，当前成功指针为空，没有把已识别融资分项小计或缺少单独融资租赁披露升级成完整债务比值。

`cold.py`由另一Python进程重新认证来源，从盘重读35条成功Run的Result与公开行，并单独重放B06扣留Run、原输入描述、行字节及无成功指针：`cold.exit=0`、**36/36**保存状态通过（`cold.json`、`cold.log`）。细分24项`PASS`、11项规则不适用、B06一项有证据扣留；C04由正常入口自动选择`C04_REGISTRATION_FOUR_FORM_UPDATE_V1`。

`compare.py`对保留390索引只比较当前业务字段：36项的值、单位、理由、实际期间、质量和适用性 **36/36相同**；Result ID只有12项相同，24项不同（`comparison.json`）。旧索引对这24项分别引用早期340批次12项、文件身份恢复3项、旧住宿闭包2项和历史/注册事件身份恢复7项；新私有Run按当前来源及代码产生自己的Result身份。这项对照**不证明**24项旧新来源/trace字节等同，也不把旧Result重签为当前版本；当前Run的原生保存验证和历史索引的旧身份分别保留。银行B06仍属于未完成的业务坐标，而非新增“披露不足”答案。

创建和冷读前后，#28真实`claims.jsonl`、来源请求日志和正式active指针哈希均不变，新增真实provider/paid/SEC调用 **0/0/0**。这验证已保存FY2025来源下，银行一个局部B06未决不阻断其余35项正常更新；不是新财年在线来源到达、完整39指标公司结果、全部390坐标、正式旧入口退出或生产采纳。B13/D03/D04仍另验。未操作#47分支、账本、快照、Run根或PR52。
