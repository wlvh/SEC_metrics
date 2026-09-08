# Marriott 年报变化检查与输入准备

本轮交付一个手动运行入口：判断是否有待处理的受支持年报，必要时准备 B01/B10
所需输入。正式迁移仍为 R3 的 24 指标、240 坐标；327 行公开矩阵不代表 39 指标
已经统一生产。PR35/PR36 已完成，本入口不重跑其真实 B10 计划。

## 本地检查

在原项目目录运行：

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY -u SEC_CONTACT_EMAIL PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_annual_update.py
```

可加 `--output <新的绝对外部JSON路径>` 保存本次检查。程序不会覆盖同名旧文件。
默认从 `PublicationView` 固定的正式 bundle 读取原生 B10 的成功期间与来源。
可加 `--candidate-run <已有原生B10成功Run绝对目录>`，同时显示历史成功候选；
未提供则显示 `candidate_baseline_status=NOT_SUPPLIED`。这不是搜索所有历史 Run
的索引服务，也不暗示不存在其他成功候选。

比较使用公司/CIK、accession、报告起止日和主文档身份，已有原文时另核对字节哈希。
两个成功基线同期间但来源不同会阻断；较新成功候选不使较旧正式结果被登记为已更新。
检查文件本身不能用作成功基线。原生候选仅复核保存的成功 attempt、证据、审核和
结果来源链接；不重新认证其内容，不把 OPEN 或内部 PUBLISHED 改成正式发布。

## 结果与接入

| status | 含义与下一步 |
|---|---|
| `NO_NEW_ANNUAL_FILING` | 清单未显示比成功对照更新的受支持年报；不准备计划、不计算 |
| `INPUT_READY` | 有新的申报，原文实际期间通过原有校验；`prepared_input` 可交给既有入口，尚未执行 |
| `INPUTS_MISSING` | 有新的申报，但列出的原文或包含目标年度的 Company Facts 缺少；未更新成功基线 |
| `CHECK_FAILED` | 日期、修订、歧义、清单完整性、来源冲突、证据损坏或获取失败；不能说没有更新 |

`submissions` 包含请求证明和真实保存时间，`checked_at_utc` 是本次检查时间，两者
不能混淆。`discovered_filing.period_basis` 在原文未读取时为 submissions 元数据，
原文通过后为 `PRIMARY_DEI_AND_CONTEXT`。输入准备成功不证明 B01/B10 数值正确。

`prepared_input.companyfacts_input` 与 `prepared_input.table_input` 保持 PR35 的
接口形状，分别交给原有 `create_companyfacts_release_run` 和
`create_table_task_review_run`；本入口不调用它们。若需要直接形成普通 B10
待批计划，可同时指定：

```text
--candidate-output-root <外部候选目录> --candidate-plan-file <新的外部计划JSON>
```

只有 `INPUT_READY` 才调用原有 `prepare_candidate_plan`，并逐字段确认准备的输入
未变化。计划仍为未授权状态，没有签发 activation 或 execution approval。
无变化时，即使传入上述参数也不生成计划。计划受阻保留 `INPUT_READY` 和输入，
另以 `candidate_plan.status=BLOCKED` 给出原因；不能误称计划已可执行。

当前普通候选仍要求 clean code、同一 open/unmerged PR 的 exact head 和独立执行
批准。真实刷新追加 ledger 可能使工作区不再干净，从而暂时不能生成计划；本轮
不自动提交新来源，不放宽冻结身份。正常运行权限及正式新旧版本衔接属于后续任务，
不能把每份新年报开一个 PR 当成最终产品流程。

## 一次最小真实 SEC 检查：待审阅、未执行

最小许可只需要：对 Marriott current submissions 发起 **1 次 GET，retry=0**，
通过已有 SEC 客户端保存响应和请求记录，provider/paid=0/0，不执行指标或发布。

| 顺序 | 请求 | 条件与上限 |
|---|---|---|
| 1 | `https://data.sec.gov/submissions/CIK0001048286.json` | 首次真实验证只批准这一项，最多1次 |
| 2 | 从该清单选出的 exact accession/primaryDocument 官方 Archives URL | 只有新年报且本地缺少主文档才考虑，另获准后最多1次 |
| 3 | `https://data.sec.gov/api/xbrl/companyfacts/CIK0001048286.json` | 只有新年报且缺少文件或目标申报年度事实才考虑，另获准后最多1次 |

代码审阅后、获得上述第1项许可才可运行（**本次未运行**）：

```bash
python3 tools/vnext_annual_update.py --refresh submissions --sec-request-limit 1 --output <新的外部JSON>
```

如将来明确批准完整条件式输入刷新，已有接线为 `--refresh missing
--sec-request-limit 3`：包含一次新清单读取，后续只补缺少项，不预先下载全部来源。
每请求零重试；HTTP失败、未知结果或原文不符合当前支持范围即停止后续请求。
CLI 参数只限制本次命令，不是新的许可签发系统。本轮真实 provider/paid/SEC=0/0/0。

新增来源通过原 `SecHttpClient` 写入独立 `evidence/annual_refresh/<唯一目录>/...`
working path，以及既有 immutable body/header 和追加 ledger；不覆盖历史材料。
如果落盘异常导致真实请求数无法确定，SEC 计数为 null，保留 fetch 次数与错误，
不会用零调用掩盖未知结果。

## 定向证据与输出示例

`tests/vnext/test_annual_update.py` 只在外部 HTTP 边界注入标注为
`SIMULATED_HTTP_BOUNDARY` 的响应，底下的选择、SEC客户端、来源保存和输入准备
均运行真实代码。没有新模型响应，没有真实 SEC 请求，没有历史来源改写。

| 场景 | 实际依据 | 关键输出 |
|---|---|---|
| 无变化 | 原仓库保存的清单，保存于 `2026-08-17T10:52:58.196463+00:00`；与 active R3 的 B10 来源比较 | `NO_NEW_ANNUAL_FILING`；FY2025，`0001048286-26-000007`；输入 null、执行 NOT_EXECUTED |
| 旧到新 | 真实保存的 FY2024 成功候选 Run，与同一份 FY2025 清单及原文对照 | `INPUT_READY`；FY2025 `2025-01-01` 至 `2025-12-31`；原文 DEI/context 通过 |
| 缺少来源 | 临时证据目录只注入清单，故缺原文/Company Facts | `INPUTS_MISSING`；逐项列 URL，不前移 FY2024 成功基线 |
| 异常 | 在临时目录注入裁剪/变更的合成清单或失败 HTTP | `CHECK_FAILED`；修订/未知日期/分片不完整/失败原因明确，不回退成无变化 |

旧到新例子证明对保存材料的前向比较和输入准备；没有声称拥有 FY2024 当时的真实
历史清单，也不证明未来在线发现。重复获取、无关8-K、代码 head 和目录变更均不会
被当成新年报。正式 pointer、root矩阵/证据/报告与原始 ledger 前后哈希保持不变。

完整运行日志与输出保存在本地
`/Users/lyuhongwang/Documents/Codex/2026-09-08/marriott-annual-update/`。
这些是离线开发证据，不能代替真实在线检查、长期运行、正式发布或 full acceptance。
未改 Reader/prompt/schema/审核/计算/调用控制/Run业务状态/Requirement；未重跑旧
资格、未恢复 PR34，也未新增调度、数据库、修订引擎或发布机制。

<!-- capability-anchor: CAPABILITY.marriott_annual_update_inputs -->
