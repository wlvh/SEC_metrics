# #54 公司交接实测材料

最新实际交付见 [Marriott真实首跑/复跑](live-marriott/README.md)：空来源任务经 `run` 完成31次真实SEC GET，复跑36候选独立冷读通过，39项逐项状态及3项限制、CSV/证据/摘要、来源/运行身份和main集成责任明确。此前 [local-run](local-run/README.md) 录制接线及既有消费者证据按原范围保留，不重新升级。

2026-10-04 [live2 新真实任务](live2/README.md)：从空来源新采集29+2次GET（含原31次累计62/120），36候选冷读通过、复跑0新Run，D04因SEC注入脚本严格等价被拒，材料持久存储于分支 claude/brave-cori-zbxo2v。

2026-10-04接班：[D04接收与基础集成核对](d04-handoff-intake/README.md)。按固定基线补齐工作镜像后，原LIVE f252a7a4在原基线来源上复现原Result e523b7a9并冷读一致，产品代码零改动、0/0/0；原live现场本会话不可见，与LIVE当前来源的等价待现场交接，见同目录 site-handover.json。

对应 `COMPANY-SEPARATION-v2.1-20261002`，接续 PR55 `0442896740c2f320fa999f932bc4d4ae0bfdf856`，普通父程序 `0bc24734736bb1e6cb34fbcf7ab9fece6951764e`。唯一当前执行记录在 [#54 §7](https://github.com/wlvh/SEC_metrics/issues/54)，本目录保存可复核材料。本页下方初始分离层阶段新增真实 SEC/provider/paid 为0/0/0；后续授权的Marriott真实GET另在 live-marriott 独立累计31次。没有 Ready、合并、采纳、部署或 active 权限。

`file-index.json` 逐文件登记原路径、字节数及 SHA256；`diagnostic-*.py` 是本次实际诊断脚本，包含执行目录，不能当作产品默认路径。输入来自原提交或封印归档，没有重新获取。产品命令和读写位置见 [运行说明](../../company_compute_boundary.md)。保存包、固定运行树及旧 Run 都按原字节保留；不同固定运行树的 Requirement closure 不混用。

| 范围 | 本方实跑 | 覆盖限制 |
|---|---|---|
| A 已提交基线 | 十公司导出及独立安装；Marriott B01、B13结构性 N/A、D01文本原生候选；核心未改 | JPM待刷新、Salesforce/Paramount未解依赖按原声明保留；不是十公司36项业务验收 |
| B 同历史仅目标新捕获 | 原 recorded 获取 JPM submissions；独立原核心 A08；第二次同 ledger capture、稳定 source_root 更新及重复 | RECORDED_TEST_ONLY；第二次有明确 synthetic metadata 标记，不算真实新财报 |
| B 后续无关公司／目标失败 | 同账本追加 Marriott metadata，JPM不新建候选；再追加 JPM 503，明确 INPUT_FAILED并保留旧成功 | 这组混合录制只检验更新边界，不能代替实际C |
| C #28 已保存混合增量 | 完整13捕获验证；原验证器在缺Salesforce原件的裁剪上实际拒绝；公司准入后 JPM A08、Salesforce C04独立计算 | 旧账本、行号、检查点及原获取信用保留；无新增LIVE额度 |
| C #47 已保存混合历史 | 固定接口归档完整恢复1547追加行；JPM五年来源公司包；2023-12-31 A08原生 FROZEN Run、重复、导出及冷读 | 只验证该公司／期间／指标接缝，非全部五年业务；已接收固定消费者回执，范围见 closeout |
| 实际导入中断 | 新来源移入、指针提交前强制进程退出91；另进程恢复v1并复用；重试v2后旧Run722文件未变 | 本地进程中断，非断电／所有存储后端保证 |
| 实际绑定负例 | 普通OPEN及历史FROZEN冷重放；从Run记录定位正文与对应headers，篡改均因目标校验拒绝 | 未改原执行者或未消费working副本；不是内容独审 |
| 特殊入口 | C04专用更新；基线及增量B13零AI N/A；保存D04登记输入6请求只读重放 | 后续 D04 基线完整保存判断已独立接入公司 CLI，见 corrective-results；B13 与 acquired-source 处理适配仍明确限制；旧答案不随 SEC 包交付 |
| 非root／只读 | uid1000，四类固定程序 chmod a-w，独立可写state；审计阻断原采集根及checkout evidence | 动态UID、OpenShift卷／网络／SCC和集群部署未测 |

最小修改来自实际失败：原完整历史验证在准备端完成，计算端使用独立安装的公司准入，检查完整账本元数据与携带原件／headers。基线默认零核心修改；增量普通、V14 native、历史分别形成 `issue_54_v1/v2/v3` 固定运行树，继承原规则及未完成责任。旧Run不重签；历史注册补丁只进入新历史树，未修改#28路径。

## 输入与信用

- #28：`docs/evidence/issue28_continuous/ordinary-document-identity/material-index.json` / `material.tar.gz`，完整恢复见 `mixed-28-full-restore.json`。两个漂移旧规则通过原 `ordinary-continuity-policy/native-continuity-material.tar.gz` 的成员绑定取回，未换成新规则。
- #47：[60c6b4d6固定说明](https://github.com/wlvh/SEC_metrics/blob/60c6b4d6/docs/evidence/issue47_history/collab-54/README.md)，消费者815c7820，恢复 `evidence/issue47_acquired` 原封印历史。完整恢复不是公司包通过的替代证据。实际导出曾因其intent字段 `allowance_binding_id` 与#28的 `binding_id` 不同失败，已按真实结构适配。
- D04：原 `review-5207290213/recorded-native-material-index.json` / `recorded-native-material.tar.xz`，全部824成员按封印验证。独立无.git只读目录，以原V14规则和tokenizers 0.22.2读取 Enphase登记输入；保留原source_id/input_record_id及六请求。未产生新来源包的D04 Result，`new_source_package_metric_completed=false`。原登记创建journal的路径和当前公司CLI限制见运行说明。
- Fable原探针脚本／日志仍未取得；#54 §2的五路线仅按外部报告引用。本方最小基线检查不冒称复跑其全部实验。旧E01=0、D02输出和已登记业务错误不作金标。

## 实际耗时与体积

计时为wall time。Linux Python3.12.14、uid1000，5 CPU affinity、cgroup 4 CPU配额／16GiB；部分材料并行运行，非隔离CPU基准，见 `material-environment.json`。规则／程序版本及每包携带文件绑定见 `runtime-inventory.json`、`package-inventory.json`。

| 实际对象 | 准备／安装 | 计算／重放／导出 |
|---|---|---|
| B首捕获、原核心 | 32.348246s含捕获 | A08 84.005421s；只读重复34.287575s |
| B第二捕获 | 稳定路径安装1.194141s | A08 86.776237s；重复29.171636s |
| B无关metadata／最新失败 | 捕获均录制，新增真实0 | 不变36.575350s；503后INPUT_FAILED 22.757884s |
| C #28 JPM | 完整恢复未单独计时 | A08 107.732688s |
| C #28 Salesforce | 来源导出25.020664s | C04 81.433609s；最终scope树另跑100.617192s计算阶段；重复28.978141s，导出21.279218s |
| A Marriott | 原核心树安装2.535702s | B01 38.369146s；B01/B13联跑及D01另有原JSON，D01端到端78.546383s |
| 增量JPM B13 | 独立V14后继树 | 67.965340s；重复27.584048s；导出24.569603s；B13/D04边界85.191130s |
| 实际v1→v2恢复 | 首装1.068285s；中断1.614752s；重试1.875651s | 首算66.468076s；恢复重复36.372338s；v2重算98.879645s；722文件不变 |
| C #47 JPM来源 | 完整恢复未单独计时；公司导出828.851315s | FY2023 A08首轮631.775606s；另一固定树673.282557s；重复328.134948s |
| C #47 Run及导出 | 原件、规则和证据都携带 | 原生冷重放256.505182s；初版未用既有scope导出498.101672s；导出后新位置冷读104.532697s |
| 保存D04输入 | 完整封印恢复，未单独计时 | 13.005559s；只读另进程14.442452s |

十公司来源首次导出12–19s/公司（两个准备进程）；原件约18–53MB/公司，基线共享规则4,154,123 bytes、全局账本／registry535,903 bytes。C47 JPM公司包原件302,212,896、账本／registry1,478,951、规则4,217,661、准入7,187,165 bytes；包含379个声明／捕获／头文件关联URL，携带827文件，完整全球元数据但不要求其他公司原件。运行树程序／规则约24.9–33.7MB，Git inventory另约6.2–8.3MB。历史导出342,776,691 bytes／1573文件。

B v2未压缩完整交接物63,419,441 bytes，新／变更成员5,859,698 bytes；当前安装复制完整包，没有传输去重。压缩、实际网络传输、每公司36项、完整历史业务和OpenShift耗时均 `NOT_MEASURED`，不推算30–60分钟承诺。

## 回归及审阅

13项事务／信任／来源不带处理状态单测通过，真实材料另验：只读独立trust、缺实际capture正文／headers、账本manifest变更、规则副本变更、跨公司均拒绝。普通与历史实际Run负例完整保留locator/hash及拒绝原因；实际Run所绑历史分片和前期年报缺失均拒绝，完整重哈希后冒改LIVE的真实来源包因未登记独立trust拒绝。源码编译及Git差异检查通过；capability alignment需在文档提交后按真实HEAD检查，不把未提交文档校验失败当代码漏洞。

本地fast119入口四workers／30s：117通过、两项TIMEOUT。structured单项24.625s通过；balance固定0bc24734原核心／原测试／原JPM字节对照仍30s超时，不改限时或宣称本地全绿。远端2a642e56的fast与多数原生Run检查通过，保存来源shard0被本方历史补丁日期字面量触发原审计；已改为唯一上游补丁定位，原失败测试16.698s通过。current-instant构建通过、后续负例于30分钟作业限时取消；同base旧CI曾通过，不能直接定为继承失败。最终head以GitHub检查实况为准。

历史导出已接入#47既有、按状态失效的单进程checkpoint replay scope，与计算入口一致；范围和原件验证保留。该增量固定树A08 658.217633s、导出206.498935s，保留前版498.101672s材料；两轮并发条件不同，不能当成严格速度比。向#28／#47直接回链；#28消费者已独立验证2a642e56（回执5959346910），原来源／导入／C04证据保留，不能自动升级为最新head；#47及新增结果／D04接口待消费者补验，执行者自查、录制和原生机械重放均不冒称独立业务验收。

最终自查修复了config处理登记与规则的边界：使用原封印Enphase D04登记副本，暂放在本任务独立准备程序的config，导出Marriott来源并安装baseline程序。两者均不带处理登记，前后规则绑定一致，原材料未变；随后删除仅由本测试创建的临时副本，原运行材料保留。13项短测覆盖该界面；移除处理登记的来源包及只读固定程序独立B01仍CANDIDATE_READY（46.383942s），同时禁止读取原D04处理材料。具体记录见source-only-saved-processing.json与source-only-marriott-compute.json。


后续收口见 [corrective-results](corrective-results/README.md)：B01+D01 局部更新缺口已复现并修复，新增真正公司级 CSV、原 journal／多期间结果视图及独立已保存 D04 输入。最近请求与当前结果分开，旧来源／未复核／失败／已确认无效不得作为本次成功。e536cdc 两条工作流已完整终态 SUCCESS；最终新增提交仍单独核对 CI。此前各段保持其固定探针范围，不扩大成全公司或内容验收。


消费者实际事件census缺口、普通六事件与历史C01修后、40项组件回归及Run data负例见[event-census/README.md](event-census/README.md)。#47固定8c798939的8项结果/冷读回执已到达，原编号问题在253/e536已修，新增接缝由本方实现并等待消费者按差异补验；不能自动算最新版本或业务验收。既有D04录制接线再次在最终参数入口重入，仍无LIVE信用。最终实际head CI终态在#54唯一执行队列和PR55原位登记，旧c17/413主工作流已分别完整成功。

原173–178完整LIVE D04材料已由#28在51f9cd7c交付；新的实际公司接入、完整来源等价、旧SEC版本独立准入、385.057s计算/176.720s同候选重入/175.471s公司冷出口与绑定header负例见[live-processing/README.md](live-processing/README.md)。48项组件回归与真实财报材料分列。旧13捕获混合历史已验证该场景；随后已接收 #28 对303d751f的真实52捕获消费者回执5963721452及固定文件索引；本方13捕获实验与对方52捕获验收分别登记，见 closeout。原LIVE身份、原WITHHELD发布和已保存判断责任保持，新增真实调用0/0/0，无业务/生产信用升级。

## 有限收口：固定消费者、历史重复成本及展示语义

[closeout/README.md](closeout/README.md) 接续303d751f，接收52捕获LIVE D04、12项历史事件及C04来源切换的实际消费者证据，分别保留固定版本与覆盖限制；后续历史运行树只修改公司适配，普通／处理链不受该安装分派影响。期间与跨运行版本释放的解释、限定耗时对照和最终CI身份在该处集中登记。
