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

受审代码为 `0a764b9dfd9976ec28a4ba9782229c5dbcf93306`。独立代码审阅与增量
保护检查通过，现有fast 32入口和年度输入/变化检查22项通过。新runtime的完整
模拟链、失败保留、新进程去重等5项通过；来源篡改用例因测试捕获了错误异常类型
曾ERROR，随后用精确原生异常重跑通过，并新增缺key/adapter混用两项PASS。
最终guard之外的长场景没有重跑为“一次最终head全套PASS”；准确命令、head和
日志见 `docs/evidence/annual_runtime/verification.json`。

[本次委托阶段批准](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5588519734)
已绑定代码、政策和累计1/1/0上限。在尚无本分支PR时，真实GitHub批准核对和原始
FY2025输入准备已进入同一 `run` 命令，但因执行环境缺少DeepSeek key，以
`STAGE_BLOCKED / DEEPSEEK_API_KEY_REQUIRED`停止。真实provider/paid/SEC均为0，
永久执行名额未消费，没有新候选，也没有声称完成真实端到端更新。

原始FY2024 B01/B10与当前正式FY2025的来源、期间和完整Result对照见
`docs/evidence/annual_runtime/candidate-comparison.json`。35项正式root/ledger
文件与阶段开始及基线main逐字节一致。真实新响应、原文核对、合并/main同步仍
待凭据解决和其余条件通过；不是新的权限批准问题。
