# 指定补丁限定独审结论

结论：**NEEDS_FIX，1 项 P2；其余指定目标在已执行的小材料范围成立。** 这不是旧普通事件行为回归：缺口继承自原选块条件，但新历史来源接口尚不能借完整 body 回调修正它。

- Base：`3d6030b1bc5e1e7b22833a0101fbeb8f88341498`。
- Patch / 实际 HEAD：`820461a084ace0e1824ba2da06a8b7be89e5cc5d`。
- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-source-recheck/SEC_metrics`。
- 起止时间：2026-10-09 08:43:07 UTC → 2026-10-09 08:52:36 UTC（Asia/Shanghai 为 16:43:07 起）。
- 实际工具调用：37（含 functions.exec 包装和其内嵌工具）；普通输出消息：2（1 条开工告知、1 条最终报告）；问题 0；子代理 0。
- 当前五项受审文件均逐字节等于 patch Git 对象；既有冻结包未改。

## P2：历史 gap 日的 block 在回调之前被漏选

位置：`scripts/vnext/normal_zero_ai_results.py:74`，新接口分别在 `scripts/vnext/selected_event_source_v1.py:68`、`:72` 调用该 walk。

该 walk 用原声明 `filingFrom`/`filingTo` 与窗口求重叠，然后才读取 body 并调用 `history_validator`。同一 SHA 的 `normal_history_catalog.block_last_days()`（第 85–113 行）明确允许旧 block 持有下一 newer block 开始前一天的 gap 日；`history_block_coherence()`（第 116–153 行）也按该有效末日核对完整 body。完整 body 回调因此只解决**已选 block**的检查，无法解决尚未读入的 block 选择。

小反例：选择 FY2025 的 2025-01-01—2025-12-31；历史 block 声明 2024-01-01—2024-12-31、filingCount=2；recent 的最早日为 2025-01-02；该完整历史 body 含 2025-01-01 的 8-K。现有 block_last_days 算得有效末日 2025-01-01，完整 body coherence 返回 None。新接口却跳过该 block，回调调用 0 次。

实际观察分成两种，不能混写：

1. 保存请求/body/header 在小录制路径、acquired-header namespace 为空时，接口返回 0 claims / 0 filings / 1 inventory proof，实际保存 body 有 1 个窗口内 Item 5.02 claim；这说明来源集合可能被缩小。它仍为 NOT_CREATED、无 Result/Run/E01 信用。
2. 把同一 header 加入 acquired-header census 后，接口明确报 `NORMAL_EVENT_ACQUIRED_SUPPLEMENT_NOT_IMPLEMENTED:0001048286-25-000011` / IMPLEMENTATION_GAP，而非接受较小结果；仍未读取该历史 block、回调仍 0 次。这个保护避免第二种布局的少计成功，但不能交付完整历史来源读取。

建议只修显式历史模式的有效范围/选块输入，让选择与 consumer 的完整 body coherence 使用同一 block 边界，并保留旧默认路径。消费者仅添加 body 回调不足以解决；修后必须用这个跨年小反例确认需要的 block 确实进入回调。当前未覆盖的 gap 选块能力不得写作历史来源覆盖通过。

反例证据：`history-gap-counterexample.log`。未重跑任何真实原件或 #47 消费者。

## 指定目标的实际确认

- source-only 根只用所选公司 registry 与保存请求/原文；rules 根供已注册 CIK。所选 predecessor 可在 successor 原件未保存时单独读取，没有自动改选最新主体。
- 回调确实收到完整 body、保留 rows、该主体 shards 和 period；两主体 union 会逐主体传递；非 None 冲突仍抛 SOURCE_COVERAGE_CONFLICT，不转空成功。这项仅覆盖已选 block。
- 同一小材料使用固定 base 原函数与 patch 默认原函数，对三元素返回 tuple、claims/manifests/filings/request proofs 实际比较完全相同；旧默认历史冲突保持。
- RAW_BLOB 合并仅忽略 storage_uri；其余字段必须完全相同。SOURCE_REFERENCE 不获得该例外。7 项原小测试实际覆盖 media 冲突、错误主体/registry、重复 GET 与最新失败。代码读取确认 subject/request record 冲突仍在完整等值条件内；未扩建防伪平台或独立信任库。
- 使用一致 body/hash/header 元数据的独立小反例确认实际 header 日期冲突及 inventory 主体冲突仍拒绝；它们不是仅靠破坏文件 hash 触发失败。
- 返回 source input 没有 Result/Run，new_calls 仍 0/0/0、production_authorized=False；空 claims 不取得独立 non-disclosure 或 E01 内容确认信用。
- workflow 明确加入该模块步骤，路径触发包含新测试；fast selector 加入同名模块。实际执行与 workflow 完全相同、不设置 PYTHONPATH 的命令也成功；没有宣称远端 CI 已运行。

## 实际执行

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_selected_event_source_v1`：7/7，0 skips，unittest 0.075s，进程 0.244502s；见 `required-tests.log`。
2. 独立小材料边界检查：7/7，0 skips，0.065s。包含 base 默认返回/proofs 相等、旧默认历史冲突、两主体完整回调正向、predecessor 单读、一致元数据的日期/主体冲突、参数拒绝；见 `independent-boundary-tests.log`。
3. workflow 原样命令（删除 PYTHONPATH）：相同 7/7 再验证，0 skips，unittest 0.085s，进程 0.277837s；见 `workflow-command.log`。这不是额外 7 项覆盖。
4. 两种 acquired-header 布局的跨年 gap 小反例：均确认回调前漏选；一者空来源集合，一者准确 IMPLEMENTATION_GAP；见 `history-gap-counterexample.log`。诊断脚本 exit 0 表示成功复现缺口，不表示该能力通过。
5. `git diff --check 3d6030b1bc5e1e7b22833a0101fbeb8f88341498 820461a084ace0e1824ba2da06a8b7be89e5cc5d` 返回 0；五项受审工作树文件与 patch Git blob 相等。

作者的 `README.md`、原件比较及旧当前事件集成日志已读，作为提供的执行侧证据。未独立重跑原件、长链、公司 CSV/保存读取集成、远端 CI 或五年批次；不把它们加入本次独立测试数。

无 commit/push、真实 SEC/provider 请求、账户操作、#47 工作树/账本/状态读取或写入；本次仓库写入仅本目录的 conclusion.md 与必要日志。测试临时目录也放在本目录并已清理，没有 tar/MANIFEST。


---

## P2 修后真正新增差异限定复核：35b9329d

**限定结论：PASS；原 P2 在显式 history_last_days 路径已修复，没有新增可行动问题。** 上方 820461a0 的 NEEDS_FIX 结论、原反例及所有原日志原样保留。本结论只接新增差异，不覆盖未测试的历史消费者接线或真实业务完成。

- 新 base：`820461a084ace0e1824ba2da06a8b7be89e5cc5d`。
- 新 patch / 实际 HEAD：`35b9329d28bd3fa0e9f47f988713d5f90b7fc152`。
- 本次范围：normal_zero_ai_results.py、selected_event_source_v1.py、test_selected_event_source_v1.py 新 gap 差异，作者 gap-regression-before/after 与 README 尾部。原主体、来源/rules 分离、RAW_BLOB 合并、CI 接线结论复用上一轮，不重新扩大复核。
- 本次起止：2026-10-09 08:57:52 UTC → 2026-10-09 09:01:24 UTC。
- 累计起止：2026-10-09 08:43:07 UTC → 2026-10-09 09:01:24 UTC。
- 本次工具 10；累计工具 **47**（含包装和嵌套）；累计普通输出消息 **3**（原开工/原最终/本次最终），问题 0，子代理 0。仍在 80 工具 / 90 分钟 / 3 消息上限内。

### 修后行为与验证

新增 history_last_days 接收当前 reader 真正读到的同一 payload 和由其产生的 shards。返回值必须是覆盖全部原 shard 名称且无额外名称的 dict，各有效末日必须是标准 ISO 日期且不早于原 filingTo。需要同时提供 callable 的完整 body validator；无 validator、非 callable 策略、缺项/多项、非法日期或缩短声明范围均拒绝。

选块现在使用该有效末日，body validator 接收完全同一个 last_day；原 shard.filingTo、body、issuer 与年度 period 不改。实际独立小例验证：空 acquired census 和含 header census 两种原反例都返回原先漏掉的 2025-01-01 event，1 claim / 4 proofs，完整 body validator 真正执行。两主体 union 的各 payload/shards 分开算有效末日，两 block 均读入并分别验证，2 claims / 8 proofs。完整 body 冲突依旧拒绝，不转空成功。

默认 history_last_days=None 保留原 filingTo 选块。本次以固定 820461a0 Git 对象载入原 selector 和 event walk，对原 gap 小材料比较整个 source-input 返回值，实际完全相等；严格只接原五个 keyword 的旧 history_validator 也成功，未默认塞入 last_day。默认路径保留旧 gap 行为是该兼容选择的明确边界；历史消费者需要实际传入新的策略及对应 validator，并登记它们的程序/config 依赖。这里没有把尚未接入的 #47 消费者写成修复完成。

### 实际测试

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_selected_event_source_v1`：**8/8、0 skips**，unittest 0.098s，进程 0.258046s；`gap-required-tests.log`。
2. 只针对新差异的独立小材料检查：**8/8、0 skips、0.105s**；`gap-independent-boundary-tests.log`。覆盖两种原 gap 反例、同 payload/shards 与 last_day、默认 None/base 整个返回相等、旧严格回调参数兼容、边界 map 拒绝、无 validator 拒绝、两主体转发和实际 body 冲突。
3. 三项受审文件与新 patch Git blobs 逐字节相等，限定 diff --check 返回 0。追加前核对上方 conclusion 与四份原独审日志均等于新 patch 提交中保存的原字节；追加后原 conclusion 仍为完整未修改前缀。

作者 before 日志的 TypeError 仅证明新可选参数当时不存在；没有把它当作原语义漏选的证明。原语义漏选依据仍是第一轮独立 history-gap-counterexample.log，本次则独立在两种同类小材料上确认修后行为。

没有重跑原件/长链/远端 CI，没有公司历史或 E01/Result/Run 信用，没有 commit/push/真实 SEC 或 provider 请求/账户操作/#47 工作树或账本操作。所有新增仓库写入仍只在这个原 independent-review 目录，同一 conclusion.md 追加及两份必要日志；原冻结包与原日志未改。
