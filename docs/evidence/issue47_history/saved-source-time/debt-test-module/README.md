# B06 测试模块复用受守卫的准备结果

测试树固定在 `4041c171`。同一棵未改树、两个独立进程同时执行同一套 13 个 `test_historical_debt_results` 用例：对照使用原有 XBRL 解析块；试验外加既有 `run_checks_replay_once` 和 `derived_once_per_state`。两边全部通过，八个实际级联结果的完整 JSON 字节相同，SHA-256 都为 `3dc43553a4f8d11c1a375e82cf2e6d6db6ea04d823077e671a6c71613dae19d8`（保存的是比对摘要，不是新增接受）。包含数值、扣留、特殊范围、前身/继任等全部对象，不只比数值。

同批本地耗时：对照 245.73 秒，试验 212.61 秒，少 33.13 秒（13.5%）。试验只发生 11 次推导计算、4 次复用；没有任何 Run 重放，因此没有采用多余的 replay 块。正式改动只在本测试模块的 `setUpModule` 里打开 `derived_once_per_state`，与原有解析块一起在 `tearDownModule` 关闭。没有改业务模块、冻结入口、断言、样本、用例数或 CI 分片。

在模块本身打开后，再独立执行一次：13/13 通过，八个结果仍逐字节相同，196.50 秒。这次并发负载较小，不能用它和上面的对照推导额外提速比例。`control.json`、`memo.json` 和 `module.json` 保存逐用例结果、完整对象摘要、测试文件摘要及缓存事件。一个本地配对测量不代表 GitHub runner 的时间；暂不降低 `SOURCE_CI_SECONDS`，等 CI 逐用例进度给出实际秒数。

复现：在隔离克隆检出 `4041c171`，对同一树分别执行 `python3 <本目录>/benchmark.py <克隆根> control <输出.json>` 和 `… memo <输出.json>`。最终模块上的调用用 `module` 模式；对照树须保留未加模块级推导块的原测试字节。脚本另外写出完整 `.resolved.json` 供字节比较，临时对象留在工作目录，不作为原生 Run、接受或生产证据。

零模型、付费、SEC 调用。既有用例仍逐字段核对普通与历史路线，并用 `original_sources_only` 禁止网络及派生答案读取。
