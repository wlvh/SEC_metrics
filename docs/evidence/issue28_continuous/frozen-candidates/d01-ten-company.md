# 十公司D01：普通保存输入、真实冻结与新进程冷读

十家公司均从各自正常保存输入自动准备，使用不变V12方法生成完整原文标题集合，真实调用`validate_and_freeze_run`，随后以新的Python进程`load_frozen_run`。本批 **10/10 FROZEN / validation PASSED / 新进程冷读PASS**，共410条标题；没有失败、人工选标题、参考答案或修补共享规则。

实现提交：`180a05e816a6f2b4014f403768458506d56c96c9`。Requirement closure：`sha256:b275dc81a817283d60593d58fbe31ca7668222e0d1a7f779b4339d65947dcf67`。执行结束再次核对全部V12 execution authority和五snapshot相对该提交无漂移。

| 公司 | 原文标题条数 | 实际期间 | 冻结/验证 | 新进程冷读 |
|---|---:|---|---|---|
| Marriott International | 34 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Southwest Airlines | 34 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Ford Motor Company | 30 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Pfizer | 28 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| JPMorgan Chase | 57 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Salesforce | 43 | 2025-02-01 → 2026-01-31 | FROZEN / PASSED | PASS |
| Lumen Technologies | 50 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Macy's | 36 | 2025-02-02 → 2026-01-31 | FROZEN / PASSED | PASS |
| Paramount Skydance / Paramount Global | 38 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |
| Enphase Energy | 60 | 2025-01-01 → 2025-12-31 | FROZEN / PASSED | PASS |

期间由正常准备读取原件；非自然年度保留实际起止日期，FY字段保存在index中，不用自然年假定替代。Paramount D01为申报全文的2025全年窗口；此前C03薪酬指标实际测量窗口为2025-08-07至12-31，两者没有强行混成同一期。

每家公司均在新的独立data/run目录生成材料，目录内没有.git。每次冷读使用不同于父进程的全新Python进程；子进程禁止所有socket事件以及所有子进程（包括git），无触发记录。读取依赖当前可信安装代码，这不是独立代码安装包或新目录重定位验收。

冻结前后及子进程冷读核对完整Result、整个record graph、所有SourceReference/正文SHA、完整data树（含header、metadata、ledger）、实际期间、SYSTEM Review及其渲染文件，均完全一致。10例各有1条SYSTEM Review，不把标题中的风险说成实际已发生。实际active、matrix/evidence、报告、validation manifest及原始ledger/ledger manifest前后hash均未变。

实际调用provider/paid/SEC=0/0/0。本批总案例耗时380.26秒，JPM约95秒；这是完整材料重放耗时，不能记成单JSON往返。

## 命令与文件

实际命令：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 /tmp/sec_metrics_issue28_continuous/pr43-review/run_d01_ten_company_batch.py /tmp/sec_metrics_issue28_continuous/pr43-review/d01-ten-company-180a05e
```

工作目录：`/Users/lyuhongwang/Developer/SEC_metrics`。复跑需给脚本新的输出目录；脚本拒绝覆盖既有批次。

`index.json`保存每家公司完整Run/result/validation/content/audit身份、来源申报/CIK、段数、期间、子进程PID和真实命令。每家公司目录包含installed-input、自动标题proposal、before-freeze、frozen-manifest、cold-read、cold-process.log和outcome；上一级`d01-ten-company-180a05e.log`为批次实际日志。此前两例材料未重写。

## Run索引

- `marriott_international`: `run:normal-saved:0c9e57e53239508bd69512b6f1fe21fa24ea16284f4115ec235d2e0628945f3c`
- `southwest_airlines`: `run:normal-saved:4fd988dd4bc8fdd3073e8d4464a2a938d177af9a918d24cbf54fe1cb53d285e0`
- `ford_motor_company`: `run:normal-saved:9e7683ca011650087b70f808facad2c6e2cc43acb3bc0eee69b0e7fb3a464659`
- `pfizer`: `run:normal-saved:85dc8f82c91fae243b6a46db37fcb6eaccbbc227816f83026fdd5426c67fd8e5`
- `jpmorgan_chase`: `run:normal-saved:34265b70f6c68a39c6d0f7a8857379738c688ffb943ffdc419eb87d9e6efee87`
- `salesforce`: `run:normal-saved:1481133700da359ce8b18f84fae88da1c788196ff5ebbf46aefb20a8a663c104`
- `lumen_technologies`: `run:normal-saved:974080e94b6752039ad5be625123caebcf905c6268cedc9fa7a3e7299e1545b6`
- `macys`: `run:normal-saved:33205a2253446f1d4044bfd8e330e0091408adce8286e1567220c492a643b709`
- `paramount_skydance_paramount_global`: `run:normal-saved:e548ed6496abfd00d7b9ac1a35f9a97507510a4921f84c6f71ed82b513ef8e04`
- `enphase_energy`: `run:normal-saved:b9345b8c491d369c624b824ca2be5a1a2edc9ac594b7fa665da95ebca6a54938`

这是既定十家公司已保存原文上的D01标题级能力验收。它没有验证新SEC获取、长期更新触发、任意新披露样式、风险发生/未披露判断或其他R6语义，没有正式采纳/发布/active切换，也不宣称Issue #28完成。
