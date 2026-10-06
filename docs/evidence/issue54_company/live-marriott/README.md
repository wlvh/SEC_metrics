# Marriott 真实 SEC 首跑与同目录复跑

本次在 **Codex Linux 工作区**运行，UID1000、无 capabilities；不是用户本机、跨平台或 OpenShift 验收。执行用户直接批准的 Marriott 最新完整财年、累计120次GET授权。两次及修复共 **31次真实SEC GET，31次HTTP200、0失败，provider/paid 0/0**；固定同一任务账本，1次/秒、零自动重试、项目User-Agent和正常TLS。没有把RECORDED任务改成LIVE、借用#28/#47额度或新增模型判断。

第一次任务来源目录不存在。只安装固定程序、规则、公司登记、空CSV账本和完整性清单；财报原件由SEC获取。申报原文确认 **FY2025，2025-01-01至2025-12-31**，10-K `0001048286-26-000007`，主文档 `mar-20251231.htm`，2026-02-10申报。时间戳以原始UTC保存。

## 实际命令和位置

两次都在 `/workspace` 执行同一命令，默认全部39项，没有手工跳过获取或交接：

```bash
PYTHONPATH=/workspace/work/local-python-deps PYTHONDONTWRITEBYTECODE=1 \
python /workspace/work/sec-company-compute/tools/vnext_company.py run \
  --company marriott_international --period latest-complete-fy \
  --work-dir /workspace/work/live-marriott-20261004 \
  --output-dir /workspace/work/live-marriott-outputs \
  --max-sec-requests 120 --sec-allowance 120
```

这些绝对路径记录实际环境，程序不要求 `/workspace`。用户通常只需源码路径、公司、工作目录和输出目录；安装本地固定依赖见[使用说明](../../../company_local_run.md)。

- 唯一LIVE账本：`/workspace/work/live-marriott-20261004/acquisition`。
- 首跑输出：`/workspace/work/live-marriott-outputs/20261003T163448Z-f6e42f9b`。
- 复跑输出：`/workspace/work/live-marriott-outputs/20261003T171912Z-e2aade11`。
- 独立计算状态：`work-dir/company-state`；稳定来源路径为其 `source`，不可变版本为其 `versions/<checkpoint>`。
- 来源/程序/信任登记与持久状态仍分别保存。计算和原生冷读消费公司交接物，未调用SEC或读取原采集根；采集只获取来源。

## 两次实际结果

| 项目 | 首跑 | 同目录复跑 |
|---|---:|---:|
| 新SEC GET，成功/失败 | 29，29/0 | 2，2/0 |
| 来源URL复用 | 0 | 27 |
| 收到响应正文，字节 | 13,604,999 | 3,417,342（两份元数据） |
| 新建/复用Run | 30/0 | 6/30 |
| 原生冷读通过/失败 | 23/7 | 36/0 |
| 获取，秒 | 175.481425 | 27.961234 |
| 公司交接，秒 | 5.897156 | 6.385830 |
| 安装来源，秒 | 0.908389 | 1.128663 |
| 计算，秒 | 808.095771 | 393.538339 |
| 独立冷读/出口，秒 | 253.559658 | 290.572469 |
| 命令总耗时，秒 | 1243.990465 | 719.631892 |

原件按正文哈希去重为 **13,604,999字节**；重复检查两份元数据正文未变。新捕获的HTTP观察身份和准备端保存路径投影使来源checkpoint不同，不代表出现新申报或需要重算已有指标。30个原Run的manifest SHA及金融运行版本都未变。

首跑实际暴露两个问题，未把失败算成验收成功：

1. C01/E01–E05需要已有读取器的 `evidence/accession_materials` 路径，原件已在当前捕获中但未投影到保存路径。修复只在**完整来源历史验证后**从已验证、账本实际引用的正文及headers生成字节相同的保存路径副本，登记 `saved_path_origins`；原捕获、账本和原件未修改、未重取。旧基线已有该路径时沿用其目录，避免重复accession目录。
2. 7个候选的首轮冷出口因磁盘不足失败，首跑CSV如实WITHHELD。只归档本任务拥有的非活动复制材料，逐文件SHA/大小验证后保留可恢复压缩包；旧Run、规则、原来源及#28/#47工作现场不动。复跑重新独立冷读36项，全部通过。首轮失败CSV/日志保留。

另一个公司视图显示问题已修复：普通 `SUCCESSOR_RUN` 中初始空记录哈希不等于运行后追加记录哈希，不应先解释成原生记录损坏。视图先明确窗口尚未原生回读；出口仍执行原完整Run/来源/记录验证，再从实际行带出测量窗口，未放宽校验。

## 39项完整状态与真正产出

复跑矩阵含39项；其中36项有原生候选且通过独立冷读，另外3项明确待处理。**36个候选不等于36项数值，也不等于39项业务正确性已接受或正式发布。**

| 类别 | 数量 | 指标 |
|---|---:|---|
| 数值、标志及事件计数 | 18 | B01/B02/B03/B04/B05/B07/B08/B09/B10/B11、C01/C03/C04、E01–E05 |
| 文字 | 2 | C02、D01 |
| 结构性不适用 | 15 | A01–A13、B12、B13 |
| 不可比较 | 1 | B06，NOT_MEANINGFUL，保持原规则 |
| 原业务暂停 | 1 | D02，UPDATE_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED |
| 普通完整Run尚未实现 | 1 | D03，IMPLEMENTATION_GAP |
| 独立处理输入尚未交接 | 1 | D04，AI_PROCESSING_INPUT_REQUIRED |

例如B01实际输出 `26186000000 USD`，C01和E03各为3，C04为0；来自本次真实来源和既有内核，不作为财务业务金标。逐项状态、期间、原件、证据、来源和Run身份以CSV/JSON为准。

D04不是已证明必须重新调用模型：#28已登记Marriott完整旧LIVE115–118判断及Result `e523b7a9b36b787596d7de5100746a3c23b44ca336b4791d64c7df9ef7555371`，但本任务未取得完整、可独立认证的处理包、原运行程序及原SEC来源。已[直接请求#28交接](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5971226130)。接收后仍须按既有严格完整内容/期间/请求等价机制验证，不能把旧答案塞进SEC包或宣称其已与本次来源匹配；本次新业务模型调用0。

## 版本、部分重入与负例

| 身份 | 固定值 |
|---|---|
| 首跑编排源码 | `b4f97bba3539b89fa045dd221329a2f76cb5fd67` |
| 复跑编排源码 | `b8f3ac04ca82d39b8072acd7c710ff6d74f75f44` |
| 后续旧基线路径保护源码 | `0e6153c711893192d27cd2c514e26525ea1ab95e`，该分支不影响本次新空任务；定向回归覆盖 |
| 固定采集/金融程序git | `140bd8e96f9980ed18cd825bcc11402c9e48c4e2` |
| 全部36Run requirement | `issue_54_v4` / `sha256:7e577402fa98974628bf613a3a82e66d79f55385ccce117ea5d1f0cd11d49fa2` |
| 修复后准备/冷出口控制程序git | `958a1e08d786362d1372225c5d34c2f9bfaf0617` |
| 准备控制程序closure | `sha256:7e099cd4b1a27577f7d03e326d1b73fe86ede5c79974f8c643d5d9bce6f52b4c` |
| 首跑来源 | `sha256:671a25cd86baceec0cd20a6be08cbb225328ce65bf46e91fb435a80ca39da4d9` |
| 复跑来源 | `sha256:7050dd9ee6cfd0e50cbe3e2d694b6b1131c8fcc498d95579b41751fed7f3c896` |

既有任务明确固定一个新的**准备及冷出口控制**程序；原采集/金融程序和账本绑定保留，未静默更新、重签或重算旧Run。新任务从修复后源码自动安装。摘要的 `source_checkpoint_id` 与公司视图和实际安装版本两次均一致。

复跑后另进程只请求C01/E01–E05，40.593644秒，6项均NO_SOURCE_CONTENT_CHANGE，无新Run/GET；公司查询仍保留36个相同Run和Result（另有D02/D04两项无候选记录，D03由本地摘要补状态）。[partial-reentry.json](partial-reentry.json)保存全部manifest SHA；[after-partial-company-results.json](after-partial-company-results.json)为另进程回读，不把查询哈希检查冒充新的冷重放。

从实际成功C01 Run绑定解析活动来源证明，隔离副本篡改其**实际消费HTTP header**，2.028104秒被 `COMPANY_SOURCE_BYTES_CHANGED` 拒绝；原header和旧成功保持。见[负例报告](actual-run-header-negative.json)。67项组件检查通过；定向覆盖摘要一致、旧目录保存、保存路径绑定及重复配置不丢明确准备版本。没有因最后文档提交再重跑财报。

## 材料与合并准备

- [首跑矩阵](first/metrics_matrix.csv)、[证据](first/metric_evidence.csv)、[摘要](first/run_summary.json)；[复跑矩阵](repeat/metrics_matrix.csv)、[证据](repeat/metric_evidence.csv)、[摘要](repeat/run_summary.json)。CSV和摘要为实际输出原样副本。
- [对照](comparison.json)、[31次来源文件索引](sec-source-index.json)、两轮 `source-admission.json` 保存准入引用及保存路径来源映射；大体积原件、HTTP headers、账本/claims、独立trust、来源版本和原生Run保存在上述任务，不要求用户由CSV重新获取旧原件。
- [分项体积](sizes.json)是实际普通文件逻辑字节，包含各阶段不可变/冷读复制；不是网络传输量，不把重复树相加称为唯一原件大小。一次性程序安装耗时未单独测量，宿主非独占，不外推全部公司或历史五年。
- 首跑冷出口复制材料经19037个文件验证后保存为 `/workspace/work/live-first-export.preserved.tar.gz` 及索引；首跑外层CSV/摘要/日志与原始Run仍保留。这个开发现场归档不是产品运行前提。
- 历史消费者及52捕获D04沿固定已验版本复用，见[既有收口](../closeout/README.md)；没有把本次Marriott当前年试跑扩为历史五年或所有公司验收。

main固定观察 `af1984ad5f1a3598ded3626fe999d3abeffd29b9`，仍缺本地普通流程使用的来源发现/capture/ledger、普通annual/Run/update/投影、C04/native接口以及V13/V14冻结基础。**负责人#28/PR43**需确认可独立审查的完整基础接收范围；已在上述5971226130和5969467696评论请求阶段集成，未收到范围批准，不能夹带整个PR43或要求#28全部业务完成。#54负责统一入口及本次适配，#47/PR52五年接口单列，不阻塞当前年首跑。

顺序为：基础明确审查并进入main → PR55目标改main → 核对实际差异和最终集成检查 → 另获合并批准。PR55保持Draft及比较base；本次没有Ready、Merge、正式采纳、部署或active权限。

旧bbfe0743主CI37126576786的16/16作业及生成37126576801的1/1已成功，不能再登记待完成。修复提交和最后证据提交的CI必须分别读取实际终态、受测合并树和base；最新观察在#54唯一队列及PR55登记，不将上述金融/准备程序git或旧CI绿灯混作最新源码验收。
