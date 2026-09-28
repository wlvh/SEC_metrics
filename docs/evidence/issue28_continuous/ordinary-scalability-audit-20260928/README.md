# 私有普通发布的来源引用与授权日期扫描误报

当前`070f1c4e`的Enphase D04真实响应已在现行V14下零新调用生成新Run、完整版本准备包及1714文件独立冷读；但复用已有`OrdinaryIsolatedPublicationMaterialTest`时，在私有发布`stage()`内以`ORDINARY_PUBLICATION_SCALABILITY_FAILED`停止，尚未切换私有指针。原失败和960.034秒日志保存在同一任务的`d04-unified-release-20260928/publication-current.log`。只运行原`annual_publication._scalability_snapshot()`约9秒，得到七条拒绝：五条把原生来源引用的单字母`F`误认成Ford股票代码，两条把追加授权的`user_instruction_date`误认成固定财年日期。这里没有忽略真实公司身份或财年硬编码的理由。

显式后继`ordinary_scalability_audit.successor_scalability_snapshot()`仍遍历完整`config/company_registry.csv`、`scripts/`和`tools/`，复用原身份、CIK、申报号及日期匹配器；仅在AST位置证明单字母属于`NATIVE_FACT`等来源引用前缀，或日期是`delegation_source`等值核对中的`user_instruction_date`时排除。**冻结`annual_publication.py`与`sec_pipeline.py`没有改动。** 私有后继发布入口改用该扫描器并把新模块列入其执行依赖。定向测试证明实际当前树的误报消失，`ticker='F'`、硬编码CIK、`period_end='2026-09-23'`、以及同一行中混有合法前缀和非法身份/期间仍被拒。

`rebind.py`只更新未冻结`issue_28_v14`的两份执行文件绑定：修改后的`ordinary_isolated_publication.py`和新增扫描器，并同步三份当前禁网接线收据；V13清单字节未变，V14闭包为`sha256:221aa44fde504d3cb41f41bf6b63a885978bbaf6ff535559688454c5495f704c`。`binding-before.json`/`binding-after.json`保留具体哈希。没有改共享普通运行默认、记录类型、来源或调用权限。

最终定向9项通过（`directed.log`）；当前树完整扫描作为来源材料单项在240秒限时内返回0（`source-selector.json`）。快速套件首轮136项中只有新全树扫描在30秒限时返回124，保留`fast-first-failure.log`；将两个小反例留在fast、完整扫描放在`SOURCE_TESTS`列表末尾后，第二轮137项中仅未改的`test_ordinary_source_authority`在30秒限时返回124（`fast.log`），它隔离重跑6项6.647秒通过（`source-authority-isolated.log`）。**不能把这两次整体fast写成全绿。** 新增两个fast selector本身均返回0；本补丁的远端主CI及限定独立审阅仍待完成，不用旧head成功替代。

改变V14执行身份后，先前`070f1c4e`生成的D04 Run/准备包属于旧闭包；私有发布不得把它们重签或直接继承本补丁的通过。下一步在此新闭包从第173—178次原真实响应零新调用重建Enphase Run，再做受影响的准备、冷读与私有发布回退演练。旧候选、原失败及账本不改，真实新增模型/SEC调用0/0/0，无正式采纳、active切换或#47操作。
