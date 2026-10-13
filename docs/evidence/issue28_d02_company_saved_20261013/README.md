# D02：原保存回答进入公司 run、保存、复跑与独立读取

## 使用者实际得到什么

公司正式入口显式选择一家公司、一个申报财年、D02、只读 SEC 来源根及单独的原保存回答根。历史来源核心重建完整 Item 8 请求，公共读取器核对原请求/响应，现有 D02 汇总与 Calculator 形成原文集合，再经普通 controller/store 输出 CSV 与出处。不是直接把旧 Result 放进新目录，也没有模型或 SEC 调用。

本批实际 Ford FY2025 完成：20 个 Item 3 原文块、25 个被引用 Note 24 上下文块，共 17,765 字符。Result `sha256:fd73a6b3af93494b482bbf81609766fe1b4f56951c11f79e9f92bbf92f7a1257`，全年 2025-01-01 至 2025-12-31，unit=text / quality=EXACT / reason=PASS。7 个结果文件共 409,480 字节。每日读取仍标 `SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED`，不授正式业务采纳或生产权限。

## 固定依赖和修改职责

- 实际 main `6efe086455693abbc0fc9d54cbe54b5286a84877` 已含公共七文件读取器 PR239、公共失败/部分任务保存 PR241、实际 feature CI PR242、当前消费者 PR238 及页眉 PR240。
- 本批只消费明确的纯业务提交 `a539b081b3888f5db0b0a43f673c27bae2d3cec0`：#47 提供 `d02_reviewed_source` 的完整来源、请求和现有原生 case 汇总；不合整个历史分支，不并写其业务核心。
- 打开页眉开关的前置 P2 修补为 [PR245](https://github.com/wlvh/SEC_metrics/pull/245) / `33d8237d946ff2f30a82506c44f2e7fb0e978a7c`。实际已合到本方组合，普通编号小节和未引用 NOTE 40 不能成为删除正文的锚点；年份保护亦保留。Root 不把旧 5a74 或仅默认关闭当成修后信用。
- 本方修改公共 `historical_d02_case`、`company_local`、CLI 和 `ordinary_saved_result` 的显式 case 集合；旧默认返回形状不变，D02 没有加入默认 current 已接指标集合。共享 controller/store 仍为一份。
- 新测试 `tests.vnext.test_d02_company_saved` 通过独立 feature 登记进入实际 foundation CI，不改共享测试列表、workflow 或保护设置。

## 原件、回答和范围

来源根是本方既有 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`，全程只读。实际 HTML `f-20251231.htm` 的 SHA256 为 `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`；公司 CIK=37996，申报 `0000037996-26-000015`。

原回答来自固定 `bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786` 的 `evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz`（SHA256 `970c98e67b7c7b8c1b55eae6b9dd602917cec45af8c193ec1ac9a5d941acf9a0`）。只取 `root/calls/0009/` 下当前读取器实际需要的七个原成员，另放本方开发目录 `d02-company-ford-20261013/answers/call0009`。不复制调用账本或来源包，不重编号、不改原回答。

从完整来源重建的请求仍是 `sha256:7f0d2be204ae60689397a55ac102ec07f3ad0923c57ab00db59060abd9fe8908`。其整个合格 Item 8 池是一段指向 Item 15/财务报表位置的说明（b1812），不是法律事项；原空子答与此原文相符。原 LIVE 调用身份、1/1/0 原计数、963/13 token usage 保留，费用未知仍为 null。空子答没有变成“公司没有诉讼”：Item 3 和被明确引用的附注经实际汇总仍有非空披露。

范围按 [原批准 Spec](https://github.com/wlvh/SEC_metrics/blob/bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786/catalog/r6/D02_legal_disclosures_v1.md)、[已有双向阅读](https://github.com/wlvh/SEC_metrics/blob/bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786/docs/evidence/issue47_history/content-acceptance/d02-both-directions-read.json) 和 [固定来源核心澄清](https://github.com/wlvh/SEC_metrics/blob/5424438168a5e602e04b1516ef48054ab924e88b/docs/evidence/issue47_d02_reviewed_consumer_20261013/README.md) 复核。Ford Item 3 指整 Note 24，Marriott 的指定 caption 是相反例。担保及一般保修属于被引用整 note 的来源上下文，不能把 45 段称作 45 件诉讼、45 条独立法律发现或总诉讼负债。当前 CSV 的说明明确不推断案件数或总负债。

Root 已核对上述原文引用、Item 8 实际段落及结果后段的诉讼/索赔、确认政策、担保和保修上下文；另逐项核对 45 个 raw byte span、原 HTML 哈希、CSV 引文、CIK 和实际期间，见 `source-span-checks.json`。逐字节/引文检查不等于完整语义漏报验收，也不宣称本次独立重读了所有财报内容。

## 实际执行和限制

实测生产文件为本地组合 `f40b04a15e684b73ded57c67d7cd5cbc31f2aa34`。当时未提交差异只在本证据脚本、日志及新增测试，逐阶段记录见 `company-executions.json`；不把工作树演练伪称最终发布 SHA 实测。提交后核对相同生产文件字节，原 Run/Result/回答均未改签。

| 实际步骤 | 秒 | 结论 |
|---|---:|---|
| 完整来源准备并核对旧请求 | 8.023 | 原 request ID 与七原成员对应，没有创建 Result |
| 正式 CLI 首次 run | 8.211 | FLOW_COMPLETED / CANDIDATE_READY，实际非空结果及 CSV |
| 相同输入复跑 | 0.554 | NO_SOURCE_CONTENT_CHANGE；真正生产函数 code guard 零调用；原7文件保持 |
| 新进程 results 读取 | 0.096 | 同文本、期间、出处；不准备来源或计算 |
| 缺必要完整回答 | 23.682 | 明确 MODEL_RESPONSE_REQUIRED / INPUT_OR_EXECUTION_FAILED；未汇总或计算；7结果文件保持 |
| 新进程读取失败状态 | 0.097 | 当前 value/unit 为空，旧成功仅 previous_result_value / PREVIOUS_RESULT |
| 恢复原回答 | 0.562 | 零生产函数调用并复用原结果；不新增结果目录 |

这些计时来自同一代码根/机器/任务。缺件及复跑/读取带生产函数守护，首次没有全 Python 调用 profiler；不把计时拼成提速比例。第一轮只读准备曾因本验证脚本的 profiler 占据执行而安全停止（没有请求或结果），原空日志与 `profiled-preflight-stopped.txt` 保留；修正测试仪器后才得到上述计时。

定向组合最终 166 项 / 9.485s，零失败/错误/skip：公共分派、保存读取、更新/恢复、来源核心、旧 V2/D03/H1 边界及 CI 登记。原一次命令错误引用不存在的 `test_ordinary_saved_result` 导致 1 个 import error，原日志保留；更正为真实 `test_ordinary_storage_identity` 后重新执行，不删除错误或改业务断言。9 项公共分派测试含一个隔离的未决回答边界，真实源/聚合器抛 `LegalReviewUnsettled`，Calculator 不可进入；其模拟 reader 输出不授业务信用。

正式 CLI 首次、复跑、独立读取都只替换外部网络/SDK send/调用申领为“尝试即报错”的守护，未 mock 安装、选源、汇总、计算、保存或整个子进程。新增业务调用 0/0/0；本方原账本仍195条（PROVIDER/paid143，SEC52），总限240/240/80，剩97/97/28；原计数和原失败机会不改。

## 复现入口

需要完整保存 SEC 来源和独立的七文件原回答集。不是默认在线获取，不需要业务密钥；未知/缺回答、原 RECORDED 回答、未知 usage、其它公司、多期间或源/回答重叠仍拒绝。当前仅一个连续主体、无修订的财年；新来源没有匹配已登记回答时明确缺处理，不能购买替代或从旧答案裁出新请求。

```bash
TMPDIR=/private/tmp python3 tools/vnext_company.py run \
  --company ford_motor_company --period fiscal-years \
  --fiscal-year-start 2025 --fiscal-year-end 2025 --metric D02 \
  --source-root <完整只读SEC来源根> --saved-legal-reviews <七文件原回答根> \
  --work-dir <新的独立状态目录> --output-dir <公司输出父目录>
python3 tools/vnext_company.py results --company ford_motor_company \
  --state-root <上述状态目录> --output-root <新的独立读取输出目录>
```

`verify_company.py` 是本批可运行的离线 CLI 复现器，参数为 program/source/answer/work roots 和 prepare/first/repeat/read/missing/read-failed/restore phase；first 只允许空状态。Root 验证使用 Python3.12.14 和已有 tokenizers 环境。原始引用及请求保持，未增加模型、SEC、内网用途或额度。

当前成果是实际公司保存/复跑/读取闭环及其有限来源内容核对，不是新 DeepSeek 验收、所有年份 D02、390完整验收、正式采纳或生产切换。接收方仍须按实际组合复核。其他原队列责任继续。
