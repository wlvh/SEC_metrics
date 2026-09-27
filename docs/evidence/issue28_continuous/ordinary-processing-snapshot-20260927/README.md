# 普通更新：旧来源根与当前执行规则分开接线

已确认的故障是固定 #28 `source-inputs` 根中的旧普通处理规则副本：直接调用当前`normal_run_v3.prepare_case()`准备Salesforce B01，先报`ORDINARY_INTEGRATED_INSTALLED_POLICY_CHANGED`，尚未到业务来源判断；之前的混合C04刷新因此把B01等其它普通指标统一标成阻断。旧根保存真实SEC请求历史、来源证明和既有安装身份，不能为修正常态更新直接覆盖它的旧副本。

本增量沿用原来源权威，不建第二账本：`ordinary_processing_source.py`先核原来源账本的可信checkpoint，再以当前未冻结V13/V14规则建立私有处理副本；1256份冻结基线逐字节验真，额外105份已登记请求原件/头文件按原路径复制，原请求日志/manifest与checkpoint身份保持。macOS APFS用`clonefile`创建独立 inode 的写时复制文件，无法使用时退回普通独立复制，**绝不硬链接原件**。副本按原账本摘要和当前需求闭包命名，重用时重新验来源账本、checkpoint、普通规则与财年政策；部分中断目录没有完成标记，不能复用。原账本、binding、来源文件及生产指针不改。

`ordinary_update_cycle`只在显式提供`source_identity_root`时，用原固定来源路径保持跨输入版本的更新配置身份，同时在处理前后证明实际私有副本与该原账本精确对应。默认调用参数、返回结构和历史原生包路径不改。`ordinary_refresh_cycle`仅对原先因旧处理副本而阻断的显式混合C04路线，在来源获取之后构建此副本：其它普通指标从当前规则副本准备并生成Run，C04仍沿原来源根的既有显式后继，以保留其更新历史。来源发现仍覆盖完整依赖，缺件时整体`UPDATES_INCOMPLETE`；不因B01/C04局部成功伪称全39已更新。当前混合路线对非C04缺件的真实SEC获取仍保持原受限边界，后续须单独接通并验收。

本机原账本只读/私有验证：`root-probe-final.log`记录原来源旧规则字节不动，当前副本从同一checkpoint使Salesforce B01正向准备为41,525,000,000、C04正向准备为0；`b01-history.log`记录B01私有Run第一次`CANDIDATE_READY`、第二次`NO_SOURCE_CONTENT_CHANGE`且成功尝试不变。`mixed-refresh.log`及`mixed-refresh-repeat.log`记录混合入口B01/C04各自第一次`CANDIDATE_READY`、重复触发均不增候选，整体因其它来源待办继续`UPDATES_INCOMPLETE`；原账本均143/143/52，调用0/0/0。这四份运行发生于写时复制优化前的当前规则闭包，不能冒称已经在最终代码树重做。其外部临时根也不是Git归档。

最终当前规则闭包的写时复制证据见`cow-test.log`：私有副本创建前后文件系统可用量差2.8MiB（单次macOS观察，不是跨平台承诺），当前B01/C04仍正向准备；改坏私有B06规则后，副本验证拒绝，而ROOT规则字节不变。`material-test.log`在**录制基线**上完成1项完整来源测试（49.451秒）：旧政策副本确实阻断旧默认B01，当前副本使B01通过，冻结基线缺Salesforce额外C04来源时仍拒绝，混合刷新给B01独立`CANDIDATE_READY`而整体保持不完整。`source-version-rehearsal.log`另以一次**相同真实保存字节的录制元数据响应**使来源账本版本从0变1，得到两个不同处理副本ID；B01再次返回`NO_SOURCE_CONTENT_CHANGE`、成功尝试不变。录制SEC槽不是真实GET或新业务结果，原#28总账仍143/143/52。

短回归`refresh-boundary-tests.log`为11项PASS；`c04-bootstrap-fast-fix.log`两项PASS，明确原测试的“发现错误必须是最后一条”不是新处理副本出现后的业务不变量。快速套件`fast-suite.log`为132/132通过（80.621秒）；`sec-default-regression.log`一项完整录制SEC获取/失败隔离默认入口100.237秒通过，原默认`initialize_source_inputs()`仍使用原独立复制行为。初次`fast-suite-first.log`的130项通过、2项旧错误顺序断言失败保留，修正后才记录完整绿。

首次来源探针因把可缺的C04规则副本当作必须存在而在复制前失败；初次写时复制反例选了属于展示文件、不会进入当前来源规则集的路径；前几次材料测试分别假设JSON空白会触发语义政策错误、冻结基线已含Salesforce额外C04来源、可在录制账本初始化前写来源，以及把所有本地Git身份读取也当成外部网络子进程。原日志保留，最终测试只允许本地只读Git命令、阻断网络/HTTP与其它子进程。

这不是正式采纳、生产切换、全390成功或新财年在线更新完成。旧候选/Run按原安装身份继续读取，私有副本只是本轮显式路线的当前处理输入；新代码和绑定须限定独审及新head CI另验。无provider/paid/SEC新调用，无#47分支、快照、账本或运行根操作。

## 40bff457限定审阅发现与受限回修

`independent-review/conclusion.md`对`40bff457`给出`NEEDS_FIX`：混合刷新已能让B01形成候选，但续跑入口仍要求旧报告里“B01阻断”的形状，因而新报告不能作为下一次受限SEC捕获的前驱。该报告的来源副本、账本身份及旧默认兼容认可边界仍有效，失败结论保持原义。

受限回修只改变`ordinary_refresh_cycle._resume_one_c04_source()`：带处理副本ID的新报告必须核对原来源账本、私有副本、每个已执行普通指标的本地配置/指针/终态、C04原终态和待办URL；旧报告没有副本ID时仍按旧阻断形状读取，不能把旧报告改签为新Run。相应材料用例先篡改B01尝试编号，要求在第二次SEC捕获前拒绝，再用原报告完成两次录制捕获。初跑走完录制链却在最后因测试仍期待旧整体`UPDATES_INCOMPLETE`而失败；该实际状态为来源补齐后的`UPDATES_READY`，失败原文在`resume-material-first.log`。改正预期后同一录制材料测试完整通过，`resume-material.log`记录1项PASS/195.651秒；两次C04来源捕获及B01/C04更新状态都由实际测试断言检查。`resume-short.log`记录原旧刷新边界11项PASS。第一次快测误用缺tokenizers的系统Python，`resume-fast-system-python-failed.log`保留环境失败；在已有`/private/tmp/issue28_py314_venv`的tokenizers0.22.2中重跑`resume-fast.log`为132/132 PASS、118.048秒。当前SEC实账本没有变化；录制槽不计真实信用。该测试已在`tools/run_fast_tests_v2.py`的来源材料选择器末尾追加，未改runner函数体；新补丁限定独审和新head CI仍待完成。

## 134dcf4f限定审阅的两个恢复边界

`independent-review-followup/conclusion.md`仍给`NEEDS_FIX`，且确认前述正常路径P2已关：一是可把B01真实成功行伪装成`UPDATE_BLOCKED`，使新报告跳过B01尝试核对；二是处理副本在已成功SEC捕获后创建失败时，报告无副本ID，续跑误按旧`SOURCE_SCOPE`报告拒绝。这两个都是同一恢复入口的明确反例，不扩大成通用审批平台。

当时的受限回修要求新报告的`UPDATE_BLOCKED`行没有对应普通更新配置或当前指针；此要求在下节核对实际配置写入顺序后进一步收窄；有真实尝试的行仍需逐份匹配终态。混合报告明确标记副本`READY`或`FAILED`；失败态保留SEC成功收据和C04状态，下一次捕获前先重建并验当前副本，再检查原待办URL和账本序列。无标记旧报告保留旧形状，但不能伪装成已经执行普通指标的报告。`resume-followup-material.log`用两套独立临时来源根完成2项录制材料测试、合计377.258秒PASS：正常续跑前拒绝尝试编号和状态降格篡改，副本创建失败后不撤销已成功捕获，修复副本后再完成另一URL和B01/C04结果。`resume-followup-short.log`11项PASS，固定tokenizers0.22.2下`resume-followup-fast.log`132/132 PASS（118.568秒）；V14绑定与三份接线收据见`binding-resume-followup-after.json`。第二条材料选择器仅追加于`tools/run_fast_tests_v2.py`末尾，runner函数体不变。新差异限定独审与当前head CI另验；原`134dcf4f`结论不改，录制槽不计真实调用或新公司结果。

## 8ce178a5限定审阅后的配置/尝试边界

`independent-review-recovery/conclusion.md`确认上述两项指定反例已处理，但结论仍为`NEEDS_FIX`：普通更新先写`configuration.json`，随后若状态读取失败会返回真实`UPDATE_BLOCKED`而没有创建尝试；先前把配置存在一律当作尝试，误拦C04独立来源续跑。短注入日志`independent-review-recovery/blocked-history-short.log`记录了这个实际写入顺序，前次独审结论保留。

本轮仅让“配置存在但与当前来源/规则身份一致、当前指针和尝试目录都不存在”成为可续跑的阻断状态；已有真实尝试或当前指针仍不可凭报告自称阻断来跳过核对。已有历史指针但本轮未尝试的情形没有独立的前态证明，本路径保守拒绝该报告的`resume_from`，不把它宣称为全部恢复能力。`config-only-short.log`12项PASS，验证配置先写、状态读取失败时没有尝试；`config-only-material.log`两套录制来源材料2项PASS、合计377.591秒，把有效既存配置放入副本失败报告的同一状态根，恢复后仍完成另一来源及B01/C04结果，并保留成功行状态降格拒绝。当前V13父级闭包字节未变，V14与三份收据见`binding-config-only-after.json`。前次`resume-followup-fast.log`132/132只覆盖旧子补丁；本次受影响短测与材料另验，新head CI仍待核对。原账本无新增真实调用或生产采纳；本补丁限定独审另记。
