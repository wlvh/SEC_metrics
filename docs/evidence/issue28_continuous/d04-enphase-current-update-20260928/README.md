# Enphase D04既有真实响应进入当前普通更新

目标是核对第173—178次已成功的Enphase D04原响应能否在**当前**`task/b06-new-source`绑定下，经过正常更新入口形成可保存的公司候选；不重新发送模型或SEC请求，不重做已通过的2482秒录制生命周期或D04十家公司冷读。源为#28固定总账`source-inputs`，处理状态根为隔离的`/private/tmp/issue28-d04-enphase-normal-b868-20260928`；这不是生产状态根或新版390坐标索引。

`run-existing-real.py`用实际 `CallLedger` 的只读当前快照与当前V14禁网接线，阻断socket、DNS和非只读子进程，在普通`run_company(metric_ids=['D04'],native_assessment_mode='LIVE')`中仅复用原成功响应。`run.log`实际终态`UPDATES_READY / CANDIDATE_READY`，Result ID `sha256:7bf9ea839cb7ef2c636ebf524fb4305056a048447880bd37e2df81664483f99b`与原Enphase完成收据相同，理由仍为`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`；Run本次从当前输入重新构造，没有为原响应重新赋予调用信用。固定账本前后计数均143/143/52、行数195、调用目录名不变；binding、claims、来源请求日志及active的指定哨兵文件哈希不变。一次当前普通更新耗时1150.446秒，不能推论正常在线全年更新总耗时。

第一轮独立进程确实从安装的代码与来源副本重读出相同Result ID和公开行摘要，但启动时生成Python字节码缓存，令“私有历史整树前后字节不变”失败；失败的原始`cold-initial.log`和`cold-initial-result.json`保留，不能计为完整冷读通过。仅在冷读启动器禁用字节码写入，并使`PASS`在全部断言通过后才赋值。最终`cold.log`与`cold-result.json`：独立进程从安装运行根重验相同Result、需求闭包和公开行；930个当时已有文件前后哈希一致、改动0、网络0，158.412秒通过。首次额外产生的缓存文件仍留在隔离测试根；不把首次失败抹除或说成原账本/原Run损坏。

`repeat-existing-real.py`在同一当前状态根重复触发真实保存输入，`repeat.log`实际返回`UPDATES_READY / NO_SOURCE_CONTENT_CHANGE`，耗时430.333秒。重复尝试有自己的终态，但`successful_attempt`仍指向原当前Run，`new_candidate_created=false`；原成功包全树哈希不变，Result ID仍为`sha256:7bf9ea83...`，总账计数143/143/52和195行均不变。重复触发不会为相同来源再建一个Run或购买回答。

`reconcile.py`只读原Enphase真实完成/冷读摘要及本次Run、独立冷读和重复收据，`reconciliation.json`交叉核对原173—178序号、原Run与当前Run不同身份、**同一个Result ID**、当前V14闭包、公开行字节与FY2025期间。原Result仍`WITHHELD / D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`，当前公开行为`TEXT_QUAL`的限定来源结论，不能解释为财务健康保证。它也核对零新增provider/paid/SEC。原保存材料与旧Run未被重签。

本项增加的是**当前正常更新入口复用既有真实公司结果、持久化冷读与重复触发幂等**的限定证据；D04原来的10/10公司候选数量不变，不构成正式采纳、生产切换、跨财年新报表在线更新或390统一验收。实际新增provider/paid/SEC为0/0/0，#47/PR52的分支、来源及账本未使用。

执行所用代码head `b868ac42` 的主CI [`36354613173`](https://github.com/wlvh/SEC_metrics/actions/runs/36354613173) 已整体SUCCESS（15/15作业，含保存来源两片和汇总）。CI覆盖的是该head的既有测试，不独立重跑本目录1150.446秒的真实既有响应普通更新；两者的证据范围不能互换。
