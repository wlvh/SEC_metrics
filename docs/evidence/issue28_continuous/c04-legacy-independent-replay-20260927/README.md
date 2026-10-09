# 旧语义导出不可用时，Salesforce C04 私有原生Run仍可回读

本项复用既有FY2026 Salesforce C04真实保存来源与私有原生Run，不重新获取、不重新生成Result。`probe.py`在**一次性独立Python进程**中读取Issue15冻结语义生产者清单，把覆盖39指标的116个旧`sec_pipeline`语义导出临时替换成原仓库的`retired_legacy_entrypoint`；一条旧导出对照调用确实被拒。然后在同一临时禁用范围内，通过当前C04原生更新验证器从原保存Run重读Result及公共行。网络、HTTP、DNS和子进程调用均被阻断；active指针、总账claims、私有Run manifest、矩阵行与证据行在前后逐字节SHA一致。

`result.json`记录单条Salesforce/C04 FY2026路径`PUBLISHED/0`、原Result/Run ID保持、旧导出对照拒绝及调用`0/0/0`。实测代码根为`b686814f586bc4ba7471e00218a54773645cc48e`（运行时仅有本目录证据未提交）。这是比早先“只禁用旧导出且历史发布可读”多一步的**新原生路径依赖演练**：新C04回读可以在旧模块导出被禁用时完成。它仍不证明完整390个坐标的调用图都与旧语义生产者隔离；可能存在预先导入的函数别名或其它未覆盖入口，也没有正式退出旧路径、发布或切换active。未来完整新链和生产级退出仍须另验。本次没有修改真实生产代码、共享默认、#47或任何已采纳发布。

运行：`PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python docs/evidence/issue28_continuous/c04-legacy-independent-replay-20260927/probe.py`。该命令本次约46秒；输出保存为`result.json`。它读取的是当前主机私有Run，Git材料本身不携带该包，异机不能仅凭本目录复现。
