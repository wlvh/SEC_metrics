# 公司级来源交接与独立计算

**状态：Draft 开发接口；实际覆盖见证据索引。** 对应 `COMPANY-SEPARATION-v2.1-20261002`。当前接口不授生产、active 切换或部署权限。

任务范围、连续执行委托、接口责任和唯一当前队列见 [Issue #54](https://github.com/wlvh/SEC_metrics/issues/54)。本页用于承接最终的稳定使用说明，不复制 Issue 进度或建立另一份待办。

## 目标边界

获取/来源准备输出明确的交接来源；计算只读取这些来源和自己安装的程序、规则及受控信任状态。计算不能回读原采集工作区、私有 journal 或 SEC，也不要求其他公司先完成。公司是运行和状态隔离单位，指标及结果继续复用已有 Run、Result、证据和读取接口。

共享规则、公司注册信息和必要的全局账本元数据可以保留；实际公司原件及其前期、历史分片、主体角色依赖必须明确。来源自洽哈希不能代替可信获取凭据，导入不能把 recorded 标为 LIVE。一次计算固定一个来源版本，失败或导入中断不破坏上一有效输入及运行。

## 与已有能力的关系

[Issue #28](https://github.com/wlvh/SEC_metrics/issues/28) 保留普通指标、正常更新、统一生产与旧路径退出责任；[Issue #47](https://github.com/wlvh/SEC_metrics/issues/47) 保留五年历史期间、依赖和业务验收责任。#54 负责两阶段边界、公司运行和集成验证，不复制业务内核，不重建正式发布、选版或认证平台。

首个内网平台为 OpenShift。镜像、任务、卷、网络、脚本及内网 AI 接线留给下一 Issue；本期没有集群部署或 OpenShift 验收。新增真实 SEC/provider/paid 调用为 0/0/0。

## 使用与证据

`tools/vnext_company.py` 提供 `export`、`install-runtime`、`install`、`compute`、`export-results`。所有路径必须显式传入、绝对且无 symlink，输出不得覆盖程序或 active 工作区。下面的 `/srv/sec-metrics` 是部署方选择的示例，不要求该目录、个人 HOME、root 或特权功能。

来源准备端先用原机制校验完整来源历史。A 类读取已提交基线；B 类使用原 recorded 获取会话，在同一个 `ledger.root/source-inputs` 追加目标公司；C 类可以在准备端恢复合法保存的混合获取归档。不能删账本行、改行号、拼接不同历史或另设真实额度。然后执行：

```bash
python3 tools/vnext_company.py export \
  --source-root /srv/sec-metrics/prepared-history/source-inputs \
  --output-root /srv/sec-metrics/transfer/jpmorgan-v1 \
  --trust-root /srv/sec-metrics/source-trust \
  --company jpmorgan_chase --metric A08
```

公司包保留整个请求账本、manifest、注册信息和原检查点元数据；按经验证的依赖声明及目标公司捕获引用收集原件和 headers，包括 legacy 保存位置、旧尝试、前期、窗口外、前身 CIK、历史分片和事件头文件。全局元数据可以出现其他公司，其他公司原件不会随包交付。来源包没有 Result 或 AI 答案前置。

`source-trust` 是准备端安装的独立信任登记；计算端只读。包自己携带的 JSON/哈希不能注册自己，也不能把 recorded 提升为 LIVE。允许保存原获取信用，但不因此获得新获取或生产权限。

计算运行树由原固定程序安装。A 类 baseline 默认不改核心文件；增量包使用 `--kind ordinary` 的独立后继运行树。原 `issue_28_v13` 文件、旧 Run 和闭合额度保持原字节；后继只登记公司来源准入与新运行身份，业务规则继承原版本。代码变更发生在新安装树，不写回 #28 checkout。历史另用 `--kind historical`，从 #47 固定树安装，应用其提供的注册补丁，继承 `issue_47_v1` 并形成独立 `issue_54_v3`；不能把该补丁打入普通树。

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

普通 `compute` 复用每指标 update controller；C04 调用专用四 form 更新入口。增量 B13 的零 AI 结构性 N/A 使用单独 `--kind native` 固定树（继承原 V14、后继 issue_54_v2）；普通树明确返回 NATIVE_RUNTIME_REQUIRED。本 CLI 尚未连接适用 B13/D04 的独立判断登记库，返回 `AI_PROCESSING_INPUT_REQUIRED`，保留来源和公司身份，不能算指标完成。已保存判断使用其原固定运行树重放，与 SEC 来源分开交接；本期不调用业务模型。D04 的已登记输入读取已实测，不能扩大成新来源包的 D04 Result。

历史准备从固定 #47 树调用 `export --history-years 5`，使用其 `declared_frame`；计算选择历史固定树并加 `--report-end YYYY-MM-DD` 或 `--fiscal-year YYYY`。这些消费者的实际通过范围须看证据索引，不能由接口存在推出五年全部业务验收。

`export-results` 在公司锁内导出结果引用、最新导入状态、现有候选的原生 Run/data/rows，以及文件哈希索引。旧结果与当前来源是否一致分别登记。普通候选保持 OPEN，回读用既有原生 OPEN replay；FROZEN Run 才使用 `load_frozen_run`。生产发布状态继续由原流程决定。

实际实验、失败位置、分项体积和耗时见 [证据索引](evidence/issue54_company/README.md)。十家公司来源导出不等于全部 36 项或 30–60 分钟验收。Fable 外部报告保留原信用，尚未取得的原脚本/日志不记成本方复跑。

<!-- capability-anchor: CAPABILITY.company_import_transaction -->

## 保存处理输入的实际接口与限制

#28 原接口为 `capacity_assessment_input.load_registered_input(data_root, source, requirement, mode, input_record_id)`；`source` 必须由同版原工厂重建并保持原 source_id/请求集合，登记记录不能改签成新输入。合法旧 D04 录制材料已在无 `.git`、只读独立目录重放，使用其原 V14 规则及固定 tokenizer 0.22.2，6 个请求完整核对；没有创建 Result 或调用模型。

原登记创建端的 `_journal` 位于该固定运行树 `.git/ordinary-source-authority/{capacity-assessments,going-concern-assessments}/<mode>` 目录；无 `.git` 读取端可以消费保存的 config 登记副本。本 CLI 不向只读程序登记新判断，也不把旧登记塞进来源包。将判断登记创建/读取连接到公司的独立可写处理状态仍需 #28 消费者核对，并在下一期内网 AI 接线时完成；当前限制明确呈现在结果状态中。

导出结果带相对 native 路径及逐文件索引。读取旧 Run 应选择创建它的固定运行树与独立 trust；程序、Requirement 或 source admission 的绑定副本必须保留。历史导出复用 #47 已有单进程、按状态失效的 checkpoint replay scope，实际原件和每个原生结果仍验证，不建立新的通用缓存。
