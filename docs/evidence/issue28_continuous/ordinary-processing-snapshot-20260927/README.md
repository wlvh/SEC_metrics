# 普通更新：旧来源根与当前执行规则分开接线

已确认的故障是固定 #28 `source-inputs` 根中的旧普通处理规则副本：直接调用当前`normal_run_v3.prepare_case()`准备Salesforce B01，先报`ORDINARY_INTEGRATED_INSTALLED_POLICY_CHANGED`，尚未到业务来源判断；之前的混合C04刷新因此把B01等其它普通指标统一标成阻断。旧根保存真实SEC请求历史、来源证明和既有安装身份，不能为修正常态更新直接覆盖它的旧副本。

本增量沿用原来源权威，不建第二账本：`ordinary_processing_source.py`先核原来源账本的可信checkpoint，再以当前未冻结V13/V14规则建立私有处理副本；1256份冻结基线逐字节验真，额外105份已登记请求原件/头文件按原路径复制，原请求日志/manifest与checkpoint身份保持。macOS APFS用`clonefile`创建独立 inode 的写时复制文件，无法使用时退回普通独立复制，**绝不硬链接原件**。副本按原账本摘要和当前需求闭包命名，重用时重新验来源账本、checkpoint、普通规则与财年政策；部分中断目录没有完成标记，不能复用。原账本、binding、来源文件及生产指针不改。

`ordinary_update_cycle`只在显式提供`source_identity_root`时，用原固定来源路径保持跨输入版本的更新配置身份，同时在处理前后证明实际私有副本与该原账本精确对应。默认调用参数、返回结构和历史原生包路径不改。`ordinary_refresh_cycle`仅对原先因旧处理副本而阻断的显式混合C04路线，在来源获取之后构建此副本：其它普通指标从当前规则副本准备并生成Run，C04仍沿原来源根的既有显式后继，以保留其更新历史。来源发现仍覆盖完整依赖，缺件时整体`UPDATES_INCOMPLETE`；不因B01/C04局部成功伪称全39已更新。当前混合路线对非C04缺件的真实SEC获取仍保持原受限边界，后续须单独接通并验收。

本机原账本只读/私有验证：`root-probe-final.log`记录原来源旧规则字节不动，当前副本从同一checkpoint使Salesforce B01正向准备为41,525,000,000、C04正向准备为0；`b01-history.log`记录B01私有Run第一次`CANDIDATE_READY`、第二次`NO_SOURCE_CONTENT_CHANGE`且成功尝试不变。`mixed-refresh.log`及`mixed-refresh-repeat.log`记录混合入口B01/C04各自第一次`CANDIDATE_READY`、重复触发均不增候选，整体因其它来源待办继续`UPDATES_INCOMPLETE`；原账本均143/143/52，调用0/0/0。这四份运行发生于写时复制优化前的当前规则闭包，不能冒称已经在最终代码树重做。其外部临时根也不是Git归档。

最终当前规则闭包的写时复制证据见`cow-test.log`：私有副本创建前后文件系统可用量差2.8MiB（单次macOS观察，不是跨平台承诺），当前B01/C04仍正向准备；改坏私有B06规则后，副本验证拒绝，而ROOT规则字节不变。`material-test.log`在**录制基线**上完成1项完整来源测试（49.451秒）：旧政策副本确实阻断旧默认B01，当前副本使B01通过，冻结基线缺Salesforce额外C04来源时仍拒绝，混合刷新给B01独立`CANDIDATE_READY`而整体保持不完整。`source-version-rehearsal.log`另以一次**相同真实保存字节的录制元数据响应**使来源账本版本从0变1，得到两个不同处理副本ID；B01再次返回`NO_SOURCE_CONTENT_CHANGE`、成功尝试不变。录制SEC槽不是真实GET或新业务结果，原#28总账仍143/143/52。

短回归`refresh-boundary-tests.log`为11项PASS；`c04-bootstrap-fast-fix.log`两项PASS，明确原测试的“发现错误必须是最后一条”不是新处理副本出现后的业务不变量。快速套件`fast-suite.log`为132/132通过（80.621秒）；`sec-default-regression.log`一项完整录制SEC获取/失败隔离默认入口100.237秒通过，原默认`initialize_source_inputs()`仍使用原独立复制行为。初次`fast-suite-first.log`的130项通过、2项旧错误顺序断言失败保留，修正后才记录完整绿。

首次来源探针因把可缺的C04规则副本当作必须存在而在复制前失败；初次写时复制反例选了属于展示文件、不会进入当前来源规则集的路径；前几次材料测试分别假设JSON空白会触发语义政策错误、冻结基线已含Salesforce额外C04来源、可在录制账本初始化前写来源，以及把所有本地Git身份读取也当成外部网络子进程。原日志保留，最终测试只允许本地只读Git命令、阻断网络/HTTP与其它子进程。

这不是正式采纳、生产切换、全390成功或新财年在线更新完成。旧候选/Run按原安装身份继续读取，私有副本只是本轮显式路线的当前处理输入；新代码和绑定须限定独审及新head CI另验。无provider/paid/SEC新调用，无#47分支、快照、账本或运行根操作。
