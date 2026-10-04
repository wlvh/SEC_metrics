# 限定新增差异独立复核

结论：`PASS_LIMITED_DELTA`。在指定两文件的新增差异内未发现需修复问题；原4c9完整mapper审阅不重开，也不扩大为整个C02或PR批准。

- Base：`50fbf66feb898c139b747329b26984de1da7c880`。
- 审阅目标与实际起始HEAD：`9000d02a1a0ee57f967fe4690a2f407150e68662`；结束观察HEAD：`9000d02a1a0ee57f967fe4690a2f407150e68662`。两受审文件工作区字节逐一等于目标提交。
- 范围：canonical增加`strict_json_file`导入；`_root`由硬编码账本路径改为读取`config/issue28_continuous_calls_v1.json`的`budget_root`；一个配置根保护回归。逐字替换后与目标源码完全相同，无其他mapper逻辑差异。
- 起止UTC：2026-10-04 11:15:52 UTC → 2026-10-04 11:23:01 UTC。
- 工具计数：25，wrapper与nested各计一次，含最后生成/核验本材料；10个wrapper、15个nested。含1次仅wrapper的JS变量名错误，该次无nested执行或文件变化。普通消息：3（开头、一次进度、最终）；无问题、嵌套spawn、commit、push。

当前配置与保存旧运行时配置均指向用户固定总账`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`。配置、调用政策/账本、财政字面量审计、审计白名单与反例测试、C02 Spec在base→目标之间均未改动。账本目录及祖先/子路径、源码目录及祖先/子路径、相对路径、符号链接、含active指针的目录及子路径仍拒绝；来源同根、祖先、子路径重叠仍在构造前拒绝。新增配置回归还证明配置换为独立临时根时仍拒绝该根/祖先/子路径，合法相邻开发路径可用。此变化没有公司/财年特殊分支，没有审计白名单、财政反例放宽或真实调用授权。

指定`PYTHONPATH=scripts /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_c02_table_model_processing tests.vnext.test_ordinary_scalability_audit -v`（另加`PYTHONDONTWRITEBYTECODE=1`）一次17项全通过，unittest耗时12.338秒、进程12.475秒。另作一次禁网路径保护检查：13个拒绝情形、1个合法输出情形通过，临时材料正常清理。证据：`specified-short-tests.log`、`independent-root-protections.log`。

独立逐一核对`old-runtime-files.json`所列344份保存运行时文件，均匹配保存SHA；旧mapper的`3097ae19...`同时匹配git 4c9e195原字节，新mapper为`05806a45...`。随后在OS禁止网络、禁止写源码/旧运行时/旧原生包/实际账本的条件下，用该旧运行时对原模型对象重读一次，源数据根仍为原仓库；5.624秒完成，全部6份保存包文件在前后与原创建manifest一致，无重签。Candidate仍为`sha256:f94c88771b7f8627470fd06fe44427d58af0fce75a5a856dc97d4b06896b3bf4`，Review Unit仍为`sha256:8faf9fec2e563a8c7ee4693df427501697a8483f30fd6f78fe31deb1955b335c`，`PENDING`及SYSTEM审批拒绝保持。证据：`saved-runtime-byte-check.log`、`old-runtime-independent-replay.log`；与已有`old-runtime-replay-after-guard-fix.json`身份相符。

本次provider/paid/SEC增量`0/0/0`。未跑模型抽取、真实付费/SEC或旧长链；未改变源码、执行状态、旧native对象、peer现场或账本。预先存在的`execution-state.json`工作区修改保留。输出仅本目录内一个`conclusion.md`与日志，没有tar。本结论不授予语义APPROVE、Result/Run、公司或390信用、Ready、merge、生产采纳或active切换。当前Issue #28正文实时读取记录在`issue28-live.log`，仅用于确认现行边界，不将导航状态当作运行授权。
