# 固定代码版本的 Marriott 年度候选更新

入口为 `tools/vnext_annual_runtime.py`。它将保存的清单变化检查、原始输入准备、
B01 结构化计算、B10 原生模型候选及成功引用接在一起。正常运行使用 Issue #28 上
真实 owner 的阶段批准记录，不查询开发 PR 状态，也不要求把每份新来源提交 Git。

本阶段限 Marriott B01/B10。已有模型、完整表集合、prompt/schema、MetricSpec、
Evidence、SYSTEM Review 和 Calculator 的业务语义不变。B01 的原生入口自然附带
其他指标；这些记录保留并列明，不扩大本轮修复责任。

## 运行入口

以下目录均须为原 checkout 外的绝对路径。`initialize` 只复制当前已保存输入，
不会访问 SEC，也不会创建另一个开发 checkout。缺少模型凭据时明确返回
`STAGE_BLOCKED / DEEPSEEK_API_KEY_REQUIRED`，调用为0，且不消耗阶段执行名额。

```bash
python3 tools/vnext_annual_runtime.py initialize \
  --data-root <absolute-data-root> --output-json <new-external-seed.json>

python3 tools/vnext_annual_runtime.py stage-proposal \
  --data-root <absolute-data-root> --stage-root <absolute-stage-root> \
  --baseline-run <existing-successful-FY2024-run> \
  --review-file <independent-review.json> --output-json <new-stage-proposal.json>

python3 tools/vnext_annual_runtime.py run \
  --approval-url <Issue-28-owner-stage-comment-url> --output-json <new-run-report.json>
```

`stage-proposal` 是可核对的批准草稿，不授予执行能力。真实执行重新读取 GitHub
owner 评论，验证评论未编辑、Issue/作者/正文及受审代码、政策和目录绑定。
批准明确标记为用户委托的条件式阶段批准，不声称用户逐字审阅了未来提交。
每份输入自动形成精确计划；年度、accession、正确数值或表格位置不进入许可。

源代码必须保持干净，实际 runtime 文件集合与受审代码逐字节一致。后续仅增加
交付证据的提交或 merge，可以保持同一个 runtime tree；报告同时给出受审提交和
实际执行提交。运行目录中的规则副本按固定文件集合与代码根核对，Python 始终
从原目录加载。每个候选保存独立的原始 body/header、完整 ledger/manifest 快照，
旧 Run 不会追随下一份清单漂移。规则副本不能被调用者改成另一套 Spec 或模型。

## 本阶段许可与输出

整个阶段累计 SEC=0，provider/paid 至多1/1，retry=0。阶段开始执行前用独占文件
永久保留这一额度；换年度、计划、head、目录或进程均不会复位。HTTP失败、内容
失败、UNKNOWN、usage缺失/矛盾或实际输入超过200000均停止真实请求。usage是
执行后的接受条件，估算值不能代替 provider 实际报告值。

输出分别展示发现的申报、隔离测试的旧成功候选、新候选和当前正式结果。当前
R3已是FY2025，本阶段明确把真实FY2024成功记录作为隔离测试起点，真实正式结果
只作独立对照。这个设置验证新运行链，不冒充线上发现新年报或未见材料泛化。

只有 B01 与 B10 均成功才保存 `successful-candidate.json`。该引用必须指向本阶段
机械派生的原生 Run，并在重入时重验两指标。失败和部分成功保留原记录；发现或
准备成功不表示候选更新成功。同一输入再次处理返回 `NO_NEW_ANNUAL_FILING`，
本次新增调用为0，并另列阶段累计调用。每次输出文件必须为新文件。

本轮没有正式发布入口，active R3、root mirrors和24指标/240坐标迁移状态不变。
下一项交付仍需把该候选路径接入既有正式发布资格、版本对照、publication及
rollback/restore验收；不另造两指标发布包。其余15指标、WB-7和旧路径退出责任保留。

## 验证范围

`tests/vnext/test_annual_runtime.py` 只模拟 GitHub 和 provider HTTP 返回，禁用全部
真实 socket。它执行真实新许可校验、输入解析、WB-3、Evidence、SYSTEM Review、
Calculator和原生重验。模拟审阅和历史answer封装只证明连接行为，不能充当独立
代码审阅或新模型反馈。真实运行结果、调用数和提交身份以最终交付证据为准。

<!-- capability-anchor: CAPABILITY.marriott_annual_candidate_runtime -->

## 本次交付状态

**本阶段真实验证失败，PR38继续Draft、未合并。** 本次唯一新响应已真实执行，
B01生成成功候选，B10在原生证据门失败；不能把部分成功写成整年更新成功。

受审代码为 `0a764b9dfd9976ec28a4ba9782229c5dbcf93306`，实际执行head为
`d196e49dbda6cfe341772a05f15c669d7efadb3d`，运行代码相同。独立代码审阅通过；
此前fast 32入口、年度输入/变化检查22项通过。新runtime完整模拟链等5项通过；
来源篡改测试捕获异常类型的错误已修正并重跑通过，另有缺key/adapter混用两项
PASS。准确命令、head和重跑范围保留在原`verification.json`检查点，不改写成
一次最终head全套PASS。

[本次委托阶段批准](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5588519734)
最初在本分支尚无PR时，已由真实GitHub核对进入正常run入口并准备FY2025输入；
缺key的初次preflight当时没有消耗执行名额。用户随后提供凭据，沿同一批准继续，
没有新增政策或逐输入批准。实际运行命令：

```bash
python3 tools/vnext_annual_runtime.py run \
  --approval-url https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5588519734 \
  --output-json /Users/lyuhongwang/Documents/Codex/2026-09-08/marriott-annual-runtime/live-run.json
```

本次HTTP200，provider/paid/SEC=`1/1/0`，retry=0，actual usage为
161707 input + 580 output = 162287 total；输入未超过200000。程序给出
`CANDIDATE_UPDATE_FAILED`。B01原生候选为26186000000 USD；B10新响应给出69.3%，
但范围标签遗漏原格raw_text开头的换行：

| 字段 | 原始固定表示 | 模型返回 |
|---|---|---|
| Worldwide范围标签 | `"\nWorldwide (2)"` | `"Worldwide (2)"` |

离线原生Evidence重建返回`REJECTED / SCOPE_LABEL_TEXT_MISMATCH`。独立原文核对
确认正确表格、2025列、Worldwide范围和69.3%，但本次没有B10 Result或Review，
成功引用未推进。仅在隔离诊断副本补回该换行后，原生检查通过；这不修改原响应、
不创建新Run、不提供成功/资格/发布信用。模型、prompt、schema和Evidence规则均未修改。

失败后再次运行同一输入返回`STAGE_STOPPED / RUNTIME_STAGE_ALREADY_CONSUMED`，
新增调用0/0/0，阶段累计仍1/1/0。名额已消费，不能通过换head、目录或计划补一次。
35项正式root/ledger及原FY2024成功记录均未变化，正式R3仍是原FY2025结果。

[本次真实运行证据](evidence/annual_runtime/live/live-verification.json)、
[新旧与正式对照](evidence/annual_runtime/live/candidate-comparison-after-live.json)和
[独立原文核对](evidence/annual_runtime/live/source-audit-independent.json)均已提交。
同目录`native-candidate/`是原生Run/controller/请求/响应的逐字节审计副本，
`live-native-manifest.json`列出原目录与全部文件hash；副本不是新的执行根或批准。
原目录保留在外部阶段workspace，没有覆盖历史成功。

本阶段“新B01/B10均成功”的真实验收条件未达到，因此不自动合并/main同步。
没有继续provider/SEC调用、改提示词或放宽校验。正式发布接入、其余15指标、
WB-7和旧路径退出仍保留后续责任，不在本轮展开。
