# H4：接收 #28 的轻量来源与 CSV 接口

接收固定 [PR60/e6dd436b](https://github.com/wlvh/SEC_metrics/pull/60) 的 `annual_sources` 和 `csv_output`，以及原来源/发布模块的兼容导出。共用模块仍由 #28 维护，本方只更新历史来源消费者、已有历史公司范围/读取出口的导入；没有复制整个 PR43、改公共 AGENTS/CI 或新建历史 pipeline。原公司 `fiscal-years` 分派继续复用，不重开发或重新算两年 B01。

历史 B06、事件、年度输入、语义来源和酒店适配读取同一 `annual_sources.saved_source`；异常类型与旧 `annual_update` 接口相同。公司历史计算及范围/状态/结果出口读取同一 CSV 字段和序列化函数，缺列仍失败。原 publication 的本分支 scalability 差异保留，没有用整文件覆盖现有改动。未接入与本项无关的普通 B01 新记录路径或整套 runtime/trust。

主要验证：

- 实际 Marriott FY2025 保存来源（2048661字节）及出处，用修改前 getter 与新 getter读取完全相同，分别0.024/0.022秒；异常/函数兼容导出对象相同。没有计算、写入或网络调用。
- 当期、两年历史范围及缺失年份的六份既有 CSV，全量字段/行用新旧格式器序列化后与原文件逐字节相同；只读验证，不重新计算 B01。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. work/issue47-venv/bin/python -m unittest tests.vnext.test_historical_runtime_helpers -v`：4项通过，0.001秒，覆盖兼容异常、最新失败不回落旧成功、六份原CSV及缺列错误。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. work/issue47-venv/bin/python -m unittest tests.vnext.test_company_historical_range tests.vnext.test_historical_lodging_introduction.TheOlderFormsAreTwoAndOnlyTwoTest -v`：10项通过，0.026秒。第一次有一个范围读取例被macOS `/var`临时目录别名阻挡；仅在历史测试中先解析夹具实际路径，再执行同样的期间/失败/旧Run身份断言。未放宽生产检查，原失败保留在本次工作日志。

此接收在历史分支，尚未main；PR60本身也仍Draft。它减少历史消费者对发布模块的小工具依赖，不表示所有间接治理导入都退出。旧固定程序/Run未修改；两年范围、同目录复跑及缺年实际验证继续承接。

后续已接PR67普通当期保存记录、共享XBRL解析和公共公司读口，实际同一CLI的首跑/不重算重入/子集合后读取通过；主要结果见[公司消费者记录](evidence/issue47_history/company-ordinary-receiving-2026-10-07/README.md)。历史分派和旧任务读取保持，既有两年B01不重算。普通接口与本方历史能力仍在分支，未入main。

仍待H4：指定历史期间进入新版共用保存记录/共享来源，以及历史发现、缺件报告和必要补齐进入同一公司`run`。当前历史入口仍需预备`source-root`，没有自动五年取源到CSV的新增交付。指定EX-99原动作仍在HTTP前被原grant范围阻塞，原机制、账本及最多一次许可保留，未在此接口接收中绕过。新增模型/SEC调用为0，无新Run/业务接受/发布或active切换。
