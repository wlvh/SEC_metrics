# 原173–178 LIVE处理输入：#28消费者补验与可读材料

回应#54评论5960148666；固定提供方 `8a521e32204866021955f8330080a024db5f1b3c`，本方实际测试head `64c95e71eb85590afb66721b61be768087e5124d`。测试准备使用本方独立clone，不操作#54工作树。仅走新 `company_processing.export_processing/authenticate_processing` 和 acquired-source 拒绝；没有重跑D04十家或原Run冷读，没有调用provider/SEC、重登记或生成公司Result。

原输入来自此前持久化的Enphase安装 `native-candidate-results-20260924/enphase_energy/data`，原input_id `44801106654d1a1fa57ed9120f8238e832c7cfe8ce5072976ff628cb6871f314`、source_id `6fbbc9244e78b185ff176d9431aefc173cfc8c02d3058fcd41b1ee7fc6761c05`，原V14闭包 `568ab1eb52f4f44721e94a871efe78caf389862213a9c9278201c31b7e67c8d2`。LIVE六组173–178的请求、回应、执行与接受记录保持，原110/171/172失败和全部计数不变；历史授权对象保留，不是新的调用许可。

新导出13.641秒完成；原登记JSON3118724字节逐字节相同。`input/`是**独立的计算处理材料**，包含该登记、处理来源快照及#54生成的处理元数据；不是SEC原件包，不要求新来源携带旧AI答案。处理程序未携带SEC evidence、模型登记或Git alternates。原登记含历史接受及执行证明，这不授予接收方本次结果信用；接收方仍须按真实来源、固定程序和自己的受控信任登记核验。

原固定程序无需重新打包：`runtime-git-equivalence.json`证明662个程序/规则/受绑定文件中661个与Git提交 `fd31d639aa3a1315d85ea2ac87f83b855bdf20d8`逐字节相同；唯一不同的 `outputs/scalability_audit.csv` 是原安装的56字节文件，已原样放在 `runtime-exception/`。完整路径、SHA256及大小来自实际#54导出元数据，可按现有安装机制从该提交和该例外恢复，不用当前代码重签原V14。此处不再复制整个运行树、不生成tar.xz、不重生成旧MANIFEST、不复制原Result/Run作为答案。

计算侧定向认证在外部processing trust下通过，错误公司被 `COMPANY_PROCESSING_WRONG_COMPANY_OR_AUTHORITY` 拒绝。对本方前次已安装的真实52捕获混合公司来源调用新入口，得到明确 `COMPANY_PROCESSING_ACQUIRED_SOURCE_ADAPTER_REQUIRED`；Enphase state全部文件保持、没有updates/Run产生。这是当前#54显式baseline-only入口的实际边界，不是声称原LIVE判断失效或要求重新付费。原件/来源checkpoint与处理记录之间的acquired-source等价适配仍由#54主实现，本方补消费验证，不另造公司包或关闭守卫。

第一份脚本将报告写在禁止访问的原代码根，保存报告失败，原脚本及日志保留。修报告到外部可写目录后复用已经完成的导出，未再认证原Run或执行新计算；认证及拒绝0.488秒。子进程拒绝读取原仓库和私有ledger、拒绝open写处理程序；父进程随后核原账本根文件、来源日志、active和原登记前后SHA相同。审计是Python边界，不冒充内核隔离、动态UID、只读挂载或OpenShift实测。

结论只授已有合法LIVE输入的独立导出/认证与明确兼容限制。没有证明当前acquired公司来源能完成D04，没有新真实模型结果、完整39指标公司或390信用，原十家D04候选按原身份保留。当前#54新处理入口和其原V14需求分别固定，代码/规则读，processing/source trust由受控准备端写后只读，报告与更新状态写外部根；没有个人HOME、可写主程序、root或unshare的新平台默认。
