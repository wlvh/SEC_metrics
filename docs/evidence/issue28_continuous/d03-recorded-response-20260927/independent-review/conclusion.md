# D03 录制响应字节保存：限定独立审阅

**结论：PASS_WITH_BOUNDS。** 受审对象为提交 `1535e5c18e843d6fdc02584a801e51a884249766` 的 D03 离线保存增量及其直接接口；没有发现阻断这项**录制测试证据**保存的缺陷。此结论不授予 D03 真实请求、模型判断、完整公司结论、原生 Evidence/Result/Run 或生产信用。

## 已核实的行为

- `record_offline_response` 先以现有 `candidate_request` 和 `validate_candidate_response` 重建来源、原请求和后继请求并检查传入响应，再将响应的**原始字节**写入 `raw-response.bin`。来源、前后请求和检查结果分别保存；包索引记录每个文件的 SHA-256/长度、模块 SHA-256、固定 `RECORDED_TEST_ONLY`、`calls=[0,0,0]` 和 `production_authorized=false`。`replay_offline_response` 先验包索引与文件，再从仓库保存来源重建请求、重新校验原始响应，并要求检查结果与保存值相同。该链将响应字节与来源/请求身份相连，但传入响应在本次测试中是**合成录制答案**，没有提供真实 provider 执行收据。
- 现场保存包 `/private/tmp/issue28-d03-recorded-packet-20260927-02` 仍存在。我独立核对其包索引哈希、5 个内容文件的长度和 SHA-256、模块 SHA-256、来源与两个请求的内容 ID、响应中的请求 ID、原始响应 SHA-256 和 `U+037E` 字节；均吻合已提交 `summary.json` 和 `cold-read-final.log`。提交中该模块 SHA-256 为 `89e46c2bf900ff14935969a784efeac6786cea4a88ce89e1659b51c54eac0785`，包 ID 为 `sha256:4bac51a935deadda11f456ba39f6976647fe2d5cd05fe194f89fbc7ef7ce02d6`。
- 已提交的最终日志记载 2 项测试在 116.887 秒通过，另一个进程禁网、禁子进程冷读后仍有 2 项未决。我未重跑这项长测试；独立短探针复核了现存包、符号链接路径和不完整包拒绝，并单独运行了真实账本根拒绝测试。测试中的改响应单文件、将录制信用连同包 ID 改签为 `LIVE`、不完整包拒绝，依据测试代码和已提交日志确认；这些攻击没有由本次独审全部重跑。
- 新提交未修改 `regulatory_fact_review.py`、原 D03 来源组装/响应校验、`canonical.py`、`sec_http.py`、既有 Requirement 或真实调用配置。`tools/run_fast_tests_v2.py` 只追加了该 source-material selector；旧历史绑定没有被新包追认或改写。`TESTING.md` 对离线/真实/原生信用的区分与实现一致。

## 保留边界与后续接线要求

1. **包哈希给出内容身份，不给出真实执行身份。** `replay_offline_response` 没有接收外部可信的预期 `packet_id`。从代码可复现的例子是给合法 JSON 响应末尾增加空格，随后更新 `checked.json` 的原始响应哈希、两个文件的摘要/长度及包 ID；响应语义不变，重放会把它视为**另一个**自洽的录制包。此例是代码路径分析，未重跑耗时来源重建。单靠包内哈希无法证明“就是先前那次响应”。当前已提交冷读输出与 `summary.json` 的包 ID 一致，所以本次有限证据可核对。未来若把保存包接到真实调用或原生链，必须以独立执行收据/预期包 ID 绑定实际请求及响应，不能仅凭本包自带的哈希赋予信用。
2. **冷读依赖当前安装根和本机外部包。** 重放重新读取仓库保存来源，并要求当前模块字节等于包内 SHA；`cold_read_recorded.py` 还写死本机 `/private/tmp/...` 路径。提交本身不携带 18 MB 的完整包，因此另一台机器仅凭 Git 提交不能直接复跑该冷读；可重新运行录制测试生成新包，但其 ID 须重新登记。禁网保证来自脚本中的 Python monkeypatch，并非系统级网络沙箱。本次认可范围限于日志与现场包的现有身份。
3. **业务含义仍未被验收。** 保存包中的 2 项未决保持未决；无真实 D03 响应、完整全文冲突判断、原生 Run 或公司级结论。未来接线还须分别验证这些门槛。本结论未审计同一提交的 `execution-state.json` 与 `continuation.md` 更新，也未触碰 #47/PR52。

复核材料：`short-probes.log`、`identity-probes.log`、`ledger-root-short-test.log`；原记录为上级目录中的 `recorded-store-final.log`、`cold-read-final.log`、`summary.json`。本次没有 provider/paid/SEC 调用，没有提交、推送或改写父执行者的工作树状态。工具调用共 **52 次**（14 次外层 `functions.exec`，38 次其内执行工具；其中一次短探针因 macOS 临时目录 `/var` 别名而自行失败，改用解析后的路径复测通过）。
