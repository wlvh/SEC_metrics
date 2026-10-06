# 指定 main 阶段接收边界独立审阅

本次限定审阅完成。指定补丁在已审范围内没有发现新的阻断代码问题，可继续进行固定版本的接收核对和隔离消费者接入；**不能据此标记 main 合并就绪、生产采纳或39指标业务验收通过**。已有通用发布门禁与旧测试环境/身份不兼容仍然阻止相应发布及无条件 main 验收。发现一项非阻断的证据清单过时问题，见下文。

## 审阅身份与执行约束

- 补丁：`469d3ea42e2346e03976e8d4a50db1d2f7de9289`；main：`af1984ad5f1a3598ded3626fe999d3abeffd29b9`。
- 固定来源里程碑：`0bc24734736bb1e6cb34fbcf7ab9fece6951764e`；PR55消费者：`83db2c0284d76cfe6a1fafc8703743add05738f8`。
- 审阅工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics`；开始读取时间：2026-10-04T10:19:21.629149Z。
- 工具量按外层 `functions.exec` 和内部工具各计一次，含最终写入及回读为 **39次**：19次 `functions.exec`、20次内部工具。普通消息 **2条**：开始说明1条，最终报告1条；问题0条。至报告写入已用 **672秒**，最终回读在随后数秒完成。没有触及80次工具/90分钟上限。
- 只运行获准的4项 unittest；其他应用测试、安装、材料重算和D04接收执行均只读现有日志。静态核对使用Git对象、文件字节与源代码，不调用HTTP或模型、不spawn、不修改源码/快照、不commit/push。
- 未在线刷新Issue正文：本次限定审阅禁止HTTP请求，结论不重新认证实时权限。未使用记忆中的历史交付事实形成结论。

## 固定来源、完整父快照与执行绑定

独立Git对象检查确认：相对main的303个 `scripts/tools/catalog/config/requirements` 固定里程碑差异，候选全部与0bc对应blob一致；0bc的84个Requirement文件全部一致。V13的389个、V14的493个 `execution_authority.files` 在指定候选工作树全部满足SHA256和大小绑定。逐项读取父快照绑定又核对72个被引用文件，未见缺失或字节差异；冻结 `frozen-parent-v10-index.json` 的89个成员全部匹配。这里的“完整”指声明的版本与绑定成员完整，未扩大为所有业务正确性。

来源定位：`foundation-inventory.json` 的752行对象清单；`requirements/issue_28_v13/baseline_manifest.json` 与 `requirements/issue_28_v14/baseline_manifest.json`；`scripts/vnext/requirement_profile_v14.py:22`、`:34`、`:40`、`:47`；`requirement_profile_v15.py:18`、`:30`、`:36`、`:40`；`requirement_profile_v1.py:1998` 的执行文件与语义版本检查未被删除。已有 `first-runtime-load.log:1`、`:2` 记录closure分别为99f07acd与8f993f08；这两次实际加载是创建者证据，本审阅未将其称为自己新运行。

PR55的运行时增量确为18路径，候选没有把这些消费者新实现混入基础代码。其稀疏安装材料补齐的17个祖先文件在main、0bc和候选三者blob全部相同。现有安装日志证明固定18路径叠加后实际安装成功，生成issue_54_v4私有authority；本审阅只读该结果，不复跑安装、不把它当合并信用。定位：`pr55-overlay-scope.json:4`、`installer-ancestor-completion.json`、`pr55-runtime-install-complete.log:3`、`:22`。

**非阻断问题 C1：materialized-scope仍误列一个“保留main”文件。** `materialized-scope.json:419` 将 `tests/vnext/projection_fixture_support.py` 列在 `kept_main_paths`；实际候选已经采用0bc的blob 2c1bac06，与main的7816d8f4不同。README:17已经说明换入匹配的历史helper，实际代码恢复冻结Issue15配置/收据，也没有篡改快照。因此这是可复现的清单不一致，建议交接前纠正该条；它不否定上面303个运行时文件及完整authority的核对结果。本审阅没有修改该原始清单。

## 现有核心与冻结身份兼容边界

审阅读取了相对main的16个已有运行时/工具文件差异，加上历史测试helper；完整读取本次重点 `records/run_store/normal_run_v3/publication/invocation_control` 的差异和关键上下游。旧数字记录没有被自动补 `TEXT_V1` 字段：数字Result/Trace/Observation的身份算法在字段缺席时仍走原分支；新文本字段加入自己的身份并与Spec种类、原文、Review及完整记录图核对。定位：`records.py:638`、`:962`、`:980`、`:1002`；`run_store.py:2138`、`:2341`、`:2557`、`:2901`、`:3071`。这支持静态身份兼容，不等于所有历史Run已用新代码重放通过。

普通Run按绑定的Requirement及原件重建输入/Spec/期间和完整计算图，新的事件窗口及主体不可比终态被限制在重建后的确切记录上；不能用任意Spec或空输入冒充普通来源成功。定位：`normal_run_v3.py:452`、`:508`、`:520`；`run_store.py:2138`、`:2162`、`:2947`。独立运行唯一获准命令：

```sh
PYTHONPATH=scripts:tools PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_normal_run_authority
```

结果exit0，4项通过，0.004秒。**这4项具体测试针对issue_28_v12的authority删除、空/多Spec和未批准Spec路由负例**，见 `tests/vnext/test_normal_run_authority.py:16`、`:27`、`:35`、`:46`；不能把它写成V13/V14所有正向业务路线的完整独审。

新增调用分支仅显式issue_28_v14启用；缺失usage没有伪造数字，缺input/output usage的200响应变成USAGE_UNKNOWN，SUCCEEDED仍拒绝必需usage为null。旧Requirement的处理未被全局放宽。定位：`invocation_control.py:233`、`:281`、`:718`、`:576`、`:2778`。本次只审接入和身份边界，未重新审调用账本、预算或B13业务P2。

候选的main active pointer、matrix、对应publication manifest和原release plan索引blob全部与main相同。新增普通发布钩子要拥有进程内创建的私有能力，并限制在源码checkout之外的新工作区、确切候选和前任；旧默认通用scanner仍保留。定位：`publication.py:5688`、`:5704`、`:5716`；`ordinary_isolated_publication.py:56`、`:308`、`:332`、`:344`、`:354`。已有 `active-publication-read.log:1` 记录读取现存24bf8f16和c0aa1c7d矩阵且pointer未变；该成功读取由创建者完成，本审阅独立确认保留的Git字节。

## 已知失败是否阻止后续接收

现有146回归日志不能汇总成PASS。`regression.log:1604`、`:1606` 是146 tests、70 errors、2 failures。独立只读分类发现67个PublicationError出自 `Scalability audit execution failed`，另有缺publication锁、冻结provider配置不匹配、当时authority测试模块未带入等问题；两项assertion涉及历史publication身份。定位：`regression.log:1540`、`:1551`、`:1572`、`:1583`、`:1595`。

通用发布调用确实仍在 `publication.py:3056` 执行真实scanner，在 `:3088` 和 `:3472` 对非零/非空结果拒绝。`scalability-check.log:1`–`:10` 保存9个拒绝项。普通隔离发布中的特定规则不能被当作通用发布门禁已通过。四项新独立负例只补上authority测试本身的现时证据；其余历史失败未在本次重跑，不能宣告已消除。

这些失败**阻止无条件main合并/通用发布可用性验收**，但没有显示固定基础对象、绑定闭包或只读材料传输被破坏；因此不阻止继续隔离接收、消费者差异核对、对已知不兼容实施有界修复。后续若要宣告main阶段验收完成，需要对应发布边界的明确修复/选择及受影响验证，不能通过关闭scanner、改旧authority或恢复旧pointer获得PASS。此次审阅没有授予任何合并/生产动作。

B01既存正向更新日志有真实CANDIDATE_READY、重复进入复用Run和公共CSV重放，但总摘要保留FAIL，因为首个负例harness漏接RunStoreError。独立只读核对其脚本/摘要，接受它证明已完成的正向步骤，并把后续单独负例/恢复日志作为分开证据；不把FAIL改写成整体PASS。定位：`normal-foundation-smoke-summary.json`；`normal-foundation-smoke.py:59`、`:68`、`:74`；`normal-foundation-negatives.log:2`、`normal-foundation-recovery.log:2`。年度/C04十项通过也是创建者证据，不是本审阅的新执行。

## D04传输与信任边界

独立静态核对652个原程序成员、8个SEC/获取证明成员：每一个Git对象的blob、SHA256、大小均与locator一致，无重复目标路径。程序成员映射与processing metadata的runtime_files **完全相同**。locators引用的四个完整提交均可从0bc里程碑历史到达，包括40ca4267的原V14 baseline；该旧manifest与LIVE packet的0f724fa7原closure保持关系，没有替换成候选当前8f993f08。定位：`d04-runtime-object-locators.json`、`d04-source-object-locators.json`，以及 `processing/processing.json`。

承载的两个processing内容文件SHA/大小满足metadata，metadata与单独trust文件字节相同；与原本地export-processing输出逐文件比较也相同。原assessment文件还与原installed data字节一致，含四个原生请求ordinal115–118的semantic_request、wire、assistant_output、intent、plan、terminal和acceptance_receipt。该核对证明本次传输没有换掉原处理包，不重新裁决那四次模型判断的业务准确性。

`materialize-d04-handoff.py:18`–`:38` 拒绝绝对/上跳路径并验证每项字节；`:48`–`:51` 要求新绝对输出根且无符号链接父路径；`:53`–`:71` 分开重建原程序、旧SEC/proof输入、processing及trust。它创建的Git提交是接收端原程序成员清单，没有改仓库或旧提交；`:73`–`:78` 复制并比较原export的trust，未根据incoming metadata生成新的trust。脚本本身只是运输，还要求随后固定83认证，见 `:82`。

固定83的 `company_processing.py:74`–`:102` 从独立环境指定trust root读取已信任metadata，要求根不重叠、成员集合和各项SHA/大小相同、正确公司/D04、无新调用/生产权限，并排除程序中的SEC和assessment状态。`company_processing_read.py:137`–`:140` 在实际消费时还验证原Requirement执行字节并禁网。已有 `d04-portable-authenticate.log:1`–`:3` 记录创建者在Mac接收端认证PASS、改包/错公司拒绝；本审阅只做静态核对，不冒充新认证或Linux执行。

SEC/proof成员仅为三对原件/header与完整原requests_log/manifest，无assessment、Run或Result。旧source-only exporter仍失败于缺失声明的 `evidence/submissions/CIK0001048286.json` 镜像；材料保留该失败而不是补一份新答案或改原账本。定位：`d04-source-object-locators.json:2`；`d04-sec-stderr.log:14`；README:42。原程序及processing包可继续传输和认证；不能写成已成功导出独立来源包或Linux已完成消费。

## 覆盖与未覆盖

已覆盖：固定main/0bc/83身份及实际候选差异、303个运行时成员来源、84个Requirement文件、V13/V14执行文件SHA/大小、父快照及冻结v10成员、现有核心接入/字段身份/私有发布和调用null边界、main active/result镜像字节保留、18路径消费者与17祖先补齐的性质、D04四根传输结构及652+8成员、原processing/trust/assessment字节，获准4个负例的独立执行，以及已有失败日志对验收的实际限制。

未覆盖：所有新模块业务规则、39指标全量验收、B13已关闭P2、Issue47、146回归/长材料重新运行、Marriott重新取数/重新计算/新模型判断、Linux真实消费、D04 source-only包装兼容修复、生产发布/合并/active切换、真实调用身份/总账本及实时Issue权限刷新。没有把未执行或其他执行者的测试写成自己的独审。
