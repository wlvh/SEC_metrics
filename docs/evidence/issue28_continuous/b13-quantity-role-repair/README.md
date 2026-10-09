# B13 数量角色证明与主体时间：隔离修复

待应用运行补丁：`/tmp/sec_metrics_issue28_continuous/b13-role-proof.patch`。新 `capacity_quantity_roles.py` 由 `capacity_semantic_review.validate_response` 与 `capacity_text_results._prepare` 共用；原年度配对/Calculator未放宽。主运行文件尚未应用。新增/修改测试文件已写工作区。

第94次原请求仍FAILED。独立原角色探针显示，去掉响应矛盾limit后，无数量的生产质性句可被ACTUAL_PRODUCTION错收；两条行业整体容量被TARGET_REGISTRANT错收。原82仍由独立sales-only守卫拒绝。诊断原件与hash见相邻 call94-role-probe 和 call82-role-probe。

修复增加反向数量角色证明：有限已支持年度原件量或明确的契约制造安排季度容量；无法证明的直数量句式保留具体实现未决。季度角色不等于年度可比，保留原季度，不年化；其明确数量也不能被OTHER_CONTEXT错误抹去。行业整体断言只在同证据存在同一finding时段的目标容量断言时可支持TARGET；任意our/industry词不单独解锁。

根独立审阅发现的两条时间附着错误均保留：运营前置2024被当当前；历史自己容量被用来解锁当前行业标签。修后记录运营断言自己的明确年度，原因前缀/后续shipping年份不自动扩散；未知时间具体未决。当前等待根对修后范围复核，不将自测记作独立通过。

验证：16个限定测试通过；4个完整 Enphase 原件文本/Review 测试17.572秒通过。后者显式在保存原HTML上构造新scope输入身份，是记录测试，不借旧源请求信用。无量/行业错误标签延伸至纯原生文本结果与公共缺失行专用投影并被拒；正确季度文本完成。未执行完整磁盘Run，未发任何真实请求。

下一步：根同范围复核、应用并加入V14/V15执行/安装闭包，再按实际影响验证完整native Run；第82/94原失败不能升级。


## 来源数量义务的独立发现与修复

后续独立审阅又实际发现：未知数量句式可由OTHER_CONTEXT/遗漏抹掉，生成原生未披露结果；只列produced/was还会漏totaled/amounted关系族；把数字后of/our/we泛排除又漏掉partitive数量。所有旧探针保留，不能只记“待审”。

当前待复核补丁SHA `f2291a0212a9b4906e573de52d1c635d9c909c9595ce2f7e114c944de4a2742f`。来源端复用既有生产/产能候选关系族，逐句保留未获同句proof支持的数量义务，不随模型标签改变。普通of/our/we及未证明的年形数字不再形成排除依据；日期、期间计数、货币/百分比、产品代码和取消规划计数必须有相应结构。18项限定测试通过；82/94只改错误角色并保留原引用的合成变体仍无未决。当前仍待独立复核，不自动赋真实成功或新调用许可。


## 修后独立复核

`independent-review/v4/review.json`绑定上述f2291a补丁及三个受测模块SHA。独立复核状态为 `NO_BLOCKING_FINDINGS_IN_REVIEWED_SCOPE`，关闭 `B13_ROLE_REVIEW_01`及totaled/amounted/partitive变体；原发现报告保留。未知量OTHER/遗漏不能形成原生/public未披露，809季度量及82/94拒绝/修正变体、期间/原因作用域对照保留；21项相关测试20.018秒通过。

这是定向代码及可执行反例复核，不是全PR批准，不覆盖新绑定完整registered Run、新真实B13验收或生产权限。原82/94失败不变。
