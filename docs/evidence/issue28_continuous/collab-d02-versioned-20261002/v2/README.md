# D02 Item 8 共用规则 v2：本方显式普通路径接入

#47 的共用实现由其负责人在提交 `147957c400c3361ab26ee0b04bbb89b2a692cadd` 修复；本方增量读取时对方分支为 `3e061e8a70fc1cdbe50c1b255d37efecf007ae12`，规则源码与词表Git blob分别为 `18432749…`、`e65ccafc…`，其后未变。`verify-peer-copy.py`证明本方专用 `d02_item8_category_28_v2.py` 除两处词表路径外与固定源码相同，词表只适配 `reader`、`supersedes` 和本方需求快照说明。旧v1模块、规则、Run和Result不改，也没有导入对方历史运行或验收信用。

本方在原D02显式参数中新增 `ITEM8_V2` 值：**默认未选后继的参数、返回结构和旧绑定不变；旧 `True` v1 路径仍在新Run/更新前拒绝**。旧 `ordinary_d02_category_update.py` 也恢复原字节和拒绝行为；正常更新CLI明确改选新的 `ordinary_d02_category_update_v2.py`，只为新的D02尝试使用本方`metrics/D02-item8-v2`独立状态根。来源准备、原生Run、保存和重读按策略身份区分新旧。未冻结V13父级及V14后继更新实际执行文件、三份已有接线收据；前后闭包见 `binding-before.json`、`binding-after.json`。第一次绑定脚本在父级清单尚未与新规则列表同步时拒绝，第二次因误将父级新规则也加入V14自己的专属规则集合而拒绝；两次错误由工具输出转录在 `binding-attempts.md`，重定向日志在重跑时被覆盖，不能称为原始持久日志。最初接线把v2行为直接放进旧包装器，随后为了保持共享旧入口逐字节不变，改用上述新包装器并只改正常CLI选择，因此第一次私有Run只属中间代码树；**最终**V13闭包 `sha256:f5f6bf76dee5222f87e643adf941a7e9e8d12385a4ddb93cb3e3824a9bf3ef84`、V14闭包 `sha256:9e4e95c06501ebb257b3880a1ceddc31fb1971e23776a91d07b834d80892c2e7`、三收据均通过。收据是执行身份检查，不是新真实调用许可。

`compare-current.json`在本方保存原件上比较了Lumen、Pfizer、Paramount、Enphase的63个Item 8关键词候选：v1/v2在这四家公司没有选择差异，已知四个类别误纳块 Lumen1670、Pfizer2175/2240、Paramount2257 仍排除，Paramount2108真实诉讼段仍保留；两条审阅者构造的“本公司面临诉讼，后接从句”及“诉讼由客户提起”的v1误删在v2均保留。它只证明这些已见正反例，不是全部真实来源的漏选或内容验收。**最终树**受影响来源测试3/3、fast选择器146/146通过，见`directed-final.log`、`fast-final.log`；旧v1包装器仍返回拒绝。

最初的普通CLI在禁网、禁旧语义生产的外部状态根为 Lumen FY2025 创建一次私有`CANDIDATE_READY`原生Run：已选摘录15→14，1670移出，Evidence `PASS`，Result `sha256:845ef41fd5d00cd8c82d698bc894efb24a86b814dc62f5ab6843d3e41f24ab53`。证据脚本在Run写入后误读绑定摘要键名而退出1；`run.log`保存失败，`recover-run-report.py`只读同一次尝试、terminal与原生记录生成`run.json`，没有补跑它。随后另一进程`cold.py`重读并重入为`NO_SOURCE_CONTENT_CHANGE`。这份初始Run仅覆盖中间包装器字节；初始脚本没有保存保护文件哈希前后对照，不据此证明那项边界。

**最终代码树**改为独立v2包装器后，使用另一独立状态根进行必要重验：`run-final.py`在67.741秒产生一次私有Run `run:ordinary-integrated:18cf3dfa…`，Result内容ID仍为上述 `845ef41f…`，Evidence `PASS`；原账本、来源日志、active前后哈希不变。另一进程`cold-final.py`重读安装包和公开行并重复触发CLI，39.657秒返回`NO_SOURCE_CONTENT_CHANGE`、同Result、不生成该状态根的第二Run，保护文件哈希亦不变。两版私有Run分开保存且都没有正式390或生产信用；最终树真实provider/paid/SEC调用0/0/0。

这项接入解决了**v1已知逗号误删导致的普通更新停用**，也形成可重读的v2私有候选；尚未审核Lumen其余14段的全部业务相关性与漏选方向，更没有证明十家公司D02完整结果。原有四个已知错误旧Result继续按精确身份扣留，新的私有Result也不领取当前390或生产信用。新的源码差异仍需精确SHA限定独审；通过后按受影响范围决定是否追加内容审阅，不以程序`PASS`替代合同内容正确。
