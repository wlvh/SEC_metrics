# #28 提供给 #54 的普通路线接口

接收版本：`COMPANY-SEPARATION-v2.1-20261002`，首个平台OpenShift；本期程序边界、下期内网脚本/AI与集群接线。读取#54正文（2026-10-02T15:49:21Z）及#28评论5953695606（15:12:59Z）；本方实际代码固定 `f6a4e4425a6229d0583a4752a1a58b604a21a33e`。#54维护公司交接/导入适配，#28提供接口并验证普通消费者；不接管公司包、不新建账本或通用协调平台。下面是代码调查与有限验证，不是#54公司包验收。

## 三类输入严格分开

| 类别 | 现有实际接口与位置 | 权威/限制 |
| --- | --- | --- |
| SEC原件与来源证明 | `normal_source_requirements.discover_saved_source_requirements`；`normal_source_authority.verify_saved_source_proofs`；`ordinary_source_authority.verify_ordinary_source_proofs` | 元数据/原件/headers、原attempt身份、完整请求日志及manifest、必要前期/分片/前后继CIK。规则来自固定运行时。不是模型回答或Result。 |
| 已保存模型判断及登记 | `capacity_assessment_input.register_assessment_input` / `load_registered_input`；`capacity_run.prepare_case/install_inputs/create_run` | B13/D04请求、响应、plan、intent、terminal、wire、接受及重验收据，是计算侧处理状态。原件仍须单独齐全、source_id和Requirement匹配；输入自洽哈希不自授信任。 |
| 新真实执行许可/后续AI | `continuous_semantic_calls.prepare_requests/execute`、`capacity_update_input.ensure_native_update`、原`CallLedger` | 固定用途/请求映射、逐组机会、余额、最终绑定/接线、停止条件共同约束。已保存AI输入有`new_call_authority=False`；源码能力或#54的0/0/0不授真实调用，也不撤销#28有效旧许可。 |

Fable五条基线探针按外部报告承接；隐藏checkout evidence及逐字节原链对照只覆盖B01。原探针脚本/日志/提交尚待#54接入，未被本方重跑或扩为全部路线正确。旧E01零值/旧D02有文本不获得新口径内容信用。#28缺陷登记与旧Run保留。

## B13 / D04：现成处理记录的消费与新来源

- 普通入口：`normal_run_v3.prepare_case`、`install_normal_inputs`、`create_normal_run`，显式`registered_update_options`和`native_assessment_ledger`。`current_registered_update_options()`选择现行合同；旧默认仍保留原义。
- `capacity_update_input.prepare_registered_update(source_root, company_id, metric_id, options, ledger, allow_incomplete)`会从原factory-owned调用账本读本公司/指标的SUCCEEDED原集合，`source_equivalence`比较完整原文、主体/期间、原件URL/内容哈希集合及实质请求责任，再由当前接受器重验。它不是纯公司来源包API：默认LIVE账本仍绑定批准的`budget_root`，并且重新登记会写计算侧journal。不能让#54把该账本或原执行者的private journal作为计算前提。
- `capacity_assessment_input.register_assessment_input`只由原创建者类型的账本登记，读取`calls/NNNN/{semantic-request,source,plan,success,intent,terminal,wire...}`及原执行证明；`collect_native_assessments`要求完整组集合，缺/失败不是未披露。两阶段还保存独立扫描请求/响应/执行证明。
- journal实际在代码根的`.git/ordinary-source-authority/{capacity-assessments,going-concern-assessments}/{LIVE,RECORDED_TEST_ONLY}/<source+Requirement key>/<input_record_id>.json`。schema2携带原source_snapshot；schema1旧输入保留。
- `capacity_run.install_inputs`通过既有安装器将匹配的处理记录写为`config/ordinary_capacity_assessment.json`或`config/ordinary_going_concern_assessment.json`，与代码、规则、SEC来源一起装进**计算侧Run安装副本**。这是可选的已处理状态交接，不能混进采集输出当必带答案，更不能携带旧Result替代计算。
- `load_registered_input`：代码根有.git时必须读受信journal，再比较数据侧导出；无.git的已安装运行包从自身固定config导出读。注册/导入与消费分别授信，不能让源包自己声明可信输入。无.git运行包已有读取能力，不等于任意独立clone可只靠源包JSON取得信任。
- 新原文/期间没有对应模型判断：`prepare_registered_update(...allow_incomplete=True)`仅返回`CURRENT_NATIVE_SET_INCOMPLETE`、完整准备请求/当前source及Requirement，不创建Result。默认完整消费会明确拒绝。#54应把这是**待AI处理或已有接口限制**保留；下一期AI入口负责执行，不能悄悄用旧回答。结构性B13不适用路径独立，不应索要模型输入。
- B13目前仍无完整公司当前结果，111信用停止、190仅单组，191/192机会已耗尽；停用的语义方案不通过包装/新目录复活。D04十家公司完整真实候选按原安装身份保留，但新来源也不能自动继承旧判断或调用许可。

`probe.py/json`只读取一份合法旧Enphase D04安装记录，核input_id、六组173–178请求关联和new_call_authority=False、无.git包布局；它证明这些字段实存，**没有重跑D04引擎/cold、没有做公司源包移植或只读代码测试**。此前D04全部冷读、2482秒录制生命周期及Ford长演练仅引用原有效证据，不重复执行。

## C04：专用更新及真实获取必须拆开

- 四形式来源准备：`c04_registration_successor`，由#28正常包装器明确选EVENT_FORMS；`normal_run_v3.prepare_case/install_normal_inputs/create_normal_run(...c04_event_forms=EVENT_FORMS)`保留共享默认。
- `c04_update_cycle.run_once/run_company`是零获取计算更新。读取`source_root`的已验证原件/来源证明，写`state_root/configuration.json`、`update.lock`、`attempts/<id>/{intent,terminal,data,runs/C04,rows/C04}`和`current.json`。安装副本保存原规则及来源，旧成功重验；缺同注册人前期事实不擅自给0。
- `ordinary_refresh_cycle.refresh_and_process(...c04_successor=True)`另含发现/捕获/受限续接。它需要`SecAcquisitionSession`、原调用账本与注册权威；不适合作为#54计算端默认入口。`resume_from`会认证前次报告、原末槽、来源账本、状态和确切下一URL，并在相关锁下保留前驱；不是任意失败重试。
- 第193/194真实同财年刷新、已保存相邻年度录制续接等原证据复用，不把它们扩大成#54公司包/新财年在线更新。计算端仅消费来源时可走前述零获取入口；源缺失则列明缺件，交回来源准备侧。

## 数据根、总账与混合checkpoint

`SecAcquisitionSession.data_root = ledger.root / 'source-inputs'`；LIVE `_check`还严格核`policy.budget_root`、240/240/80和原绑定。`register_checkpoint`在账本锁下收集该账本**全部SEC槽**，不只当前company。来源日志`evidence/requests_log.csv`与业务调用`claims.jsonl/calls`不是同一个账本，前者也不能裁行/重编号来模拟新历史。

`ordinary_source_authority._trusted_checkpoint`根据完整来源日志SHA，在代码根`.git/ordinary-source-authority/{recorded,acquired}`找登记；无.git运行时读固定`config/ordinary_source_checkpoint.json`。导入侧数据JSON须与安装权威相等。`_validate_checkpoint`核受信基线精确前缀、全部新增capture、原件/headers和终态。

**当前限制已由代码确认：**`checkpoint_installation(source_root)`没有公司参数，对所有admitted capture累加原/新attempt正文与headers；`normal_run_v3._install_case_inputs`加入全部extra_source_paths。因此“仅本公司新增capture”B类可优先试现有机制，**已有多公司混合增量C类不能仅靠公司目录变成原件只读本公司**。源准备端可以先完整恢复C，再由#54的公司交接实现裁剪/受信准入；计算端不应为了一个公司恢复全体。需要新范围证明或后继准入时由#54主实现，保留原完整checkpoint/日志身份，#28验证当前消费者；不各写一套，不重新获取来绕过，也不拆现行真实总额度。已捕获多个公司不代表相互历史可拼接。

## 稳定路径、暂存和恢复

`ordinary_update_cycle._config`固定source_root字符串、公司/指标、代码/Requirement身份。同一history换physical路径会被拒，这与Fable探针一致；当前`source_identity_root`可让configuration使用稳定identity_source，而实际计算来自`ordinary_processing_source`的不可变snapshot目录，且前后重验同来源历史。

`current_processing_source`已有`.building-<uuid>`暂存、全量验证、目录rename到snapshot_id、已存在快照核验及失败保留；它现在复制受信基线/全部增量，**不是公司包生成器**。调用者在要求新鲜性时需持原获取账本锁。C04专用配置仍直接固定source_root，不提供source_identity_root参数；#54若要换不可变版本，可在稳定运行视图内受控导入/选择，或据实际失败点提出最小适配，不能偷偷用symlink绕过别名检查。

`ordinary_update_cycle._locked`锁state_root/update.lock，只串行化同一更新历史；`CallLedger.locked`锁固定账本目录。二者不自动构成任意导入与计算之间的全局锁。计算期间不得换其来源视图；导入/计算互斥需#54在公司入口使用同一明确边界。代码验证来源日志前后SHA与各原件绑定，不等于承诺所有共享存储原子行为。旧attempts/data快照及Run保留，最新失败不能回退成假新成功。

## 读写位置与OpenShift边界

| 阶段 | 现有需要写的位置 | 可只读的位置 / 尚缺适配 |
| --- | --- | --- |
| 来源获取/捕获 | ledger root与父级初始化锚点、source-inputs原始捕获/日志；创建者注册写代码根.git的acquired journal | 原码/规则读。LIVE总账固定位置属于现有批准，不按公司拆份；平台路径迁移不由#54自行批准。 |
| 接收登记 | 当前普通checkpoint注册和AI输入登记仍在代码根.git固定trust子目录 | 没有受支持的外部trust_root参数；数据包不能自行指定权威路径。#54据增量失败提出受控持久导入位置/最小后继，#28协助兼容验证；不是直接禁用检查。 |
| 只消费已安装输入 | 无.git运行时可从安装的config checkpoint/assessment读；有.git分支读受信journal，AI `_journal`会确保目录存在 | 主码/规则/已登记输入可读；是否完全只读需实际调用验证，未宣称OpenShift通过。 |
| 安装/计算/更新 | 外部data_root、run_dir；state_root下安装的代码/规则副本、intent/terminal、rows、指针及锁 | 主代码根并不作为业务输出根；暂存/输出/持久状态需要写权限。使用非root、动态UID的目标约束，当前未部署或实测集群。 |

路径用明确参数/安装配对，个人HOME只是本方现有LIVE许可定位，**不是新的OpenShift接口默认**。本期没有root/unshare依赖、镜像/集群部署或Databricks适配。建议下一步先由#54留单公司B类增量与真实C类失败证据，再约定最小信任登记/选择接口；#28不另造公司包或重做原五条基线。AGENTS文档入口在V13/V14执行/规则列表无直接绑定，本文只改职责/链接，不改变运行接口或权威。

验证边界：实际JSON/身份小核；实际源码静态追踪；读取他人Fable报告与本方旧长链日志。三个类别分别登记，未复跑全部基线、没有新AI/SEC请求、新正确公司结果或#54验收信用。
