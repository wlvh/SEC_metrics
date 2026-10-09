结论：PASS_LIMITED_COMPATIBILITY。对本次默认新任务回修，未发现阻断接收的代码问题。此结论限定于下述差异、安装/选择边界和既有录制长链，不授业务正确性、整 PR、合并、真实调用、发布或生产批准。

审阅对象：patch SHA `818dd8711b87dccedc727986070746d48f0b003f`，比较基线 `29c9c9e2080a1de8c809660ac8fbdfc49072ef12`，保留 main 程序/规则 SHA `8588ccbbb1c91d81e0fb1a89dff3575214282549`。核验源文件为 scripts/vnext/company_local.py、scripts/vnext/company_retained_local.py、tests/vnext/test_company_retained_local.py 和 tools/run_fast_tests_v2.py 新 selector；被测磁盘字节与该 patch Git 对象一致。所引用历史材料只读，审阅仅新增本目录 conclusion.md 和三份日志。

- 默认不带 source-root 的新任务：安装器只从本地 Git 的确切 main 对象选取程序、目录、规则和 baseline 声明的执行输入。暂存源码中的 HEAD 固定为该对象，继承原 installer 的父规则校验和安装流程；不取浮动 main，不联网拉取。调用方 PYTHONPATH 不传入安装子进程。未引入 PR83 或新轻量 trust 证明链。
- 已有 native 任务：prepare_program 在源安装、当前 entry-file 哈希计算和 Git clone 之前返回其原 program_root；原路径检查保持。configure_task 保留既有 program_root / preparation_program_root 等字段，不重写旧 Run 或旧安装树。该路径只导入新安装器模块，其模块顶层没有 Git、安装或 HTTP 动作。
- 已保存来源路线：run_local 的 source-root 分支在 configure_task / prepare_program 前返回现有 company_current_records 入口。指定回归同时覆盖原保存来源结果、局部失败、旧期间、写锁、已有任务不能转成另一来源任务及读取不更新。
- 支持范围与依赖：当前上层与实装 main 的 configured_scope 都为 39 项、update_metric_ids 都为 38 项（原 D03 未实现状态保持）。实际新安装树与 main / 修后长链安装树的 Git tree 同为 `8585f5417d5b488c2d415e374b6e5a6154baa28e`，故没有通过缩小 main 安装能力绕过旧绑定失败。需要确切 main 及其历史规则 Git 对象，README 已说明；缺本地 Git 源时实测 RETAINED_LOCAL_SOURCE_UNAVAILABLE，在创建程序或 HTTP 前失败。后续旧规则校验失败继续由原 installer 返回，不静默改用候选字节。
- 安装内容：实装 756 个 tracked 文件；顶层 evidence、request_attempts、raw_response / raw-response 文件和五个已保存 AI processing 配置均不存在。outputs 仅含继承的历史验收 receipt / scalability audit，tests 仅含继承的 R4 合成输入。这些原有规则输入与 main 实装树相同，不是本次 B01/B02 的隐藏答案。未安装 SEC 原件或模型响应，来源仍走原本的独立获取/交接路径。

独立运行命令：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_company_retained_local tests.vnext.test_company_current_records -v`，外包 macOS sandbox-exec `(version 1)(allow default)(deny network*)`，Python 3.14.7，28 项全通过，unittest 6.781s / 总墙钟 6.971983s，returncode 0。详见 targeted-tests.log。

另做一次无网络实安装静态探针，没有 mock installer 或程序选择：configure_task 真正生成 main 程序，保存 retained_main_commit，再次 prepare_program 返回同一程序且配置字节不变；实装树等于两份长链实装树；上层/安装树的 39 配置和 38 支持项完全一致；缺 Git 源在安装前拒绝。安装及检查共 3.838292s（约 3 秒探针，没有长链或真实调用）。临时程序及其内部 runtime Git 已清理；仓库未提交或推送。详见 static-install-probe.log。

只读复核长链证据：main return0 / 166.358414917s，原 PR67 return2 / 1.836982042s 且 stage_statuses 为空，失败为 `Normal candidate rule bytes differ: scripts/vnext/normal_source_authority.py`；修后 return0 / 165.198919417s。main 与修后 acquire/handoff/install/compute/export-results 五个实际子进程报告均 return0，使用各自安装程序。两份 acquisition 各 29 个隔离录制 claim、RECORDED_TEST_ONLY，provider/paid/SEC 都为 0；29 个 URL 对应的 Git HTTP blob 的长度和 SHA256 全部匹配 fixture manifest。sitecustomize 仅注入 local_session 的录制 HTTP 回复；没有替换 _invoke、安装、发现或 Calculator 返回值。

两份 B01/B02 的数值、单位、年度、实际起止日期、source_class、formula、source_credit、result_validity、Requirement/closure 完全一致：B01 26186000000 USD；B02 0.04326693227091633466135458167 ratio；FY2025 / 2025-01-01..2025-12-31 / status OK。source_credit 仍为 RECORDED_TEST_ONLY，result_validity 仍为 REPLAY_VERIFIED_CONTENT_NOT_ACCEPTED。详见 evidence-inspection.log；166s 长链及此前旧任务/JPM/Southwest/保存来源长材料均按本次限定委托复用，没有重跑。

证据的精确边界：打包的 pr67-fixed.summary.json 与当时 local-company.json 尚无本 patch 新增的 retained_main 元数据，因此不能把该长链说成当前 SHA 的全部上层摘要字节已重新执行。独立静态探针直接验证当前 configure_task 保存的元数据，并证明当前安装出的完整程序树与两个长链树逐 Git tree 相同；run_summary 中新增字段是对该配置字段的读取。此小型摘要增量与未改安装内长链分开说明，不扩大记录的证明范围。

本次没有读取在线 Issue、网络或账户，权限/停点采用上级明确给出的限定委托；未获新的额度或动作权限。未修改源码、原有证据、#47 目录、业务账本或许可，未 spawn、tar、commit 或 push。实际工具调用总计 36（11 次 functions.exec，25 次其内工具；其中 1 次 UTC 时钟、24 次 exec_command），普通消息 2（开工告知及最终交付；问题 0）。UTC 起始 2026-10-09 04:23:58 UTC，结束 2026-10-09 04:30:25 UTC；未达到 80 工具 / 90 分钟 / 3 普通消息上限。

最终仓库状态（新增 conclusion 前检查）：
```
?? docs/evidence/issue28_company_records_20261007/default-online-review-20261009/independent-review/
```
