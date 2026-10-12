# 新公共保存 D04 只读接缝限定独审

结论：本次明确差异范围内未发现需要修复后才能继续接入的代码问题。指定 59 项小测试通过，0 failure、0 error、0 skip；另执行 15 项小型控制检查并全部通过。该结论仅支持此公共输入适配器和共享接口差异的离线工程验收，不证明完整申报媒体已审阅、D04 业务结论成立、正式公司 CLI 已接入，也不授予调用、合并或生产采纳权限。

## 提交、时间与范围

- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-saved-d04-replay/SEC_metrics`。
- 基线：`f51d8c3d27f3169b9cdb3a246295830882240c1f`；受审提交：`4e773d44b1f5eec8d86cf92c225860175d5d87f8`。独审开始时 HEAD 为受审提交，工作树无已有未提交改动。
- UTC 开始：2026-10-10 11:38:01；差异、测试和最后一轮控制检查完成：2026-10-10 11:41:27。文档写入及只读收尾随后完成，总时长约 4 分钟，低于 90 分钟硬限。
- 完整检查新增 `scripts/vnext/saved_d04_replay.py`；限定检查 `current_d04_result.py` 的单行显式 media=false 拒绝、`ordinary_current_update.py` 的默认空 `processing_inputs`、`company_current_records.py` 的逐指标可选传递、`ordinary_projection.py` 的指定媒体未验 WITHHELD 行、两个变更测试文件与 `.github/workflows/vnext-fast.yml` 新步骤。
- 必要局部追踪仅查看现有 `native_unit_index.validate_request_partition` 和 `invocation_control._validate_acceptance_receipt` 的实现与指定既有小测试。没有扩展为历史包实现审计、来源选择器重写或公司长链重跑。
- 读取同证据目录的 README、tested-tree、first-company、reader-summary、independent-read JSON。五个受审代码文件的 SHA256 均与 `tested-tree.json` 一致；这些历史执行材料仍按其原记载的 base 加当时未提交改动解释。本次小测试直接在受审提交的文件字节上执行。

## 核对结果

1. 原调用身份保持：适配器只读 tar 成员，校验原 source/request、binding、intent、terminal、plan、实际请求体、response、success、acceptance 与 execution 的身份及相互引用；保留原 counts、usage、requirement 与执行模式。它没有创建账本、构造新 intent、申领机会或调用 provider/SEC 的路径。原 usage 中的未知值仍为 null。
2. 原请求必须完整：空调用组、重复 ordinal/成员、缺少 intent、失败终态、变更回答/请求体均被拒绝。现有来源重建函数另核对请求数量、顺序及各请求内容；缺组不会因 `missing_request_ids=[]` 而被当作空发现。小型控制检查额外确认真实重建函数拒绝缺少必需请求的列表。
3. 当前接受检查保留：回答沿现有 D04 `build_acceptance` 重验，并比对原 acceptance 的业务内容；只有验证器自身版本摘要允许更新。来源坐标同时绑定公司、CIK、accession、财年及起止日期；新增控制检查覆盖公司、CIK、accession 和起止日期错配。执行回执错绑 plan、terminal 错绑 execution，以及 plan 错绑 semantic request 均被拒绝。
4. 媒体限制准确：该读取器始终写 `filing_media_coverage_verified=False`，因此全组文字回答通过也不能通过完整公司结论门。准备接口只形成原因 `D04_SAVED_FILING_MEDIA_COVERAGE_NOT_VERIFIED` 的 WITHHELD/null 结果；没有推断图片仅为装饰，也没有将文字组无发现升级为全申报无疑虑。返回的 absence proposal 字段仍只是文字组提案，其显式媒体限制使其不能成为完整结果。
5. 投影只增加指定媒体未验分支：新分支同时要求 D04、指定 reason、WITHHELD、value=null、source_replay_only=true 和 media=false，输出明确的限制说明及原文档证据。数字分支、已有 text_payload 分支及旧无疑虑/结构不适用条件未放宽。本次对新增投影分支的核验为代码检查及提供的保存行材料检查，没有重新跑真实媒体结果链。
6. 外部答案包可以成为比较输入：显式声明后，解析得到的绝对路径和文件 SHA 进入 configuration；变化触发一次重验，稳定的 WITHHELD 随后复用，文件缺失先失败且不复活旧成功。公司 API 对指定指标保留原输入 tuple，未指定指标接收空 tuple。默认空输入不增加 `saved_processing_inputs` 键，既有比较记录形状保持。
7. 依赖声明仍由调用者负责：未来消费者必须同时声明实际外部答案包及既有处理代码依赖。此 optional passthrough 本身没有检查函数闭包内是否隐藏其他输入；这是当前明确接口边界，不是已交付完整自动依赖发现能力。文档已明确该责任，本次没有提出新平台要求。

## 本次验证

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. \
python3 tests/required_unittests.py \
  tests.vnext.test_saved_d04_replay \
  tests.vnext.test_current_d04_company \
  tests.vnext.test_ordinary_current_update.SelectedPeriodUpdateTest \
  tests.vnext.test_company_current_records
```

退出 0；59 tests，9.149 秒；无跳过。详见 `required-small-tests.log`。

另用既有小型 synthetic fixture 执行 15 项控制检查，覆盖输入/package 不变及禁止 socket、五种坐标变化、空组/缺请求、三种跨回执错配、媒体门、旧省略 flag 行为、逐指标传递与默认记录形状。仅构造临时小 fixture，不读取或重包实际历史 tar；不作模型或业务信用。详见 `scoped-control-probes.log`。控制脚本没有写入源码或测试目录。

## 未覆盖及资源账

未读取实际 old package、原公司 source、#47 目录、私有 ledger 或大原件；未重跑实际 Mar23 四组原回答、十四张图片、完整公司创建/更新/CLI 长链；未验证新公司/年份的历史选择能力、模型判断准确度、媒体完整性、远程 GitHub CI 或 Python 3.14 运行。提供的实际执行 JSON/日志是被检查的材料，不被写作本独审重新执行的业务证据。

没有 network、业务请求、账户/额度动作、源码/测试变更、commit、push 或子代理。只新增本目录的 `conclusion.md` 和两份核验日志。收尾检查确认全部受审代码/测试/workflow 相对受审提交无差异，工作树仅出现该独审目录。

实际工具节点合计 29（11 次 `functions.exec`，其中 18 次 nested 工具；包括最后写入和只读收尾，不遗漏 nested）。普通消息合计 3（2 次 commentary、1 次最终报告），没有问题消息。没有达到或重置 80 节点、90 分钟或 3 消息上限。
