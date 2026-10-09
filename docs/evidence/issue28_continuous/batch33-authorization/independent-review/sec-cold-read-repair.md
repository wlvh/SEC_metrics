# 4a5d4bb SEC 保存前缀冷读修复：限定独立复核

审阅范围仅为 `1c6bb186514284e07ebccfdfe237d5d2233e0930..4a5d4bb487406825dd2c60a3d05b6fd408e4436c` 中的 `scripts/vnext/continuous_batch33.py`、`tests/vnext/test_continuous_batch33.py` 和 `requirements/issue_28_v14/baseline_manifest.json`。上一轮 `conclusion.md` 的 P2 与其他历史结论保持原义。本轮只复核 SEC 通道停止后的保存前缀重放及相邻授权边界，不审完整 PR、模型内容或生产采纳。

**结论：上一轮 P2 所指的第二次 SEC 申领冷读漏洞已修复；本次限定差异未发现阻断。** `validate_history` 在接受每条独立 SEC 申领前，先检查已重放的停止集合是否含 SEC（`continuous_batch33.py:495-500`）。无终态的 SEC 申领，以及终态原因为 `HTTP_402` 等 `_STOP` 原因的 SEC 申领，都会把 SEC 加入该集合；之后即使伪造新的请求摘要、前驱和哈希，第二条 SEC 仍以 `BATCH33_HISTORY_SEPARATE_SEC_CHANNEL_STOPPED` 拒绝。真实 `CallLedger.claim` 对同一场景返回 `CONTINUOUS_CHANNEL_STOPPED:SEC`。PROVIDER 分支仍只按自身通道的停止记录判断，因此独立 SEC 停止不拦截合规的下一组 PROVIDER 申领。

核对结果：

- 新增反例测试在第一条 SEC 无终态时，先确认另一条 PROVIDER 组可申领并冷读，再向保存前缀追加自洽哈希的第二条 SEC，确认冷读拒绝（`test_continuous_batch33.py:121-162`）。我另用隔离录制账本复现已完成的 SEC `HTTP_402`：第二条 SEC 的真实申领被拒，另一条 PROVIDER 获得第4槽，原前缀冷读通过，追加的第二条 SEC 前缀被拒。两种停止形态均覆盖。
- 原真实账本仅作只读检查：172槽，累计 `123/123/49`，原171与新172均保存为 PROVIDER `HTTP_402` 终态；当前停止通道是 `PROVIDER`。`history_for_current` 生成的一条本批前缀经 `validate_history(mode='LIVE', native_rows=[])` 返回 `True`。原171停止只允许首个获批 D04 申领解除；新172停止未被本修复解除，也未发生真实 SEC 交织调用。
- 批次清单仍固定33组；PROVIDER 批次申领仍受66次子上限和第一个组的顺序约束，修后第二次申领分支仍关闭（`BATCH33_REPAIR_PROOF_NOT_YET_IMPLEMENTED`）。原账本 `claim` 仍按 `240/240/80` 总上限计数。批次的 `SEC0` 表示本批不授 SEC 额度；首次 D04 后的独立 SEC 获取仍须用原 Issue #28 许可和原账本的 SEC 余额，且不消耗批次 PROVIDER 槽。此次补丁未改变这些路径。
- V14 `execution_authority.files` 中本模块的 SHA-256 为 `3590f7e555180ab7265aa6718a7b28c7d909fc9fcc50b4e408c32af29193e99e`、大小31633字节，与工作区文件一致；manifest 差异仅更新该绑定值。

验证命令及输出：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. /tmp/sec_metrics_ci_20260922_venv/bin/python -m unittest -q tests.vnext.test_continuous_batch33 tests.vnext.test_continuous_call_ledger tests.vnext.test_continuous_recovery_110` → `Ran 31 tests in 0.849s`、`OK`。`git diff --check` 通过。没有真实 SEC/provider 请求，也没有修改原账本、代码或 `execution-state.json`。

边界：以上证明本次 SEC 停止与通道隔离的申领、冷读行为一致；真实账本尚无 SEC 交织前缀。全局额度由原账本完整快照与申领守卫核算，不能把本批前缀冷读单独当作完整历史额度审计；真实模型结论、完整公司 Result/Run 及生产权限仍不在本次结论内。
