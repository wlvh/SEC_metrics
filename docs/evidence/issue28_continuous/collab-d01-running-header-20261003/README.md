# JPMorgan D01：页眉混入标题的本方接入

## 原件与受影响结果

读取固定 #47 `af29ab2f41f40a442c13a3453c97d2c476f3536b` 的新增登记后，本方从已保存普通Run核对原主文 SHA `4d9febdb…`、源码跨度`1691112:1691126`及其上下文。`Parts I and II`在分页后、关闭Item1A的Item1B之前，是页眉。它作为第57项进入本方 FY2025 D01 Result `99442738…`，与原390索引是**同一身份及文字**。`audit.json`保留原来源/RawBlob/Claim、精确跨度SHA和上下文；未复制历史路线Result或验收信用。

该确切旧身份已在本方登记并由既有390读取入口扣留。当前仍选中的已知缺陷由17变18；C02/E01旧合同待新目标验收仍为20，其中8项并非确诊，原两个D01修后坐标保留。旧Run/Result/原件/总390分母不改，不按D01名称撤回其他公司。

## 固定接收与适配

提供方修复仍在 `pending-rule-changes/d01-running-header.patch`，没有把它说成已正式应用。只定向接收其中 `SEVERAL_PARTS` 和派生函数的选择器导入替换；在本方 `d01_running_header_28_v1.py` 固定该算法与必要小型源码编译守卫，`d01_emphasis_results_v3.py`固定旧V2实现并仅适配策略名与两处派生调用。没有复制历史引擎、快照或整个补丁，提供方继续维护共用核心。

新入口为显式 `RUNNING_HEADER_V3` / `D01_EMPHASIS_SOURCE_V3_RUNNING_HEADER`。正常CLI由本方新包装器选它，使用独立 `metrics/D01-header-v3` journal；其它指标委托既有包装器。`ordinary_update_cycle`新增可选`d01_header_revision=False`，共享 `text_api`新增`d01_running_header=False`；原 `d01_emphasis=False/True`分别保持旧默认/V2。冻结 `run_store.py`、`risk_signals.py`、`text_results.py`以及 `_binding()`函数源码均逐字节保持，见 `default-compatibility.json`。

冻结Run验证器只按指标取默认API，所以旧D01 API需在**显式V3策略**收到时委托新后继，默认None/V2仍走原逻辑。此处没有改冻结验证器、删除校验或默改旧记录结构。V13未冻结政策镜像与规则/执行列表、V14必要父级及执行依赖按实际变化更新；未增加真实调用用途、额度或生产权限。

## 实际验证

- 短正反9项通过：单/双部分标签、包含这些词的真实风险标题、重复原位置、篡改文档、精确替换、磁盘源码偏离及错误指标；完整快速套件 **151/151**通过。390读取短测19项也按新增已知缺陷18通过。
- 十家当前保存原件在同一重建文档上比较：只有JPMorgan **57→56**，恰好少该页眉；其他九家完整候选逐字节相同。Marriott38条下划线标题、Paramount38条含`U.S.`标题均保住。原文档/跨度不改；这一已用于开发的语料不是留出验证。
- 普通CLI在当前规则私有处理副本创建JPMorgan新私有Run/Result **`f8da5496…`**，180.243秒；全部56条标题顺序与原件对应，旧页眉不存在。独立进程同源重入60.705秒为`NO_SOURCE_CONTENT_CHANGE`，只有一份新Run。
- 从新安装代码/数据根单独冷读53.467秒，拒绝读取原checkout、网络和子进程；公开CSV逐字节相等，完整attempt文件前后SHA保持。此为安装重放，不替代56条内容的全面独立阅读。

`material-summary.json`记录实际代码基线`9e37beb9`加未提交差异、真正安装/数据路径、Result和源保护SHA；后续提交仅按相同被测源码登记，不能伪称上述执行已经在未知后续SHA完成。该新候选尚未授390/完整业务/生产信用。精确源码提交`31beeab5486a30366afa395124c7ecbb492c93b8`限定独审通过：审阅者核验实际安装的404个执行/规则文件与该提交逐字相同，亲自执行9项短测、19项390读取及6项独立反例；39工具、2条普通消息，未复跑长链或授完整内容信用。详见`independent-review-31beeab/conclusion.md`。

## 失败与复用边界

首绑定失败是未同步V13政策镜像；第二次是把仅由父级携带的新规则误加入V14独立规则集合，均已修正且日志保留。源材料首轮发现原获取根含旧规则镜像，未修改该真实根；改用既有 `current_processing_source`、持原目录锁建立私有当前规则副本，保留完整原日志/checkpoint及源身份。

随后十家比较已全部通过，但首CLI原生重放仍取旧D01 API，返回`D01_EMPHASIS_POLICY_INVALID`。修复显式V3委托后，复用已通过十家比较，只重跑受影响CLI/冷读；初失败journal和部分Run在原私有目录保留。最终使用另一明确当前版本状态根，不改签初失败或旧年度结果。

真实账本/源log/active前后字节相同，实际新增 **0/0/0**。当前真实调用接线收据实际核验为`STALE_REFUSED_BEFORE_REAL_CALL`，原拒绝保留，未只改收据哈希；下一条真实请求前必须补受影响最短禁网factory/controller并校验最终绑定。本段未发送请求，没有#47/#54工作树、账本、快照或运行状态操作；无Ready、合并、采纳、部署或active切换。
