# Ford 五年 D01 的普通公司消费者验证

本段沿既有 PR125 / `bc5ee891` 和公共 PR124 的固定代码，只补 Ford FY2021–FY2025 已形成能力的公司入口验证。共享 D01 原件读取、Evidence、Review、Calculator、期间选择、保存器和结果读口均未修改；不新增标题分类方法、模型实验或审查 PR125 的范围。

五年原件的完整阅读已在原历史分支完成，本次直接读取提交的 `d01-older-years-read-batch.json` 与 `d01-latest-years-read-batch.json` 参考。没有重读整年度或把旧答案一律当作正确；新输出仍以同一原件身份、证据与已读有序标题核对。

## 实际公司入口

在原 Ford 四指标任务中新增五个 D01 坐标，首处理 **51.340 秒**，全部通过普通公司 CLI 保存。禁止 D01 工厂的同输入复跑 **2.139 秒**，五项均 `NO_SOURCE_CONTENT_CHANGE`、没有计算；另一个进程独立读取 **0.681 秒**。

| 财年 | 标题数 | 原申报 accession | 实际期间 |
|---|---:|---|---|
| 2021 | 28 | 0000037996-22-000013 | 2021-01-01 至 2021-12-31 |
| 2022 | 29 | 0000037996-23-000012 | 2022-01-01 至 2022-12-31 |
| 2023 | 30 | 0000037996-24-000009 | 2023-01-01 至 2023-12-31 |
| 2024 | 30 | 0000037996-25-000013 | 2024-01-01 至 2024-12-31 |
| 2025 | 30 | 0000037996-26-000015 | 2025-01-01 至 2025-12-31 |

五个输出与原阅读参考逐项、按顺序一致，单位 `text`、CSV `TEXT_QUAL`、报送 CIK 37996，实际原件 SHA 也逐年与参考相同。它们描述风险披露标题，不断言风险已经发生。

原 20 个财务坐标与 281 个受保护业务文件保持；本次五个新 D01 结果加入后，共 25 个当前结果可读。复跑与读取期间 321 个受保护结果、共享输入及指针文件逐字节不变。没有重新计算 B01/B02/B04/B05，也没有获取来源。

## 新旧身份与证据

五个 Result ID 与旧历史参考不同。可确认的差异是 Spec closure 从旧参考 `06be2bd2…` 变为现已接公共 Spec 的 `2cf616cc…`；范围键相同，五年原始来源字节与已读参考相同，当前保存 Evidence 均 PASS。新值是新合法候选，不要求复制旧身份。

`identity-and-source.json` 保存具体新旧 Spec、范围和 Result ID，以及实际 Evidence；它没有声称已对本机不存在的完整旧 Run 记录逐字段重放，也没有改写旧 Run。标题一致、程序证据通过与正式业务接受分别解释，不因此增加接受数量或宣称所有 D01 年度已完成。

## 取得和运行

代码来自可取得的 `origin/task/issue47-risk-headings-consumer-20261010`；本次纯消费者证据保存在独立 `task/issue47-d01-ford-consumer-20261010`，不扩 PR125。来源沿原 PR52 已提交导出，在保留历史分支用 `tools/vnext_historical_sec.py restore` 恢复后取实际 `source-inputs` 根；已有恢复根直接复用。新状态、运行输出和读取目录必须在程序及来源根之外，读取输出须新。

```sh
python3 tools/vnext_company.py run --company ford_motor_company \
  --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 --metric D01 \
  --source-root SOURCE_INPUTS --work-dir NEW_STATE --output-dir NEW_RUNS
python3 tools/vnext_company.py results --company ford_motor_company \
  --state-root NEW_STATE --output-root NEW_READER
```

`actual-company.json` 保留真实运行参数、stdout、CSV、耗时及文件保护；`existing-reference.json` 保留原参考出处；相邻驱动只调用同一公司入口，不是新 runner。输入只读，原用户临时文件不清理。

本段仍是候选代码上的五年消费者证明，尚未进入 main；修订、继任 D01 影响等未接入限制保持。新增 SEC/provider/paid 调用为 0/0/0，没有新 Native Run、正式接受、Ready、merge、发布或 active 切换。完整十公司×39指标×五年的交付责任继续。
