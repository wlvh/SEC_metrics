# c5487b7 限定独立审阅

结论：**NEEDS_FIX，1 项 P2**。只审 c5487b73961b12fb336f7e59d59e6164ce32eb65 相对 22cfc2a6 的 ordinary_projection.py、ordinary_saved_result.py、test_successor_income_projection.py 新差异。没有重审 B03 namespace、完整 B03 或全公司链。

## [P2] 期间“已证明”的准入尚未处理同份原件的直接日期冲突

位置：scripts/vnext/ordinary_projection.py:109–114，及放行分支 125。

新判断把收入来源准备器的 statement_period=2025-08-08..2025-12-31 当作已被原件证明的实际期间，因而让 B01/B03 出表。限定源文件检查发现：同一 CIK 2041610、同一 accession 0002041610-26-000011、同一 RevenueFromContractWithCustomerExcludingAssessedTax/12,269 百万美元，正文四张表的 Successor 列均标为“Period From August 7 - December 31, … 2025”；对应 c-6 的 XHTML/native XML context 却是 startDate=2025-08-08。两份原件 SHA 均与保存请求证明匹配。这是两种原件表示直接冲突，不能通过收入包、Result 与 manifest 都使用 8 日就消除。

我实际从 source-only 包分别重新准备并投影 B01/B03，确认两者输出 8 日、DURATION、NOT_MEANINGFUL/ANNUAL_DURATION_OUT_OF_RANGE，未显示这个期间冲突；原保存结果也独立读到同样日期。旧分支对短期间报 PREPARED_PERIOD_CHANGED，本差异首次在当前保存路径放行这个未协调的日期，因此影响本次“有原件证明的短期间才出表”验收。无须认定 7 日必然正确，也不能直接把日期改成 7 日：需要在现有收入输入准备/投影接缝中解释并验证两者关系，不能解释则准确保留来源期间冲突的状态。补一个小的“表头 7 日/context 8 日”回归；一致来源的短期间状态仍应正常显示。年度 Calculator 不需要因此放宽。

实际原件（source-root 下相对路径）：

- XHTML：evidence/request_attempts/4c/4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d/psky-20251231.htm
- XML：evidence/request_attempts/e2/e250cec2bd7974042b5fdc8fc424014f72a0aa9fd3c840ca95fabfe85045af83/psky-20251231_htm.xml

source-root=/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/paramount-source-only-financial-20261007。review.log 的 confirmed-source-period-conflict-reproducer 给出独立标准库复现代码及四个表头，exit 0。

## 实际完成的有限验证

指定命令由我实际执行，14 tests / 22.108s / OK，无 skip：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B -m unittest tests.vnext.test_successor_income_projection tests.vnext.test_precalculated_case -q
```

另对 B01/B03 各做 15 个小变体，确认错误 company、annual 输入/申报、财年、statement/result 起止日期、跨主体授权、CIK、report end、年度窗外、instant、缺 proof、错误指标及漏一个数值 observation check 均被拒绝。错误指标的最终变体实际进入 INCOME_PERIOD_PROOF_CHANGED；数值变体只是边界探针，不是合法短期间数字。正常源包各有 1/3 个已核对 Observation，证据日期保留；这组字段一致性验证不能否定上面的原文冲突。

两份已有 B01/B03 保存结果使用 read_saved_result 独立读取，准备器设为抛错，读取仍通过；14 项指定测试也覆盖 Marriott 原年度值、预计算保存、不重选当前年、错主体/错财年/错期间拒绝及共享材料读取。默认无 income proof 的短期间继续被拒。相对基线 Calculator 和两个年度 Spec 无差异，[300,400] 年度守卫未改变；来源包重算仍得到 null，未变成年度数值。

日志如实保留我的探针中断：首版误写预设 CIK；第二版错误地假定 XML RawBlob 必在 packet.source_records；第三版使用该 venv 未装的 lxml。随后改读已保存 source_proofs 路径、使用标准库，不安装依赖。第四个原件探针的表头 8 日断言失败，调查四张实际表后确认这是本报告的真实来源日期冲突，而不是压掉失败。已完成所有 30 个字段变体的拒绝检查；没有把这些中断命令整体写成通过。

## 边界与工作量

未执行四指标完整公司 CLI、完整原生 Run/冷重放、历史包全量兼容、B02/B08 内容验收或任何 B03 namespace 重审；父方 README/公司 JSON/日志只作定位与比较，不算我重跑的整家公司证据。无真实模型/SEC请求，无子代理、commit/push、#47工作树/PR52操作；只写本目录 conclusion.md 与 review.log。

末次源码核验 HEAD=c5487b73961b12fb336f7e59d59e6164ce32eb65；三审阅文件与该 SHA 无未提交差异。

实际外层 functions.exec 22 次，子工具 29 次（exec_command 21、write_stdin 6、web 1、apply_patch 1）；保守合计 **51 次工具调用**，含报告写入后的核验。普通消息 **1 次**（最终报告），无问题/过程消息。未达到 80 次/90 分钟硬上限；没有单个检查超过 120 秒。

