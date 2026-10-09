# 08915a83 Ford B03 限定差异独立审阅

**结论：PASS_LIMITED（代码与绑定）**。本结论只覆盖 `08915a83f10b97d2bdef9e6b17f64307a56fb4ce` 相对父提交的 B03 来源判断、显式 B03 更新入口、对应测试及 V14 当前绑定；不证明 Ford 存在可替代的 B03 数值，也不批准完整 390、发布或生产切换。

我独立读取原 Ford FY2025 10-K 的已保存原件，重算其 SHA-256 为 `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`。解析出的第 3180 个内嵌 XBRL 事实是 `us-gaap:DepreciationDepletionAndAmortization`、`c-1`、`15,974`（scale 6）。它位于 `table_000148` 的“Depreciation and tooling amortization”行；原始单元格依次为 3,188、565、1,397、2,589、8,235、`(g)`、15,974，前五项精确相加等于总额。紧随该表的原始 `(g)` 脚注明确称其中包括 81 亿美元与 Model e 资产减值有关的折旧；脚注原始字节区间 `[5176658,5177247)` 的 SHA-256 独立复算为 `ec9bc58141f6e006e6bf928207bc6c5741a525c88b6152d210b2e1ccf35ae1f0`。代码要求内嵌事实、同一行加总、组件后标记、唯一相邻脚注和原始字节同时成立，足以支持**撤回当前 B03 信用**，并未凭四舍五入的 81 亿美元造新数。

负例把原脚注的 `Includes` 改为 `Excludes` 后只用于隔离验证，不冒充 SEC 原件。此前 Salesforce 固定资产子集、Southwest 正常路径、Ford 当前失败以及旧成功只留历史、不变成当前候选，在提交方定向和材料日志中各有记录。我只运行了 `B03HistoricalRecoveryVerifierTest` 的 2 项短测试，均通过；原件结构解析与哈希复算也由我执行，输出在 `review.log`。6 项定向、5 项来源兼容、Ford/Southwest/Salesforce 材料、141 项 fast，以及 B03+C04 录制链与冷读均**只核读提交方日志**，未由我重跑。

新的 `_verify_candidate()` 与冻结 `ordinary_update_cycle._verify_candidate()` 逐项对照：同样核对终态和配置、完整 Run 重放、唯一主结果、Result ID、完成状态、公开行字节及哈希、输入描述；显式 B03 路径额外检查公司、指标和原来源范围。`render_ordinary_run(..., _return_replay_context=True)` 返回的是本次完整重放中已得到的 manifest、records、case；独立后续调用仍从磁盘重新重放。历史恢复只在上述机械检查完成后捕获 `B03CurrentScopeConflict`，保留旧 Result 和指针；当前候选检查仍拒绝这份旧信用。冻结普通默认入口及 V13 未改。当前 V14 两份变更文件的大小与摘要、需求加载、执行权限和三份接线收据由我再次只读核验通过，闭合身份为 `sha256:1a72dda1f2254fe43b1096b0f09d5eb99ff334b56149d6648ab8c8008141ed67`。

**提交前的小修整：** `git diff 08915a83^ 08915a83 --check` 唯一提示是新增证据文件 `profile-summary.log` 第 44 行末尾多一个空行。这不影响代码审阅结论，但推送前应在后续追加提交中去掉；若只改该日志字节，无须重审上述源码差异。

边界：该规则只发现有明确原文关系的减值相关折旧；未触发不等于证明 D&A 完整。代码仍不生成新的 Ford EBITDA 值。对于未来不同表格布局，未匹配时可能留下未发现的范围问题，须按来源和业务验收继续判断。此次未运行长材料、完整 CI、真实 SEC/模型请求或正式发布。

审阅资源：16 次 `functions.exec` 调用及其中 17 次底层命令/补丁调用，共 33 次工具调用；未提问、未派生代理、未 commit/push，普通消息为开工说明加本最终报告 2 条。
