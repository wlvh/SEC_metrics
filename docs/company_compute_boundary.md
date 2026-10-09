# 公司级来源交接与独立计算

**版本：PR57 已交付 main 的原生交接接口；下列安装/信任命令仅适用该固定版本及保留的原生任务。** 对应历史 `COMPANY-SEPARATION-v2.1-20261002`；代码交付不等于业务接受、部署或发布。

PR67 的新普通记录路径在候选分支实现，使用已保存 `source-root`，不恢复本页的独立信任/递归权限链作为新路径前置；候选的新在线安装仍未接通。版本对应命令见 [公司运行](company_local_run.md)。来源/计算分离、原件与引用、公司/期间、调用计数、原子写入、锁及恢复继续保留。

当前公共及当期集成、唯一队列见 [Issue #28](https://github.com/wlvh/SEC_metrics/issues/28#run-test-simplification)，历史消费者由 [#47](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006)维护。[#54](https://github.com/wlvh/SEC_metrics/issues/54)仅保留已交付来源和证据。本页用于承接最终的稳定使用说明，不复制 Issue 进度或建立另一份待办。

## 目标边界

获取/来源准备输出明确的交接来源；计算只读取这些来源和自己安装的程序、规则及受控信任状态。计算不能回读原采集工作区、私有 journal 或 SEC，也不要求其他公司先完成。公司是运行和状态隔离单位，指标及结果继续复用已有 Run、Result、证据和读取接口。

共享规则、公司注册信息和必要的全局账本元数据可以保留；实际公司原件及其前期、历史分片、主体角色依赖必须明确。来源自洽哈希不能代替可信获取凭据，导入不能把 recorded 标为 LIVE。一次计算固定一个来源版本，失败或导入中断不破坏上一有效输入及运行。

## 与已有能力的关系

[Issue #28](https://github.com/wlvh/SEC_metrics/issues/28) 保留普通指标、正常更新、统一生产与旧路径退出责任；[Issue #47](https://github.com/wlvh/SEC_metrics/issues/47) 保留五年历史期间、依赖和业务验收责任。#54/PR57已交付两阶段边界；后续公共接口由#28维护并适配，历史消费者由#47验证，不等待原#54执行者。

首个内网平台为 OpenShift。镜像、任务、卷、网络、脚本及内网 AI 接线留给下一 Issue；本期没有集群部署或 OpenShift 验收。新增真实 SEC/provider/paid 调用为 0/0/0。

## 保留原生版本的使用与证据

main 固定原生版本使用 [单命令 `run` 与独立 `acquire`](company_local_run.md)；PR67候选只用该页保存来源示例，不能自动套用本文安装链。本文分阶段命令继续用于两个环境分别调度、诊断和既有来源恢复；新任务的空来源路径与保存混合来源恢复分别说明，不能相互充当验收。

`tools/vnext_company.py` 提供 `export`、`install-runtime`、`install`、`compute`、`results`、`export-results`、`export-processing`。所有路径必须显式传入、绝对且无 symlink，输出不得覆盖程序或 active 工作区。下面的 `/srv/sec-metrics` 是部署方选择的示例，不要求该目录、个人 HOME、root 或特权功能。

来源准备端先用原机制校验完整来源历史。A 类读取已提交基线；B 类使用原 recorded 获取会话，在同一个 `ledger.root/source-inputs` 追加目标公司；C 类可以在准备端恢复合法保存的混合获取归档。不能删账本行、改行号、拼接不同历史或另设真实额度。然后执行：

```bash
python3 tools/vnext_company.py export \
  --source-root /srv/sec-metrics/prepared-history/source-inputs \
  --output-root /srv/sec-metrics/transfer/jpmorgan-v1 \
  --trust-root /srv/sec-metrics/source-trust \
  --company jpmorgan_chase --metric A08
```

公司包保留整个请求账本、manifest、注册信息和原检查点元数据；按经验证的依赖声明及目标公司捕获引用收集原件和 headers，包括 legacy 保存位置、旧尝试、前期、窗口外、前身 CIK、历史分片和事件头文件。全局元数据可以出现其他公司，其他公司原件不会随包交付。来源包没有 Result 或 AI 答案前置。已保存的 B13/D04／历史判断登记属于处理状态，其现有 export 路径从规则收集及程序安装中明确排除；不能因文件位于 config 就携带。

`source-trust` 是准备端安装的独立信任登记；计算端只读。包自己携带的 JSON/哈希不能注册自己，也不能把 recorded 提升为 LIVE。允许保存原获取信用，但不因此获得新获取或生产权限。

计算运行树由原固定程序安装。A 类 baseline 默认不改核心文件；增量包使用 `--kind ordinary` 的独立后继运行树。原 `issue_28_v13` 文件、旧 Run 和闭合额度保持原字节；后继只登记公司来源准入与新运行身份，业务规则继承原版本。代码变更发生在新安装树，不写回 #28 checkout。历史另用 `--kind historical`，从 #47 固定树安装，应用其提供的注册补丁，继承 `issue_47_v1` 并形成独立 `issue_54_v3`；不能把该补丁打入普通树。

C01/E01–E05 是实际探针证实的基线例外，也使用 `--kind ordinary`。原事件函数会把已取得 headers census 与程序 checkout 中的原件比较；只读程序没有 SEC 原件。新安装树仅把该比较的权威端接到 `company_event_census.installed_event_filings`：先认证外部 source-trust 点名的公司文件闭包，再核对实际 headers 集合精确相等，复用原窗口／form／accession 解析和补充申报检查。原生安装器在基线账本的快速路径之前保留公司准入及其原件闭包，使 Run 的 data 根也能认证同一 census；不删除完整性检查或让 data 根自证。#47 的历史事件 code-object 遍历复用此分派，历史 coherence 检查保持。所有改动只应用于新固定树并绑定新的 closure；旧 Run 仍用原树，不改签。原普通 journal 拒绝运行时 closure 改变；新规则树使用独立更新历史，保留旧 journal，不重置配置或删尝试。

```bash
python3 tools/vnext_company.py install-runtime \
  --kind ordinary --output-root /srv/sec-metrics/runtime/ordinary-v1
python3 /srv/sec-metrics/runtime/ordinary-v1/tools/vnext_company.py install \
  --package-root /srv/sec-metrics/transfer/jpmorgan-v1 \
  --state-root /srv/sec-metrics/state/jpmorgan_chase \
  --trust-root /srv/sec-metrics/source-trust --company jpmorgan_chase
python3 /srv/sec-metrics/runtime/ordinary-v1/tools/vnext_company.py compute \
  --state-root /srv/sec-metrics/state/jpmorgan_chase \
  --trust-root /srv/sec-metrics/source-trust --company jpmorgan_chase --metric A08
```

规则只有计算运行树中固定的一版。包携带经校验的同版 config/catalog 和必要根目录定义；导入逐文件核对。Run 安装仍保留自己的旧规则与原件副本供回读，不为省空间删除。

| 位置 | 准备/安装 | 计算 |
|---|---|---|
| 固定程序、规则、Requirement 与 Git inventory | 构建新运行树时写 | 只读，计算不写镜像 `.git` |
| 来源交接包 | 准备端创建不可变目录 | 导入读取 |
| 独立来源信任登记 | 受控准备端写 | 只读 |
| 每公司持久 state | 安装写版本、intent、pointer | 写原生 Run、journal、结果与证据 |

同一 history 的运行路径始终为 `<state-root>/source`；物理版本在 `versions/<checkpoint-id>` 保留。导入和整个计算持有同一个目录锁。导入先完整检查暂存版本，再替换稳定目录并提交 `current_source.json`。重启按提交指针恢复，首次中断的未提交目录被隔离；旧结果保持。`latest_import.json` 保存成功、重复及显式失败；进程突然退出可能留下 `IN_PROGRESS`，下一进程按已提交指针恢复，未完成记录不能当成已导入。目录别名不能绕过这些检查。当前实际验证为 Linux 非 root uid 1000、只读程序、独立可写 state；动态 UID 与真实卷/网络行为未测。

普通 `compute` 复用每指标 update controller；C04 调用专用四 form 更新入口。增量 B13 的零 AI 结构性 N/A 使用单独 `--kind native` 固定树（继承原 V14、后继 issue_54_v2）；普通树明确返回 NATIVE_RUNTIME_REQUIRED。完整已保存 D04 可通过独立处理包和其原 V14 固定运行树接入。基线直接使用其独立 SEC 公司来源；acquired 同源复用还需单独准入的原基线公司来源版本，以及完整原文、主体／期间、来源集合和实质请求责任的等价检查。新账本完整保留，不裁行或转换成基线。B13 判断登记、历史处理或变化后的来源仍返回明确待处理／拒绝；不计完成或请求新模型调用。来源包仍不携处理答案。

历史准备从固定 #47 树调用 `export --history-years 5`，使用其 `declared_frame`；计算选择历史固定树并加 `--report-end YYYY-MM-DD` 或 `--fiscal-year YYYY`。这些消费者的实际通过范围须看证据索引，不能由接口存在推出五年全部业务验收。

`compute` 返回本次请求报告，并保存 `latest-execution.json` 与薄执行观察。`results`／`company-results.json` 从原每指标 journal、期间 current 指针和 native Run 生成公司视图；局部请求不删除其它指标及年份。既有成功指针仍由原消费者管理，不新增正式选版或 active。视图区分创建来源、最近核验来源、当前来源匹配／失败／未复核、Run／Requirement closure、最新请求及已确认缺陷。

`period` 保留兼容含义：Run 的归档坐标（`period_role=RUN_ARCHIVE_COORDINATE`），不是事件的计数窗口。`measurement_period` 从原生结果读取，标明仅核文件哈希还是已独立重放；缺少可核原生记录时为不可用，不用财年推测。Paramount FY2025 的归档坐标从2025-01-01开始，六事件实际窗口从2024-01-01开始，均到2025-12-31。公司CSV额外列出归档期间与测量窗口；原投影期间字段保持原义。

缺陷释放仍须同时匹配结果编号和 Requirement closure。相同结果仅在其它运行版本已释放时，显示 `CURRENT_RUNTIME_RELEASE_REQUIRED`，`defect_holds` 保留原释放的运行版本、阅读与接受引用，公司值仍扣留。这表示当前版本未被既有登记释放，不表示新发现了内容错误；结果不同或没有适用释放仍显示 `CONFIRMED_INVALID`。机械回读不替代内容接受。

### 来源交接、局部更新和公司导出的完整示例

下面以已保存 Marriott 基线的 B01/D01 为例；目录是调用方选择的挂载位置。准备端负责原完整来源验证和受控安装信任，计算端只接收该公司包、固定程序和独立信任登记。接入采集器、卷/镜像及网络是下一期。

```bash
# 在受控准备端执行，PREP 是本交付源码，FULL_SOURCE 是已有受信完整来源。
PREP=/srv/sec-metrics/preparation/program
FULL_SOURCE=/srv/sec-metrics/preparation/source
TRANSFER=/srv/sec-metrics/transfer/marriott-baseline
TRUST=/srv/sec-metrics/source-trust
PROGRAM=/srv/sec-metrics/runtime/baseline
STATE=/srv/sec-metrics/state/marriott_international
python3 "$PREP/tools/vnext_company.py" export --source-root "$FULL_SOURCE" \
  --output-root "$TRANSFER" --trust-root "$TRUST" \
  --company marriott_international --metric B01 --metric D01
python3 "$PREP/tools/vnext_company.py" install-runtime --kind baseline --output-root "$PROGRAM"
# 将 PROGRAM、TRANSFER、TRUST 分别交付到计算端；程序和信任登记可只读。
python3 "$PROGRAM/tools/vnext_company.py" install --package-root "$TRANSFER" \
  --state-root "$STATE" --trust-root "$TRUST" --company marriott_international
python3 "$PROGRAM/tools/vnext_company.py" compute --state-root "$STATE" \
  --trust-root "$TRUST" --company marriott_international --metric B01 --metric D01
# 只更新 B01，D01 及其原生 Run 仍在公司视图中。
python3 "$PROGRAM/tools/vnext_company.py" compute --state-root "$STATE" \
  --trust-root "$TRUST" --company marriott_international --metric B01
python3 "$PROGRAM/tools/vnext_company.py" results --state-root "$STATE" \
  --trust-root "$TRUST" --company marriott_international --runtime-root "$PROGRAM"
python3 "$PROGRAM/tools/vnext_company.py" export-results --state-root "$STATE" \
  --trust-root "$TRUST" --company marriott_international --runtime-root "$PROGRAM" \
  --output-root /srv/sec-metrics/output/marriott-update-001
```

最后目录包含公司 `metrics_matrix.csv`、`metric_evidence.csv`、视图、本次执行报告及原生输入/结果索引；输出目录必须是新目录。后续来源包仍安装到同一 `STATE/source`，计算固定一次版本。增量普通用 `--kind ordinary`，历史用独立 `--kind historical` 并传 `--report-end` 或 `--fiscal-year`；不要用新运行树继续旧闭包的普通 journal。混合运行树导出重复提供每个创建树的 `--runtime-root`。D04另按下面的独立处理示例接入。

`export-results` 冷重放候选并保留每项 native Run/data/rows，同时生成公司 `metrics_matrix.csv` 和 `metric_evidence.csv`。先复用既有投影字段，再追加身份和状态列；旧值保留原期间，失败／未复核不算本次更新成功。`--runtime-root` 可重复，混合普通／历史／原生闭包分别在其固定树的新进程读取；来源规则也须与其中正确树逐文件匹配。单项重放失败形成 WITHHELD 行并返回 EXPORTED_PARTIAL／退出2，其它候选仍导出；缺少全部必要来源规则树在消费前拒绝。`--defects-file` 只读原 known_result_defects 登记，按精确结果／期间／解除身份扣留；未提供登记不代表没有缺陷，机械重放不授内容验收信用。旧原生字节保持，生产发布仍由原流程决定。

实际实验、失败位置、分项体积和耗时见 [证据索引](evidence/issue54_company/README.md)。十家公司来源导出不等于全部 36 项或 30–60 分钟验收。Fable 外部报告保留原信用，尚未取得的原脚本/日志不记成本方复跑。

<!-- capability-anchor: CAPABILITY.company_import_transaction -->

<!-- capability-anchor: CAPABILITY.company_saved_processing_exact_source -->

## 保留原生版本：保存处理输入的接口与限制

#28 原接口为 `capacity_assessment_input.load_registered_input(data_root, source, requirement, mode, input_record_id)`；`source` 必须由同版原工厂重建并保持原 source_id/请求集合，登记记录不能改签成新输入。早期只读探针核对合法旧 D04 录制材料、原 V14 规则及固定 tokenizer 0.22.2 的6个请求，当时未创建 Result。收口探针已由下述公司入口生成原生 Run 和公司行；全程未调用模型。

原登记创建端的 `_journal` 位于原固定运行树 `.git/ordinary-source-authority/{capacity-assessments,going-concern-assessments}/<mode>`。本期适配只读完整保存记录，不重新 register，不读取私有 ledger，不新增模型调用。受控准备端 `export-processing --installed-root <原已安装V14输入树> --output-root <处理包> --runtime-output-root <原版只读程序> --trust-root <独立处理信任> --company <公司>` 通过原 loader／来源工厂认证完整 D04，然后分别交付原登记字节、来源身份及原代码。程序不携 SEC／处理登记；只读 Git inventory 属程序，写入不发生在程序 journal。计算加 `--processing-package`、`--processing-runtime`、`--processing-trust-root`；SEC 来源和处理信任分别检查，旧 source_id/input_record_id、请求／响应／接受及 Requirement 不改签。处理源暂存及原生 Run 只写公司 state。

首个材料为合法 RECORDED_TEST_ONLY 六请求，保持原信用，无新业务验收。既有 defined-absence 投影可形成 TEXT_QUAL 公司行，同时保留原 Result 的 WITHHELD 发布状态；这种投影沿用原能力，不能将其说成正式发布。缺输入、错误公司、处理原件／运行树篡改、没有独立信任或与原 source_id 不匹配时明确拒绝，旧结果不改。现已接收 #28 原173–178完整 LIVE 登记及原V14运行树索引；原处理输入的 LIVE 身份不会授新调用、生产或整家公司内容信用。实际接入范围和失败材料另见证据，不以录制证明真实调用。

保存处理接线支持普通基线 D04，以及能通过既有 `capacity_update_input.source_equivalence` 完整检查的 acquired 公司历史。历史树收到这些处理参数时显式返回 `COMPANY_PROCESSING_HISTORY_ADAPTER_NOT_IMPLEMENTED`；参数缺原运行树或本次未请求 D04 也拒绝，不默默忽略已交付的判断。历史处理登记的既有消费者仍由 #47 维护；本期没有把当前普通判断套到其他历史期间。

acquired 复用显式传入 `--processing-source-version <原基线公司SEC包>`；它同样由 `source-trust` 认证、必须属于本公司且准入D04。这个包只能来自合法保存的原SEC版本；不得截取当前账本前缀或重新获取原件来构造它。当前完整混合历史仍在 `<state>/source`，原版本另行只读，处理请求／响应仍只在独立处理包内。程序先以当前固定ordinary/native树重建完整当前语义来源，再用原V14的等价接口比较原处理source：原文／主体／期间／实质请求任何变化都拒绝，不按少数组拼接。

通过后，原V14仅用原公司SEC版本计算；公司state同时保存当前公司来源的完整不可变快照、等价证明及原版本checkpoint。原Run／Result／请求／响应／接受／Requirement保持原身份；单独的当前匹配证明不授新获取信用。公司CSV同时列出当前checkpoint、原SEC版本checkpoint、等价id、原来源信用及LIVE/recorded处理mode。冷导出重建当前来源并重验等价，不能单凭保存的JSON授信；须通过重复 `--runtime-root` 提供原V14与该证明创建时的固定ordinary/native树。再次计算可在调用者自己的固定树核验整个相同语义包，保留旧Run及旧证明，不重签。

```bash
python3 /srv/sec-metrics/runtime/ordinary-v1/tools/vnext_company.py compute \
  --state-root /srv/sec-metrics/state/enphase_energy \
  --trust-root /srv/sec-metrics/source-trust --company enphase_energy --metric D04 \
  --processing-package /srv/sec-metrics/processing/enphase-d04 \
  --processing-runtime /srv/sec-metrics/runtime/original-v14 \
  --processing-trust-root /srv/sec-metrics/processing-trust \
  --processing-source-version /srv/sec-metrics/transfer/enphase-original-baseline
```

程序／来源／信任可只读。导入只在私有暂存根临时增加跨父目录rename所需权限，再恢复不可变版本的原模式；输入包不改。处理子进程工作目录为外部工作区，私有副本可写并可清理；不将开发checkout、个人HOME、root或特权当作前提。

导出结果带相对 native 路径及逐文件索引。读取旧 Run 应选择创建它的固定运行树与独立 trust；程序、Requirement 或 source admission 的绑定副本必须保留。历史计算和冷读复用 #47 已有单进程、按状态失效的检查点重放、输入派生及不可变XBRL解析作用域；每个新数据状态仍完整核验，每个结果仍独立冷读。新历史安装树把外置来源信任目录同时纳入派生状态键及审计读集合，信任改变会失效，不豁免原验证。六指标仍分别安装独立数据目录；本期没有长期缓存或共享可变输入。

<!-- capability-anchor: CAPABILITY.company_result_period_and_validity -->
