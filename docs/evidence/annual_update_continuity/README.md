# PR41：受限连续更新交付与真实验证阻断

**核心接续实现和离线两轮流程已通过；本轮真实两轮验收未完成。** [PR41](https://github.com/wlvh/SEC_metrics/pull/41) 保持 Draft、未合并。一次真实请求因模型身份不符终态失败；独立原文诊断另确认错业务分组。阶段已关闭，实际新增 **provider / paid / SEC = 1 / 1 / 0**，零重试、无 UNKNOWN。实际生产 active 和原历史记录未变。

## 已实现什么

[run-once](../../../tools/vnext_annual_continuity.py) 在同一阶段许可内分开读取“发现、完整成功候选、实际发布版本”，优先处理已有待发布候选与同笔恢复，再决定是否计算。每份输入自动绑定原文、期间、原 Run/请求和确切前驱；不要求提交新输入或逐候选批准。普通无seed启动直接接续当前 active；历史演练才用成对真实旧 Run 构造 S0。

[PublicationView 原生结果读取](../../../scripts/vnext/publication_results.py) 区分当前采纳和前驱继承；[候选运行](../../../scripts/vnext/annual_continuity.py)、[快照适配](../../../scripts/vnext/annual_continuity_snapshot.py)和[发布接续](../../../scripts/vnext/annual_continuity_publication.py)复用原执行、Evidence、SYSTEM Review、Calculator、完整 Projector 与发布事务。固定规则是 annual_candidate_adoption_v3、issue_28_v8；未修改旧v1/v2政策或历史执行。每个完整版本仍是 **2项采纳＋238项继承、327公开行**；B03附带记录保留但不采纳。

范围仍限 Marriott、普通未修订完整自然年度10-K、连续主体；B01 Revenue，B10全球/可比/全系统物业。没有增加指标、数据库、第二套发布器或生产调度服务。[操作说明](../../annual_update_continuity.md)。

## 真实发生了什么

[阶段批准](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5616160149)与[代登记说明](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5616160758)由Codex按用户明确委托，通过认证wlvh账户提交。原 `_github` 边界实际回读作者、正文、位置、时间和未编辑状态。不是用户亲手输入评论，不是新增人工代码审核。一次批准固定隔离根、受审实现、永久预算和截至2026-09-11T09:13:57.750361+00:00的期限；本阶段已提前关闭，未用额度不能转用。

| 对象 | 实际状态与证据 |
|---|---|
| 隔离 S0 | 新构造的FY2023历史测试起点，原B01 OPEN/NOT_RUN和原B10 FROZEN/PASSED保持各自历史含义；不是生产回退。完整包冷读通过。 |
| 输入A / FY2024 B01 | Company Facts原生结构化链产生USD 25,100,000,000，us-gaap:Revenues，2024-01-01至2024-12-31（366天），accession0001628280-25-004818；独立原文与计算核对通过。整体成功引用未前移。 |
| 输入A / FY2024 B10 | 请求deepseek-v4-flash，响应deepseek-flash；原生FAILED_TERMINAL，DEEPSEEK_MODEL_IDENTITY_MISMATCH。没有原生Evidence、Review或B10 Result。 |
| 原响应内容诊断 | 未改原响应的Reader诊断可解析；真正Evidence拒绝ANNUAL_SCOPE_VALUE_GROUP_MISMATCH。69.7来自Company-Operated的row18，不能用之后row19的Systemwide分组标签证明；原表Systemwide Worldwide在row28为69.8。诊断不追认失败Run成功。 |
| S1、输入B与S2 | S1未产生；FY2025第二次真实请求未执行，S2未产生。不把离线回放的S1/S2冒充本轮live产物。 |
| 重入和触发 | 无凭据run-once读取原失败后拒绝，未增加请求。真实有限trigger上限3次，仅启动1次同一CLI；子进程exit2后停止，running=false。外层exit0仅表示触发器停止。 |
| 关闭 | close-stage返回STAGE_CLOSED；真实批准核验后再次执行许可检查得到CONTINUITY_STAGE_CLOSED，累计1/1/0。 |

真实请求ID `8483ddda-af4f-43aa-89ef-353e62c8e005`；execution ID `sha256:3963c683abb728a6d8daa557fce758c0777702ad90bb31aa78f69f072d270ca7`；原响应文件SHA-256 `a1a896ffb1b63ff3b4141baaba1ce7b73ccc87b58be51dcc80cebd734e141f78`。usage为输入159653、输出776、总160429，cache hit0/miss159653；输入低于200000不代表整体接受通过。调用计数取原生marker、attempt与terminal，不取下述旧检查子步骤字段，也不依据零金额推断未付费端点调用。

[真实命令与日志](live/first-run-command.json)、[完整原始返回](live/first-run.json)、[原生失败候选](native-first/outcome.json)、[独立来源审计](checks/independent-live-first-source-audit.json)、[独立失败收口](checks/independent-live-failure-closeout.json)、[原内容诊断](checks/independent-live-first-content-diagnosis.json)、[关闭记录](live/close-stage.json)。

## 为什么没有自动修复后再抽一次

直接读取的[供应商官方变更记录](https://api-docs.deepseek.com/updates/)和[当前入门说明](https://api-docs.deepseek.com/)确认：2026-09-10旧V4 Flash退役，旧请求名转到V4.1 Flash。这是模型更换，不能当作同一模型的排版别名。搜索引擎最初仍返回上周旧说明，结论依据直接打开的当前官方页面。[调查记录](live/provider-retirement-investigation.json)。本轮没有模型更换权限，不能使用第二笔或条件名额原样重抽。

另有一个**仍未修复的输出范围问题**：run-once继承了检查子步骤的顶层`provider_paid_sec_calls=0/0/0`，离线成功分支还保留`execution=NOT_EXECUTED`，与整体终态/原生累计counts并列会误导调用者。预算底层没有归零。本次原JSON不改；已提供[明确未应用的最小补丁](methods/proposed-output-scope-fix.patch)及[范围说明](methods/proposed-output-scope-fix.md)，把检查字段收进inspection、整体执行状态按原生结果填写。补丁只有语法检查，未接入/未获运行信用；应与下一受审版本接入，不能原地改已执行v8身份。**这是PR41的待修项，不把源代码交付称为无阻断完成。**

原先阶段提案序列化Decimal的工程错误已修复；修复发生在批准与任何业务请求之前。原部分输出、原预算登记及错误日志保持字节；仅在stage不存在、budget只有完全一致registration时可接续。随后两项测试准备缺失ledger也已修正并保留失败日志。[修复说明](checks/pre-grant-output-fix-summary.json)。

## 代码、规则、运行与版本关联

| 身份种类 | 实际身份 |
|---|---|
| 受审/真实执行 Git commit | `fce015270de0cc4a265ce0fb0d2179ef11ef98a7` |
| runtime对象内容ID | `sha256:b6eaffece6494de8188eee6b23d2bf2ec34a4ed898e22997a90498c4ccf2c650` |
| 测试身份 | `sha256:96c8b6cdcea29dfa38791848d2b18be6abac1eee843797bd1d5f5e10d80f04f0` |
| Requirement closure | `sha256:c3c8d40648c0bfefe8209458142754888dfd0bb87df2c3f43a3ed01a0e83ecb1` |
| stage对象ID | `sha256:7db4fef84baa329b7c17effa9808ae55244d08ec27e9cc318302044622231688` |
| 永久budget registration ID | `sha256:8c8bf0db08e434f9138164be8a5bf9050436baa0f1d71f9019bd214ffd52411f` |
| 真实隔离S0 publication ID | `publication_b1f491c0005ce616d1f9c9ea8438e6c60fb5628a60863a64d8982058c27a4335` |
| S0 manifest文件SHA-256 | `31464cda96d50cd92a29de0df3ff3f4ffe4a5957e102a895fc3257ce057397ca` |
| 正式active（未变） | `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59` |
| 正式manifest文件SHA-256 | `ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec` |

runtime身份是约定生产目录与两份历史政策证据的path→文件SHA/size集合内容ID；测试身份是`git ls-tree -r HEAD tests`文本的内容ID。它们均不是Git tree对象。对象ID、manifest字节哈希和Git commit分别核对。每条真实命令保存实际argv、根、起止时间、前后head、退出码、完整日志SHA；复制文件另列[字节对应索引](file-provenance-index.json)，不改原内部路径或身份。

## 离线正反例与保护

- **完整离线验收**：ab49924上的3项真实材料集成全部通过、无SKIP，3807.637秒：正常current-active起点、丢失成功引用/指针中断恢复/部分失败、同版S0→S1→S2及重复输入。只在GitHub/HTTP外部I/O和既有故障点注入，没有mock核心validator。[命令](checks/offline-acceptance-04-command.json)、[日志](checks/offline-acceptance-04-command.log)、[两轮绑定](offline/binding.json)。其中原生测试controller2/2是保存响应回放，实际业务0/0/0。
- **离线版本链**：S0=`publication_d410b40c385a517373a5fc47b85d18528e97fe5b20a2597a52bb679844baccb8` → S1=`publication_abef3a708bb825670d8b1a6283d1c10a1ba1501cf3964a4f4ce6e6bef7bc2e29` → S2=`publication_be9d82ab2818679e5af46da83e0fa8056b89b377978574fe6b950d30afc05f6f`；第二轮确实继承第一轮。源为完整已知历史年报，历史可见性明确模拟，不是未见材料或在线发现。
- **独立复核**：执行前完整/增量代码记录分别区分亲跑与阅读日志；26项内容正反例包含错源、错单位/期/业务范围、脚注、未知别名、真正同值错组。[原复核](checks/final-code-review.json)、[最终执行前增量](checks/final-code-review-fce0152.json)、[内容回归](checks/independent-content-regression.json)。后者保持旧日志身份，没有将ab49924的长集成改贴fce0152。最后增量未改原生业务/发布语义。
- **持续测试覆盖**：[fce0152 CI34459084103](https://github.com/wlvh/SEC_metrics/actions/runs/34459084103/job/102812329480)的38入口全部通过；新增模块实际14项/OK。[原日志](checks/ci-fce0152.log)。交付归档提交仅加说明/证据，运行代码与测试树不变。
- **最终冷读与历史兼容**：fce0152新进程、OS禁止网络/生产写入，实际正式包、真实S0的矩阵/证据/原始来源与14镜像一致；原v1审阅ZIP按保存SHA核对后在外部解压、旧v1与R3真实验证通过。[当前/S0](live/cold-read-final.json)、[v1/R3](checks/historical-compatibility-final.json)。R3未嵌入B01/B03完整原生图，明确返回不可用；旧公共结果/证据和B10原生来源仍可读，不从CSV猜Run。
- **历史保护**：[最终保护记录](checks/protection-final.json)核对5528个未改原文件、全部77条原refs、8个stash、17个其他worktree及实际active不变。没有新增SEC，原清单984行；实际业务阶段用OS写入白名单，冷读禁网。GitHub批准及公共供应商文档读取如实单列，不称整个阶段无网络。

## 最后状态和剩余决定

PR41保持Draft，不合并；工作区交付在原目录的干净、已推送`task/annual-update-continuity`，main和历史分支未推进开发提交。阶段关闭、触发器停用，实际生产权限未签发/active未切换。PR38历史2/2/0不清零，本轮1/1/0另账。

尚缺：允许何种替代模型/合同及有限后续验证的明确决定、输出字段补丁的受审接入，以及该实现上的两轮新provider成功。**本轮未达到退出Marriott试点的验收线，所以未进入R5。** 条件满足后下一责任仍是有限R5迁移、按实际需要补WB-7并逐批证明旧语义生产/补数退出；R4、R6、Rf及十家公司×39指标目标不删减。

完整原材料和运行现场继续保存在checkout外；审阅归档及其文件身份见同目录`review-archive.json`。原失败、修正、历史回放、新响应诊断各自保留，不能互相替代信用。
