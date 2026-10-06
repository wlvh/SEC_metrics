# H4：历史消费者接收 PR63 日常读取

接收固定PR63 `47285a3745e4cdc95aff18b3ea4df9fd332c968d`的`company_daily_results`及公司CLI `results --output-root`分支，不带入公共AGENTS/CI或对方缺陷登记。历史分支保留原`compute-range`和`state_root`选择；当前launcher负责日常读取，原任务固定程序继续负责计算。显式传本方`known_result_defects.json`，旧`export-results`审计入口保留。没有新增历史pipeline。

实际读取已有Macy FY2023/FY2024两年B01任务：10.908秒、原两Run/Result不变，值23092000000/22293000000 USD，FY2023实际日期2023-01-29至2024-02-03，FY2024为2024-02-04至2025-02-01。原20个指标业务列、18个出处业务列逐列相同。核验状态明确为`SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED`，测量期间为`SAVED_RECORD_CHECKED_NOT_REPLAYED`，原复跑状态`NO_SOURCE_CONTENT_CHANGE`保留。没有把日常读取说成原生冷重放或新内容接受。

实际历史launcher `_export_current`阶段再走同一CLI：11.246秒，命令记录显式指向当前源码、原historical-company-state、本方缺陷文件和原计算程序。原Run/行/收据/指针共16文件哈希前后相同。已有当期FY2025 B01保存任务读出21764000000 USD，2025-02-02至2026-01-31，10.748秒。两年与当期均未重算、未复制attempt；输出只写新的日常目录与小CSV/JSON。

测试：历史范围和本地编排21项通过，0.060秒；接收公共日常读取测试11项通过，0.182秒，覆盖值/单位/期间、错源、已知缺陷、来源失败和原子输出。Mac临时路径先解析为实际路径，避免测试在旧路径别名守卫前停住；未放宽生产检查。编排测试使用替身，以上实际保存任务读取单列，不能用替身代替真实结果。没有再跑原两年计算或完整历史批次。

仍有公共CSV增量待#28：JSON保留`requested_in_latest_execution`、`period_role`，当前日常CSV尚未输出两列。已直接报告给公共模块负责人，不由本方另写读取器；历史本地run的请求注释保留。原旧审计元数据列不要求全部镜像，新`record_root/source_root`定位保存输入。新实际读取与较早22.430秒审计导出不同运行时点/工作量，不能宣称严格同比加速倍数。

本项仅进入历史分支、尚未main。公共源发现/变化检测/共享attempt和历史来源发现补齐进入同一run仍待H4；完整五年业务验收不变。本轮DeepSeek/paid/SEC新增0，EX-99已核账本1547槽/1771累计未变，无新GET；原许可、运行包和阻塞保留，无发布或active切换。
