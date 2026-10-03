# D04 两份真实候选进入当前完整版本准备的版本边界

在已推送 `a863f722` 的产品代码树上，`prepare_private.py`选取现有 Enphase 与 Paramount D04 普通更新成功尝试的原生 Run、安装数据及真实响应身份，尝试经现有 `ordinary_release_preparation.prepare()`生成一份私有多坐标版本。两份输入原本各自为`CANDIDATE_READY`，完整来源审阅标记为真，Result仍为`WITHHELD`并由原D04限定范围规则投影为`TEXT_QUAL`。本次没有重发模型或SEC请求、没有改写原调用或提交生产操作。

**实际结果为失败，未形成新的完整版本。** `run_prepare.zsh`以nohup执行、`prepare.exit=1`；`prepare.log`显示准备器在第一份原生Run的`_mechanically_replay_open_run()`中被现行需求加载器拒绝：`Run Requirement Snapshot is invalid`，具体为`Continuous successor installed snapshot differs: baseline_manifest.json`。错误发生在组合矩阵及公开行之前，因此没有新的私有Publication、390坐标信用或冷读成功。私有输出根`/private/tmp/issue28-d04-unified-release-a863-20260928`是未完成的复制材料，不能作为已准备版本使用；本轮不删除或重新签署它。

`binding_diff.py`和`binding-diff.json`只比较这两份安装输入与当前代码根的V14清单。两份旧Run的baseline SHA-256相同，为`345712f3…`；当前head为`8258cf4e…`。父级声明未变，但七个执行文件绑定与三个规则文件绑定不同，包含D03新路线及共享原生收据组件。这证明了**安装时代码身份不同**，不证明所有D04语义都已改变，也不能据此让当前加载器忽略清单差异。旧Run既有独立冷读证据保持原范围；本次没有执行前后整树哈希，故不声称再次逐字节重验旧Run。

下一步在确定的当前实现下，从原已成功D04响应零新调用构建当前绑定的原生Run，再走同一完整版本准备与独立冷读；如果实际需要跨版本直接选择旧Run，须另有能认证旧安装代码及其相关语义的显式兼容路径，不能让自签旧包任意执行或取消当前快照断言。这里记录的是一个真实集成阻断，不是D04十家公司原候选失效，也不是要求重新购买模型回答。`prepare_private.py`与`run_prepare.zsh`是这次失败的可复核入口；未运行独立冷读。原账本真实新增调用0/0/0，生产、#47分支及PR52均未操作。

**后续当前绑定的正向路径（`070f1c4e`，私有发布审查前）：** `rebuild_current_enphase.py`确实从原第173—178次响应在当时当前V14闭包`sha256:b0a5faaf…`形成Enphase FY2025 `UPDATES_READY/CANDIDATE_READY`新Run；Result ID仍为`sha256:7bf9ea83…`，原成功包整树、账本195槽/143/143/52、来源日志和正式active前后字节不变，768.009秒，`current-enphase.exit=0`。该Run进入现有完整版本准备器，选中基础为`NATIVE_REVIEWED_DEFINED_SCOPE_STATEMENT`，公开`TEXT_QUAL`行，准备ID`sha256:8821edf8…`，前驱矩阵327行、未选389坐标；准备退出0。另一个独立进程重算准备包并核对1714文件前后字节完全相同，`cold-current.exit=0`。它新增的是一条现有真实D04结果进入统一私有版本**准备**的可复核路径，不增加D04公司数或390完成数。

继续使用仓库现有私有发布测试时，`stage()`在规模审查以`ORDINARY_PUBLICATION_SCALABILITY_FAILED`退出1，960.034秒，未走发布/回退/恢复；原失败见`publication-current.log`。具体七条误报及不放宽真实硬编码审查的显式后继修复见[相邻证据](../ordinary-scalability-audit-20260928/README.md)。该修复改变V14执行闭包，上述正向Run与准备包仍按**修补前**身份解释，不能直接写成修后私有发布通过；需要在修后闭包完成受影响的重验。没有新真实模型或SEC调用，正式生产指针未切换。

## 修后V14闭包下的完整私有发布链

`dea6e4a0`的限定后继扫描器已获[精确增量独审](../ordinary-scalability-audit-20260928/independent-review-followup/conclusion.md)`PASS_WITH_BOUNDS`；旧`652a2505`的`NEEDS_FIX`和第一次私有发布失败均保留。修后V14闭包为`sha256:1876c014…`。`rebuild_current_enphase_followup.py`只读第173—178次原真实响应与当前保存来源，用同一普通更新入口生成新的私有Enphase D04 Run `run:ordinary-integrated:275c6e31…`（878.605秒）。原Result ID仍为`sha256:7bf9ea83…`；旧成功包整树、账本195槽/143/143/52、来源日志和正式active指针均在执行前后字节一致，无新provider/paid/SEC申领。

新Run经现有版本准备器形成准备ID`sha256:e425bf77…`，选中依据`NATIVE_REVIEWED_DEFINED_SCOPE_STATEMENT`，FY2025公开行为`TEXT_QUAL`、空数值；327行矩阵只选此一坐标，另389个十公司指标坐标未选。独立进程从保存的准备包重算，1716个文件前后SHA完全相同，`cold-current-followup.exit=0`。这不是390项当前验收，也不增加D04十家完整真实候选的数量。

同一准备包进入**新建隔离根**的既有`OrdinaryIsolatedPublicationMaterialTest`，`publication-current-followup.exit=0`，实际1项完整测试4679.413秒通过。`publication-private-summary.json`来自私有根原总结：候选Publication `publication_2ede5655…`、前驱`publication_24bf8f16…`；测试依次通过stage、私有publish/read-back、rollback、restore、指针写入中断后的recover、损坏镜像修复，最终总结`PASS`、信用`NONE_ISOLATED_ORDINARY_VERSION`。另一个独立Python进程重新打开私有候选并核对准备ID、矩阵/证据哈希、Enphase D04 FY2025 `TEXT_QUAL`行、所选包文件及**正式**active指针前后SHA，`publication-cold.exit=0`。最后只读原账本仍195槽，正式active仍为前驱ID；没有Ready、合并、正式采纳、部署或生产切换。

这条路径让一个已有真实D04结果进入**共同版本准备与私有发布/回退/恢复链**，无需人工填数或再次购买模型回答。完整私有发布测试约78分钟，主要成本属于重复完整包重放；本轮没有优化它，也不把一次通过称为日常更新吞吐或十家公司×39项生产验收。`publication-profile.txt`是运行中一次1秒CPU采样，仅支持当时进程在JSON编码路径工作，不用它推断全程耗时根因。此前旧版本Run被当前加载器拒绝的原件、首版扫描器未通过独审及两次fast超时均保持历史原义。
