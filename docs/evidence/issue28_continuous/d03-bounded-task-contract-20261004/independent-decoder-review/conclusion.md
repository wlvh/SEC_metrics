# 行解码修后增量独审：LIMITED_APPROVE

指定提交：`ada4647a106d32dacd1e40811294edf32034bb74`；相对基线：`c0cef253ae5373e8c8fbd224d14cbb5bc941fab8`；分支：`task/b06-new-source`。范围仅为`scan-prompt.txt:3`的机械行解码说明、`test_task_contract.py:175`新增回归及提示变化影响的资源绑定。`task_contract.py`、实际打包/复原代码及测量脚本与基线未变。原`../independent-review/conclusion.md`的历史REQUEST_CHANGES保留；本结论仅关闭其提示与真实表示不一致的P2，未变审阅范围及既有信用限制按原结论继承。

开始：`2026-10-04T04:29:52+00:00`；结束：`2026-10-04T04:36:12.353136+00:00`；约`6.34`分钟。保守累计工具31次（10个functions.exec wrapper、21个nested工具）；普通消息3条（开场、一次进度、最终；无问题）。均在80次/90分钟/3条上限内。只新增本目录一个conclusion及三个日志，无额外审阅批次。

## 结论与必要证据

1. 新说明与实际实现一致：有`payload.row_layout`时，`blocks`/`facts`是原索引字符串键字典；按`source_order`逐个取`str(index)`的值，再按`columns`还原字段。有嵌套fact数组才按`fact_columns`还原。禁止字典顺序、字典键字符串排序和行位置冒充原索引；不存在旧错误名`row_layouts`。
2. 新增指定回归独立运行PASS（1项、0.102秒、exit0）。它验证当前原型产生的文字/事实字典及嵌套事实恢复等于原提供单元，并用字典先插入10、后插入2的例子验证按原序[2,10]读取。
3. 对保存完整Marriott Source只构造原审事实418所在的**同一个任务**。Source SHA为`5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b`。五个实际提供单元全部为字典/单数row_layout；独立依提示还原每一行、嵌套fact及原style字符串后，全部与原单元行数组精确相等。可见原索引分别从1753和0起，事实从1、229、429起；没有将局部行号替代原索引或丢失值。既有完整复原函数的五单元相等检查也通过，但它不替代这次独立行解码核对。
4. 独立六个解码专用对照覆盖[10,2]原序、异构行字段及空数组fallback、嵌套fact同构数组、异构fact仍保留字典、facts异构行fallback。经实际打包及JSON序列化后全部恢复原值；`row_layout`缺失时保留原对象数组。有row_layout但无fact_columns时fact仍为原字典。它们不构成业务或真实公司语义测试。
5. 实际SCAN wire中的system message逐字等于新prompt，user message逐对象等于实际payload；新prompt SHA为`bb99f904d3d5c5492b2ce094ec1e5a6e055d34883a3d9a8429f71d26723222f7`，与measured-plan绑定相同。独立测量请求`65df9b84471da47d41406b8d12feea9a6dcfa31ebd327bc90b585528a6dc9926`为549470字节、181819输入令牌、185915上下文令牌（含4096输出预留），fits=true；与保存该行逐字段相同。上限200000参考上下文、8388608请求字节，tokenizers0.22.2及固定DeepSeek参考格式身份保留。
6. 相同任务的FOLLOWUP只由保存fixture响应、context packet和trace重建wire，**未再运行上下文定位链**；新system message正确、独立measure对象与保存测量完整相等。请求`abdbbd1543a5be7443e670d0a815b15da9eed8a6f3353f9f4229c743cf87546f`为557934字节、184642输入/188738上下文令牌，fits=true。原packet/trace及fixture响应SHA不变。

## 资源差异和覆盖限制

保存的5个Marriott及38个JPM首轮行均改绑新请求SHA，责任分组不变，每行增加288请求字节和58参考输入/上下文令牌；保存最高值分别185915和186203，全部fits。本审仅独立重算上述一个Marriott任务，**没有重跑两家公司完整计划**。这些全计划数字仍为父测量证据。

FOLLOWUP相对旧保存测量增加288请求字节、51参考令牌。最初审阅探针错误假定它也应增加58，断言失败已在review.log保留；随后独立重建完整wire确认保存测量精确一致。FOLLOWUP还嵌入变化后的initial_request_sha256，不能仅用system prompt令牌差作加法；这不是产品失败或回避测量。

本结论只授该机械解码修复和必要离线资源绑定信用，不判断模型能否正确理解D03、4096实际输出能否完成全部责任、上下文是否充分、全公司结果、独立输入模型抽取、DeepSeek实际验收、真实控制器或运行机会。原审未覆盖项继续未覆盖；不授Review APPROVE、Result/Run、390坐标、调用许可或生产采纳。

`review.log`记录精确身份、测量差异与最终核对；`unit-test.log`保存指定独立回归命令和输出；`decoder-probes.log`保存实际单任务与fallback对照。Source只读；解码/测量探针禁止socket与子进程。无spawn、commit/push、tar、新模型答案、真实模型/SEC请求、账户或其他Issue现场操作；business_calls=0/0/0。工作树README和execution-state既有未提交修改仅观察，未消费为代码身份，也未改写。产品、原件、旧响应、原独审及父测量证据均未写入。
