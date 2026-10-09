# 限定独立审阅结论

结论：PASS；在指定三文件的增量内未发现需要修复的正确性问题。

- 工作区：`/Users/lyuhongwang/.codex/worktrees/issue28-reuse-dependencies/SEC_metrics`。
- Base：`9493ed0e973570f1331a898c73633ae4e69c8bab`。
- Patch / 审阅实跑 HEAD：`0ff6fc9ec493213f64d01fd4303981d5397a2535`。
- 审阅范围：`scripts/vnext/ordinary_current_update.py`、`tests/vnext/test_ordinary_current_update.py`、`tests/vnext/test_event_rule_root.py` 的指定增量；相关调用者与校验器仅为查证读取。
- 起始 UTC：2026-10-09 11:32:42 UTC（首次时钟观测）。结束 UTC：2026-10-09 11:36:36 UTC。
- 实际工具调用：30，包含 9 个 `functions.exec` 包装、19 个 `exec_command`、2 个 `clock__curr_time`。普通消息：3（两条进度、最终报告；无问题）。未另建代理。

## 依赖与行为核对

1. 当前公司保存入口为 `company_current_records.run_saved_company` → `ordinary_current_update.run_once` → `ordinary_saved_result.create_saved_result` / `save_calculated_case`。当前保存器的来源核验调用 `ordinary_source_authority.verify_ordinary_source_proofs`，它直接转调 `saved_source_checks.verify_saved_inputs`。`ordinary_source_session` 在脚本/工具代码中只有旧 `register_recorded_session` 函数内的按需导入，没有成为该当前处理入口的实际执行依赖。默认移除其摘要不会跳过当前来源检查。
2. 对 `SAVED_METRIC_IDS` 中 24 项逐一比较 base 与 patch 的 `_configuration` 函数，使用同一套当前文件摘要以隔离本补丁的集合变化：每项仅删除 `scripts/vnext/ordinary_source_session.py`，其余配置和摘要完全一致。`normal_annual_input.py`、`saved_source_checks.py`、`calculator.py`、`request_bindings.py` 均保留。详见 `dependency-comparison.log`。这证明本次删除范围，没有声称完成全仓依赖完整性审计或 24 项业务接受。
3. `run_once` 在默认配置之后单独读取、计算 `processing_files`，写入 `declared_processing_files`；补丁不从显式声明中删除 session。独立实跑确认显式 session 摘要变动生成新版本，同一变动随后复用且不再执行计算函数。
4. 已保留的选期、来源和公式依赖变动仍改变处理配置；独立实跑确认 `normal_annual_input` 变化重处理一次再复用，paired scope、实际计算图变化仍重处理，扣留结论仍与最近成功结果分开保存。已选年度的状态目录、选错年/依赖路径失败后的旧指针保护、年度隔离均通过指定回归。
5. 默认比较通过后仍执行 `read_saved_result` 和 `_current_sources`：原保存文件摘要、结果身份、期间、单位及实际最新请求绑定继续核验。本补丁只改变默认依赖集合，没有修改复用分支、保存器或恢复逻辑。

## 独立实跑

命令：

```text
PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_ordinary_current_update.CurrentProcessingConfigurationTest tests.vnext.test_ordinary_current_update.SelectedPeriodUpdateTest
```

实际 19 项（10 项配置测试、9 项已选年度测试），0.184 秒，退出码 0；失败 0、错误 0、skip 0。日志：`required-tests.log`。其中默认 session 排除测试有 B01/C01/B12/B10 四个 subcase；显式 session 测试走真实控制器，但计算与保存结果使用小替身，它不是真实财报材料实跑。

另独立执行纯配置对象比较，24 项全部 PASS；没有调用来源准备、计算函数或写入原结果。日志：`dependency-comparison.log`。

## 读取父任务证据，未独立重跑

核读了该提交保存的 README、`before.log`、`after.log`、`saved-entry-timing.log`，并检查新增真实入口测试实现。

- `before.log`：2 个测试，5 个失败（四个默认配置 subcase 与一个真实保存入口重复运行），14.354 秒，保留原失败。
- `after.log`：普通更新模块加事件材料模块共 39 项，15.996 秒，0 失败/错误/skip。
- `saved-entry-timing.log`：父任务实际 Marriott FY2025 C01，值 3、单位 count、期间 2025-01-01 至 2025-12-31；首次 1.906464 秒、复用 0.332565 秒、独立读取 0.002599 秒；结果身份 `sha256:724b92ab35202cc6c9e26099e8d8710f1b4321b5370e7c3b3e086a1d2a895a95`。
- 新增测试在重复运行时将计算入口设为抛错，并比较成功指针及六个保存结果文件的完整字节；随后通过真正保存读取器检查数值、单位和两端期间。因此父日志支持该真实保存入口复用、无新增结果文件及旧结果保留；本审阅没有将它报告为独立材料实跑。
- 父任务上述日志是在 base 加指定未提交补丁的树执行；本独立 19 项是提交后的 patch HEAD 实跑。两者版本与覆盖不合并。

父日志文件 SHA-256：

```text
before.log b7e870e1f78d5817e42306833392d08f1543c9c3324ba6b512a297e492c38fe3
after.log 12e4308ae347f95f355f3ba286b2e82db56a37abd2d56258c467bd05ccd6fa7d
saved-entry-timing.log 48ce80bb5b225bda9522043a1fe7489cd795377fbee821517aaa04fc96044562
```

## 覆盖边界

安装本补丁时 `ordinary_current_update.py` 自身摘要及默认文件集合会变化，既存配置会正常失配并重处理一次；它没有重写旧配置以强行跨安装复用。后续只有未使用 session 的摘要变化才保持当前普通结果可复用，显式声明 session 的消费者仍重处理。

结论仅为本补丁的默认依赖删除、显式依赖敏感性、已选年度控制及所核读真实保存接缝；不证明全 39 指标、全历史内容、在线获取、真实模型验收或业务正式采纳。未重跑长材料、未发真实请求、未 commit/push；未读取或写入 #47 工作树/账本/运行根。本审阅新增持久文件只有本目录的结论和两份必要日志，指定源码/测试保持 patch 字节。
