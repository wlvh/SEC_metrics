# Salesforce 非自然年五年 D01 消费者

与同目录 Ford 验证沿同一 PR125 固定产品 `bc5ee891`，没有任何抽取器、期间政策或保存器改动。原 `d01-full-frame-read.json`、`d01-older-years-read-batch.json` 和 `d01-latest-years-read-batch.json` 中的最终阅读参考直接复用；早期重复标题数量不替代最终有序文本，没有新增原件阅读或模型试验。

在原 Salesforce 四指标任务中，只新增 FY2022–FY2026 五个 D01 坐标。首处理 **31.950 秒**，禁 D01 工厂复跑 **2.293 秒**，独立读取 **0.709 秒**。标题数分别 **46、45、45、43、43**，每年有序全文与原参考完全相同，单位 `text`、CSV `TEXT_QUAL`、CIK 1108524、原 accession 保持；实际日期依次为 2021-02-01→2022-01-31，直到 2025-02-01→2026-01-31。FY2026 的发行人标签保持，原 DEI 标签不重写。

五年原件 SHA 逐项与已读参考相同，保存 Evidence PASS。新 Spec closure 与旧历史参考不同，五个 Result ID 是新版本；原范围键及文字关系保持，具体身份在 `identity-and-source.json`。不强制旧 ID、不重签旧 Run，也不声称已重放完整旧 Run 所有字段。

原 20 个财务坐标与 281 个受保护文件保持，新五结果加入后 25 个当前行可读，321 个受保护文件在复跑、独立读取期间不变。没有重新计算财务指标或下载任何材料。邻近真实运行参数、stdout、CSV、时间和文件摘要在 `actual-company.json`；同一驱动只使用现有公司 CLI，不是新 runner。

可取得代码和来源恢复与 [Ford 消费者记录](../ford-fiveyear/README.md) 相同；命令改为 `--company salesforce --fiscal-year-start 2022 --fiscal-year-end 2026 --metric D01`，其余来源、外部新状态和新输出参数保留。现有旧任务读取原状态即可，无需先跑别的公司。

本次纯证据与 Ford 同一独立消费者分支，未扩大正在审查的 PR125，未进入 main；修订/继任等 D01 未完成责任保持，不取消完整五年目标。新增 SEC/provider/paid 调用均 0，没有新 Native Run、正式接受、Ready/merge/部署或 active 切换。
