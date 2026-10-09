# a48d282e B13 两阶段离线候选：限定独立审阅

审阅对象固定为 `a48d282ed719c210001aab4dbfef67b892631900` 相对父提交的 `scripts/vnext/capacity_two_stage.py`、`tests/vnext/test_capacity_two_stage.py`、`tools/run_fast_tests_v2.py` 与本证据目录。为核对接口，只读查看了既有 V4 来源引用和语义验证函数；未重审历史已结案问题或整个 PR。结论：**离线来源和输入测量可复现，但两阶段结果的接线守卫尚未通过限定审阅**。以下两处校验缺口应在任何真实接线或信用申请前修复。

1. **P2：第二阶段可接受重算摘要后的超限扫描结果。** `validate_scan` 在第 127 行正确拒绝 65 个候选引用，但 `interpretation_request` 第 148–155 行仅比对扫描结果内可自行重算的 `scan_result_id`、请求身份和两个布尔标记，没有重读第一阶段原始响应，也未重新检查引用数量、归属、必评覆盖或 `raw_response_sha256` 与响应内容的一致性。对保存的第 190 次 Enphase 第 1 组（1,276 个可用引用），把已验的 64 引用结果改为 65 引用并重算摘要、保留旧原始响应哈希后，第二阶段仍构造成功；见 [boundary-repro.log](boundary-repro.log)。因此“超限即停止”只对直接调用 `validate_scan` 成立，不能作为跨阶段保证。建议让第二阶段从保存的扫描原始字节重新验证，或在有不可变录制绑定的前提下复核完整扫描不变量，并新增重算摘要的反例。
2. **P2：扫描单元序号没有严格整数检查。** `SCAN_PROTOCOL` 第 50 行要求整数，但 `validate_scan` 第 117–119 行只用 Python 列表相等比较；`false == 0`，实际把第 0 项改为 JSON `false` 仍产生成功的形状结果，见 [boundary-repro.log](boundary-repro.log)。应逐项要求 `type(index) is int`，再比对完整顺序，并补布尔/浮点负例。这个缺口不证明模型确实漏读了来源，但当前“完整单元序号已核验”的声明比实际检查更强。

已确认的边界：扫描和判断请求保留原 V4 组内 `units`、共享字典及来源身份；可见块、原生事实、补充对象的类型和归属由既有引用清单核对，`validate_scan` 对直接响应拒绝错类型、重复、越界、漏必评及 65 引用，第二阶段要求全部候选有发现或未决项并调用原 V4 语义验证。空扫描明确写 `absence_established=false`。新增模块没有真实调用入口、Candidate/Evidence/Run 输出或生产信用。提交没有改动旧第 190 次请求/账本文件；测量脚本把 Enphase 第 0 组标作精确复用并跳过新请求构造，但本审阅**没有重验**旧 190 的历史成功或跨新旧组的公司合并。

指定短测试 `PYTHONPATH=scripts uv run --no-project --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_capacity_reference_contract -q` 实际运行 **21 项，OK**；日志见 [targeted-test.log](targeted-test.log)。提交中 `run_fast_tests_v2.py` 只增加一个 fast selector；保存的 `fast.json` 记载 128 selector / PASSED，未在本审阅重跑长套件。测试中的超限负例仅把全局上限临时改为 1 后调用第一阶段；它未覆盖跨阶段重算摘要反例。

从原账本保存的 Enphase 190、Ford 171 来源只读重算，生成结果与提交的 `measurement.json` **逐字段相同**；摘要见 [measurement-replay.log](measurement-replay.log)。共 6+11 个原组，保留 Enphase 第 0 组后，新方案按 5×2+11×2 得到**最多 32 次假设新请求**。16 个新双阶段组的扫描与判断输入加 4,096 输出预留，在当前渲染规则下均小于 200,000；最紧的是 Ford 第 9 组 199,179，余量 **821 token**。判断阶段的合成候选数是每组 `min(64, 可用引用数)`：其中 **5 组少于 64**（Enphase 第 4、5 组；Ford 第 8、9、10 组），所以 README 第 11 行的“每一组 64 引用压力输入”应改成这个精确表述。测量只证明这些保存来源、当前代码/渲染及合成输入的尺寸；它不证明真实扫描能找全、真实响应在 4,096 内结束或类别正确。Ford 使用第 171 次保存来源，并非本次新获取的当前申报。

未覆盖：真实模型扫描/判断响应、第一阶段遗漏率与假阴性、超限时真实停止与费用账本、原生保存/冷读、旧 190 与新结果合并、完整公司 B13、远端 CI、正式生产/发布，以及 #47/PR52。未运行真实模型或 SEC 调用、账户操作、长测试；未授新请求权限，也没有把第 191/192 组失败改成可第三次抽样。两处发现只针对本 SHA 新增的双阶段边界，不扩成对原 V4 或全 PR 的否定。
