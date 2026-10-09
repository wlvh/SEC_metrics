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

后续H4已将所选历史期间接入新版共用保存记录、状态、同一公司CLI与CSV/证据；首批PR71已消费当前PR67/29c9并完成Marriott两年B10/B11，见[唯一公司接收记录](https://github.com/wlvh/SEC_metrics/blob/task/issue47-history-consumers/docs/evidence/issue47_history/simplification-closeout-2026-10-08/README.md)。这里的早期接口验证按原版本保留，不能把当时未完成的接线继续当作今天阻塞。首批不包含后续业务候选，也不表示完整五年业务接受。

仍待H4的是历史发现、缺件报告及按具体用途许可补齐进入同一公司工作流。当前范围计算依赖预备`source-root`，没有自动五年取源到CSV的交付；年度基础原件齐备不等于所有指标附件/图片/前期依赖齐备。指定EX-99最多一次GET/零重试已获原用途批准，当前未调用，原范围表达修补已经通过离线预检；后续仍被旧运行字节绑定挡在HTTP前，属于公共普通调用迁移缺口，不是缺少附件用途批准。原机制、同一实际账本及一次限制保持，未借余额或重铸旧证明绕过。新增模型/SEC调用为0，无新Run/业务接受/发布或active切换。
