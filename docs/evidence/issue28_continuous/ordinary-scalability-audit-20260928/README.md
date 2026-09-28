# 私有普通发布的来源引用与授权日期扫描误报

当前`070f1c4e`的Enphase D04真实响应已在现行V14下零新调用生成新Run、完整版本准备包及1714文件独立冷读；但复用已有`OrdinaryIsolatedPublicationMaterialTest`时，在私有发布`stage()`内以`ORDINARY_PUBLICATION_SCALABILITY_FAILED`停止，尚未切换私有指针。原失败和960.034秒日志保存在同一任务的`d04-unified-release-20260928/publication-current.log`。只运行原`annual_publication._scalability_snapshot()`约9秒，得到七条拒绝：五条把原生来源引用的单字母`F`误认成Ford股票代码，两条把追加授权的`user_instruction_date`误认成固定财年日期。这里没有忽略真实公司身份或财年硬编码的理由。

显式后继`ordinary_scalability_audit.successor_scalability_snapshot()`仍遍历完整`config/company_registry.csv`、`scripts/`和`tools/`，复用原身份、CIK、申报号及日期匹配器；仅在AST位置证明单字母属于`NATIVE_FACT`等来源引用前缀，或日期是`delegation_source`等值核对中的`user_instruction_date`时排除。**冻结`annual_publication.py`与`sec_pipeline.py`没有改动。** 私有后继发布入口改用该扫描器并把新模块列入其执行依赖。定向测试证明实际当前树的误报消失，`ticker='F'`、硬编码CIK、`period_end='2026-09-23'`、以及同一行中混有合法前缀和非法身份/期间仍被拒。

`rebind.py`只更新未冻结`issue_28_v14`的两份执行文件绑定：修改后的`ordinary_isolated_publication.py`和新增扫描器，并同步三份当前禁网接线收据；V13清单字节未变，V14闭包为`sha256:221aa44fde504d3cb41f41bf6b63a885978bbaf6ff535559688454c5495f704c`。`binding-before.json`/`binding-after.json`保留具体哈希。没有改共享普通运行默认、记录类型、来源或调用权限。

最终定向9项通过（`directed.log`）；当前树完整扫描作为来源材料单项在240秒限时内返回0（`source-selector.json`）。快速套件首轮136项中只有新全树扫描在30秒限时返回124，保留`fast-first-failure.log`；将两个小反例留在fast、完整扫描放在`SOURCE_TESTS`列表末尾后，第二轮137项中仅未改的`test_ordinary_source_authority`在30秒限时返回124（`fast.log`），它隔离重跑6项6.647秒通过（`source-authority-isolated.log`）。**不能把这两次整体fast写成全绿。** 新增两个fast selector本身均返回0；本补丁的远端主CI及限定独立审阅仍待完成，不用旧head成功替代。

改变V14执行身份后，先前`070f1c4e`生成的D04 Run/准备包属于旧闭包；私有发布不得把它们重签或直接继承本补丁的通过。下一步在此新闭包从第173—178次原真实响应零新调用重建Enphase Run，再做受影响的准备、冷读与私有发布回退演练。旧候选、原失败及账本不改，真实新增模型/SEC调用0/0/0，无正式采纳、active切换或#47操作。

## 精确SHA独审后的P2回修

`652a2505`的[限定独审](independent-review/conclusion.md)为**NEEDS_FIX**，不能因上述9项通过而改写它。审阅构造两条反例：把`{'NATIVE_FACT':'F'}`的值用于`ticker`判断，或把`user_instruction_date`字典值用于`period_end`比较；首版仅凭局部AST形状就错误排除，完整扫描返回零行。审阅者35次底层工具、指定短测9/9，未运行长材料。

后续增量保留AST识别，但**只有**该AST形状所在的`file + line + literal + type`与`config/ordinary_scalability_exemptions_v1.json`登记的精确源文件SHA/size同时一致，才排除当前8条待限定复核的误报（新增扫描器自身的`NATIVE_FACT`前缀也计入）。配置列入显式私有发布`IMPLEMENTATION`与当前V14执行文件集合；被登记文件字节变化、登记行消失、重复或策略字段异常均拒绝。临时树即使复制相同语法、没有独立审批也继续报告身份/日期违规。没有按公司ID或来源原件给业务通过特例；此处仅约束静态审查的确切误报，真实公司ticker/CIK/期间硬编码仍必须报错。

两条审阅反例与改字节负例现在进入完整扫描器测试。修后11项定向通过；4个新增短fast selector在原30秒子进程中各返回0，当前代码树全扫描作为240秒来源材料selector在10.014秒返回0。V14后继闭包`sha256:1876c014183369af05b19a2d7e0e8c08c92d2e0b70388084250fedd5eb031c98`、V13原字节和三份接线由`rebind_followup.py`核对。新的完整fast与远端CI尚无全绿记录；前述两次fast失败仍保留历史原义。D04私有发布必须在**本次新闭包**重新验证，不能使用`070f1c4e`旧准备包取得成功信用；实际修后验证见下文。真实新增调用仍0/0/0。

精确`dea6e4a0`[修后限定独审](independent-review-followup/conclusion.md)为`PASS_WITH_BOUNDS`：两项旧P2反例都被完整扫描器报告，八项豁免的整文件SHA/size、行、字面值和类型闭合，V13未变，11项指定短测通过；审阅者没有重跑长材料或发真实调用，38次底层工具。父会话随后在**该闭包**从原真实Enphase D04响应重建新Run、准备一坐标完整版本并做1716文件独立冷读，全部通过。原私有发布测试又在隔离根完成暂存、私有切换与回读、回退、恢复、中断和镜像修复，1项4679.413秒通过；独立进程再读私有候选也通过，详见[同一D04证据](../d04-unified-release-20260928/README.md)。这些是执行方材料，不能扩成独审代理亲自运行的范围。旧`652a2505`失败审阅和两轮fast本地限时失败不改；新head远端CI仍待核验。业务调用0/0/0，生产未动。
