# D04完整响应合同：记录响应原生材料与真实Ford进度

本目录的V5完整响应合同要求逐一返回请求中所有来源单元，不能用空findings省略整个单元。这里分别保存完整**记录响应**原生材料和真实请求70/71；两类证据不互相升级。

## 完整V5记录响应材料

`native.log`：完整Enphase来源的6个新合同请求，经明确记录响应、原生Evidence/Review、OPEN Run及公共行通过，303.604秒。Run为`run:ordinary-integrated:934d9bb31656478ff25d60199b71b690b767211076c3a52d275ef9f8de75964d`，Result为`sha256:7bf9ea839cb7ef2c636ebf524fb4305056a048447880bd37e2df81664483f99b`。缺请求、把recorded改为LIVE、改请求格式、改响应覆盖合同均拒绝。

`cold.log`证明复制的OPEN包通过冷读，11条原生记录和1个Review决定重验通过，网络/进程事件为空；`real_model_credit=false`。`current-wiring.log`另有真实工厂/opener/WB-3禁网接线及原身份2项测试，59.858秒。以上均为0/0/0真实调用，不能写成真实模型已完成Enphase或十家公司D04。

## 真实Ford：接受1/11个原请求，尚无完整指标

原始合同的Ford任务有11个请求。固定账本70、71均为真实provider执行，完整摘要见`real-call70-71-index.json`。

| 原槽 | 原始request_id | 原终态 | 本次准确含义 |
|---|---|---|---|
| 70 | `sha256:77a7d67057a27769f42a148ffb103fc4eff5abe423cf4edc3e571e686ce98775` | SUCCEEDED | 本请求5个来源单元通过，创建原生Candidate/Evidence；未创建指标Result |
| 71 | `sha256:cd327064f63d440e30c9c8dbbf7e3e77b07320f710ad7b78f81819b26325a05a` | FAILED_TERMINAL | 返回4个单元，但首个unit_id抄写少一个`f`，被当前检查拒绝；无可用结果信用 |

第71次原错误为`D04_RESPONSE_UNIT_CENSUS_ORDER_CHANGED`。逐字核对实际缺陷是首个标识符的64位摘要变成63位：

- 原请求：`sha256:b27d6d307ee950d7f2e0e7f01e30693fad427f02d0cdd20a7a93c880fe93789c`
- 原返回：`sha256:b27d6d307ee950d7f2e0e7f01e30693fad42702d0cdd20a7a93c880fe93789c`

其余3个ID逐项相同。原返回、错误名称和FAILED终态均保留，没有补回`f`、重签或重新发送该请求。此错误也不能被描述为已经证实的业务分类错误。

70的SUCCEEDED和exact ID保留，只能在原请求/来源/收据及当前检查均满足时复用，不能借给不同提示、格式或新请求。`d04-assessment.json`明确`acceptance_scope=ONE_REQUEST_SOURCE_ASSESSMENT_NOT_COMPLETE_METRIC`、`native_result_created=false`、`semantic_correctness_verified=false`。Ford目前是**1个已接受、1个失败、9个未执行**，仍有10个请求未获得完成信用；没有完整Ford D04 Run或“未披露持续经营疑虑”公共结论，也没有新增完整真实390坐标。

## 固定总账与CI

通过只读共享目录锁调用原生`CallLedger.snapshot`，核对71个顺序槽、claims/intent/terminal身份及终态证据哈希：累计**provider/paid/SEC=36/36/35**，剩余**204/204/45**，无UNKNOWN槽，`stopped_channels=[]`。账本、初始化锚点与70/71所有文件核对前后字节不变。见`ledger-through-0071.json`、`ledger-preservation-sha256.json`。未增加任何调用；空的全局停止通道不解除第71次受影响路线的修复/审阅停点。

GitHub实时核对CI34955496714已12/12成功，仅绑定`ddecbf03b98c9c40f24be87c8181ae9077cb7ae3`。工作区后续差异没有借该CI取得信用；原记录见`../review-5207290213/ci34955496714-verified-through71.json`。

## 原件归档

`real-call70-71-material-index.json`逐文件绑定两槽的完整source/request、原发出请求、原响应、原生收据/保留记录和原执行清单；必要新增字节保存于`real-call70-71-objects.tar.xz`，沿用既有objects/仓库同字节引用格式。已用既有还原器在新进程、新目录实际还原35个文件，并逐项与原槽字节、索引SHA及完整文件树比较一致；见`real-call70-71-restore-check.json`。还原未修改固定总账或赋予新执行信用。

```bash
python3 docs/evidence/issue28_continuous/b13-native-assessment/restore_material.py --evidence docs/evidence/issue28_continuous/d04-complete-response-contract --index real-call70-71-material-index.json --repository /absolute/checkout --output /absolute/new/call70-71-material
```

当前计数和剩余调用计划见`../review-5207290213/d04-representative-plan.json`。D04、B13、D03、修后验证、正常更新和最终验收继续共享同一累计预算；本目录不授予Ready、合并、采纳、部署或active切换。
