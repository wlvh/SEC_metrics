限定独立审阅结论：REQUEST_CHANGES；发现 1 项 P2，尚不能确认“完整字典保留”目标全部成立。

[P2] 原生事实上下文遗漏 context/unit 各自的命名空间字典。位置：`scripts/vnext/d03_context_requests.py:63-66`。这里保留了 context/unit 的原 XML 及 `namespace_environment_id`，却只输出事实自身的 `p['namespace_environments'][env]`。XML 前缀的含义由各元素所在位置的命名空间对应表决定；事实、context、unit 的对应表可以不同。独立反例用未改动的 `_shared` / `_seal_unit` 来源表示生成完整字典：unit 原 XML 中的 `z:USD` 在原来源里属于 `urn:currency`，包里唯一输出的 `z` 对应 `urn:fact`，context/unit 需要的 `xbrli` 也未带出。请求进入正常 `LOCATED` 分支，原字典并非来源缺失；但后续读者仅凭 context 包无法恢复这些含义。独立冷回放仍完全相等，因为重建重复同一遗漏。它是表示内容不完整，不是外部摘要绕过，也不是对 D03 语义的判断。

建议保留事实、context、unit 所引用的全部 namespace environment 映射，检查这些依赖确实存在，并将补入的字典计入 context 字节限额；增加命名空间不同／前缀重绑定的正向测试与缺少相应字典的拒绝测试。补充后的实际包若字节改变，应形成新包及新摘要，旧包不改签。现有测试 fixture 的 context 只有 `period`，没有依赖环境引用，无法暴露本问题。

范围与证据：

- 精确审阅 SHA：`7c50eab93f8e99d28dd6ecd5a04bf9992a479ad7`；基线：`75f0905ed0626f5bb740902196fe3adee1a3348c`；工作区 HEAD 与指定 SHA 一致。
- 代码仅审 `scripts/vnext/d03_context_requests.py`、`tests/vnext/test_d03_context_requests.py`、`tools/run_fast_tests_v2.py` 新增 selector。只为确认原表示与锚点结构，窄读 `_bytes`、`evidence_json_bytes`、`_source_items`、`_shared` / `_seal_unit` 等未改依赖；未重新审阅旧 D03 mapper 或抽取语义。
- 实际保存来源和包位置来自指定 `verify_actual.py`／`actual-save.json`；没有执行会改写父证据的 verifier，也没有把父测试／其他代理判读作为独审证据。两组外部固定来源摘要、包摘要、磁盘字节与无损 JSON 序列化独立核对一致。
- Marriott 来源仍为原 17 单元、1 个责任单元；两个精确 nested XML `f-408-1` / `f-408-2` 分别逐字对照原根切片、原单元 ID、原元数据和范围，context 4878 字节。JPM 来源仍为原 130 单元、1 个责任单元；原 10172—10175 四个正文块逐字对照原块及索引，context 2287 字节。两包在独立进程中重新定位及回放一致。实际两来源的事实/context/unit 环境恰好一致，所以本 P2 不否定这两个已保存样本的字节定位结果。
- 指定 unittest 命令本次独立执行，8/8 通过，0.011 秒。另做 15 项独立边界断言（包括准确进入正常分支的 P2 反例），并单独确认 P2 的冷回放；日志保留原反例 Source 与导出包实际 JSON。
- 来源改字节沿用外部摘要、非责任锚点、无边界目标、布尔索引、重复请求被拒；来源/原单元身份经摘要及内容身份核对。查询缺位、重复 XML ID／正文索引、正文块数或 context 字节超限保留 `UNRESOLVED` 与原请求且不带半份上下文。同文档索引隔离通过。请求总数超过 `max_requests` 是整批显式拒绝，未静默丢弃多出的请求。
- 包内 context 改字节即便重算包摘要，仍被来源重建拒绝；重算包摘要并篡改语义/公司/调用信用标志也被拒。包的外部摘要与来源获取真实性仍由调用方提供；本 helper 没有获得来源获取信用。
- fast selector 恰好新增一次。指定差异中旧 mapper、CLI 和默认 Run 文件未改；未跑旧长链或 full suite，没有模型抽取、真实模型/SEC 请求、账户动作或 #47/PR52 操作。产品文件、历史证据与保存来源/包未改。

尚未覆盖／不授信用：D03 内容正确性、完整公司责任、动态后续请求总上限、4096 输出合同、生产输入检验、DeepSeek 独立验收、正式 Run/Result/生产。成功定位与冷回放均不授语义或公司结果信用；本次业务调用 0/0/0。

本次日志：`targeted-tests.log`、`actual-independent.log`、`dictionary-investigation.log`、`independent-boundaries.log`、`defect-replay.log`。全部只写入本 independent-review 目录。起始工作树已有 `execution-state.json` 修改，本审阅没有写该文件；最后只新增本审阅目录。

资源登记：开始 2026-10-04T03:12:34Z；结束 2026-10-04T03:20:40Z；用时 486 秒。实际工具调用 21（8 次 functions wrapper + 13 次 nested exec_command，包含本结论写入）；普通消息 3（2 次开场/进度 + 1 次最终报告）。未提问、未 spawn、未 commit/push、未打包。均在 ≤80 工具、≤90 分钟、≤3 普通消息的硬上限内。此结论仅绑定上述精确差异，不是全 PR 批准。
