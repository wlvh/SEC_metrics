# 限定独审结论：REQUEST_CHANGES

审阅提交：`c0cef253ae5373e8c8fbd224d14cbb5bc941fab8`；相对基线：`e8fa288095edc894101628d49392572c9c49e7af`。范围仅为本目录 `task_contract.py`、`scan-prompt.txt`、`test_task_contract.py` 及必要保存测量证据；未变旧mapper/CLI/context helper沿用原限定审阅，只核对本原型实际调用的机械合同。不授语义、完整公司、DeepSeek、普通入口、真实控制器或运行许可信用。

开始：`2026-10-04T04:18:35+00:00`；结束：`2026-10-04T04:24:00.182727+00:00`；约`5.42`分钟。工具实际20次（7个functions.exec wrapper＋13个nested exec_command，按保守口径累计）；普通消息3条（开场、一次进度、最终报告；没有问题），均在80次/90分钟/3条上限内。此结论针对上述确切提交，不覆盖后继修订。

## 一项必须修正的P2

`scan-prompt.txt:3`把行压缩表示写成“arrays of arrays”，并指示读取不存在的 `payload.row_layouts["blocks" or "facts"]`。该提示由`task_contract.py:27–32`直接进入实际拟发system message，但调用的 `_shared_units` 实际输出是 **`payload.blocks`/`payload.facts` 为按原索引字符串编号的字典，解码元数据是单数 `payload.row_layout`**。必须按 `row_layout.source_order` 取字典对应键、按`row_layout.columns`还原行，并按其`fact_columns`还原嵌套fact；不能把JSON字典序当原顺序。

独立有限实证：对保存完整Marriott Source只构造事实418所在的一个既有任务。请求SHA `b3d2c6ee826c29cb64f1f5b502f5fa7542b7fe121c971dfc70b8e5b2b1666ea7`与保存测量行一致；549182字节、185857含4096预留的参考上下文令牌。五个提供单元全部使用`dict`行容器和`row_layout`，全部没有`row_layouts`；其中可见文字索引1753起、facts索引1/229/429起。原件可逆复原相等，但提示给独立输入读者的解码规则与这些真实字节不符。现有11测全部通过仍未检验这个提示/打包格式一致性。

影响是拟交付输入合同本身存在可修正缺口；本审不推断模型实际会误读或已造成语义错误。修正这段提示并以实际打包形状/原序作一个必要机械回归即可，按提示真实差异更新相关资源测量绑定；不需要重做旧抽取、全公司语义或完整长链。

## 已覆盖的机械判断

- 完整Source依赖调用者固定摘要：`_source`验证完整序列化、整个Source及每原单元身份/字节摘要；`scan_plan`按原序遍历且最终flatten必须等于完整`required_unit_ids`、无重复。每次完整原责任单元及同文档完整身份单元经打包/复原相等校验；没有裁掉原payload。发行人身份上下文不保证所有相关上下文充分，这一限制在实际payload明确保存。
- 六字段新回应先对**完整原响应字节**执行4096参考token检查、严格JSON与`scan_complete`检查，然后才对内部四字段外壳/七字段finding形状作旧检查的投影。投影不是新响应原件，不登记为旧执行；整体响应对象与外部摘要保留。未完成必须有未决文字，64finding是结构上限，并不证明全部责任能装下。
- 扫描任务提供的实际请求字节、摘要、payload、提供单元均必须与完整Source重建相等；后续又要求显式传入`actual_request_body`及外部预期摘要，与所拟定请求逐字节一致。独立对两个阶段各追加一个空格并重新计算其摘要，仍分别被`INPUT_CHANGED`/`ACTUAL_FOLLOWUP_REQUEST_CHANGED`拒绝。此处只证明离线字节身份，没有网络执行证据。
- 补取使用原责任引用作anchor，只在同一文档按原XML id或原正文闭区间查找。literal `continuedat`只从成功定位的原属性向前追踪，轨迹保存原前后请求；不从关键词/公司/事项猜关联。独立禁网重放Marriott事实418的`f-408-1→f-408-2`，与保存packet/trace逐对象相同，两位置、4878已定位context字节，后续返回`FOLLOWUP_STRUCTURE_READ`且语义/公司信用仍false。
- 模型请求和自动literal续接合计最多8位置；单个正文range最多32块；262144上限针对已定位context item列表的JSON字节累计，包含packet元数据的完整请求另外按8MiB/200000参考上下文上限检查。缺件、歧义、超块/字节为带原因UNRESOLVED；循环与第九位置保留pending后停止后续请求，不丢掉第一原答。循环/八位置及资源拒绝的指定测试部分使用替身，本审不把这些替身当实际大材料实验。
- 只提供一个后续判断入口。后续再要求上下文则返回`STOP_FOLLOWUP_CEILING`、保持原请求/回应与remaining需求、不构造第三次执行。`scan_complete=false`且仍有工作时未决文字保留，即使无新增context也不获完成信用。重复调用这些离线函数本身没有持久controller计数守卫，代码和README已准确声明这一点。

## 停止上限与证据边界

独立读取并验证两份完整保存Source实际字节摘要以及报告中每任务owners：Marriott17原单元全一次责任/5首轮/最多5后续/设计最多10次；JPM130原单元全一次责任/38首轮/最多38后续/设计最多76次。两样本合计43首轮、设计最多86次。此算式在“一首轮最多一后续、无retry”设计下准确；不是完成保证、用量收据、已获调用机会，也不是当前持久controller守卫。默认每任务最多4原责任单元是分组参数；函数允许调用者选择其他正整数，不能把默认4写成不可更改的业务政策。

报告中的全样本token测量是已有父证据，本审核其绑定/责任/算术并独立复量上述一个Marriott任务，**没有重跑两家公司全计划**。保存的最高参考上下文Marriott185857、JPM186145和“全首轮fit”不证明实际4096输出责任可完成、补取充分或剩余八家公司资源够用。整批语义/完整公司合并/保存读取、独立输入使用、DeepSeek、真实控制器机会及最终接线均未覆盖；新JPM模型抽取批次没有发生。

## 独立执行证据

`unit-tests.log`：按指定命令独立运行11项，0.368秒，exit0。`actual-source-probes.log`：独立禁网有限实际Source重建、解码形状、完整责任/身份复原、原continuedat冷读取及两个请求篡改反例。`review.log`：精确文件摘要、提交匹配、保存Source/责任算术核验及审阅计数。

只新增本`independent-review/`中的本结论与日志。未改产品、原件、父证据、旧响应/终态或其他现场；没有spawn、commit/push、打包、真实模型/SEC请求、账户操作、运行根/账本操作。父工作树已有`execution-state.json`修改仅观察，不消费为审阅证据，也未操作。
