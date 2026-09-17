# 短整数来源单元索引与旧成功保留：限定独立审阅

审阅范围是根执行者实现的`native_unit_index.py`、D04/B13的indexed验证入口、`SemanticRequest.validate`新准入、自动保留原成功选择器和对应request_digest/CLI差异。文件SHA见`scope-files.json`。不独立批准审阅者自己实施的三个混合消费修改，不覆盖旧6e5 D03受限任务、全PR或真实语义资格。

## 发现及修复

**曾发现一项阻断，现已复验修复。**初版request_digest把整个`indexed_unit_contract`纳入语义去重，其中`base_request_id`重新引入了机械source/request身份。只改变source_id并规范重算request_id、保持正文/提示/输出语义相同，BASE的语义digest仍相同，INDEXED却不同，可能让纯身份变化绕过“不重抽同语义请求”的限制。

根执行者现仅从语义digest中的indexed元数据排除`base_request_id`；原完整HTTP、request_id、plan和receipt继续绑定该字段。独立持久回归`tests/vnext/test_native_unit_index.py`修前3项中1项失败，修后3项全部通过（0.022秒）：机械身份变化不允许重抽，实际来源payload、提示或输出合同变化仍产生不同语义身份，BASE与INDEXED本身也保持不同合同身份。修前/修后日志均保留。

当前审阅范围未发现其他未处理阻断。

## 身份恢复与原业务检查

38个独立合成反例/正例跨D04和B13实际验证器通过：

- `restore_base_request(upgrade_request(base))`完整等于原请求，原BASE字节不变。
- 索引必须是真正整数，0到n−1各出现一次；遗漏、重复、布尔、字符串、小数、负数和越界均拒绝。
- 响应数组可以乱序，程序按索引恢复原来源顺序。它不根据相似字符串猜测hash，不推测丢失单元。
- 模型额外回request_id或unit_id hash会被拒绝；新格式只接受规定字段。
- 跨单元引用仍由原源引用校验拒绝；D04把明确当前疑虑改成条件句、B13把税收抵免改成产能，递归回原验证器后仍拒绝。恢复身份没有替代原分类/来源检查。
- 重签后的错版本、错base_request_id、缩短必评清单、扩大索引范围、缩小schema计数、调换请求源单元等均拒绝。
- checked结果保存真正indexed请求ID及原始响应对象；复原的BASE格式只用于已有验证逻辑，原HTTP响应字节没有被写回替换。

首个审阅工具曾用仓库规范JSON写入小数，规范写入器先拒绝而未抵达被测入口；改用真实provider可返回的普通JSON字节后，38项全部抵达预期检查。工具初错单列，不作为产品反例通过。

## 原成功选择与准入

另有7个选择/准入情景通过：

1. 没有已成功请求时，各原分组选择其确切INDEXED版本。
2. 已成功BASE和已成功INDEXED都保持各自原请求；失败BASE不获取成功信用。
3. 同一原分组出现两个成功版本时拒绝，不任意挑选。
4. 已成功记录的当前重验失败直接停止选择，不换新请求抽样。
5. 其他source的成功不会被本任务借用。
6. 真正`SemanticRequest.validate`成员检查接受由该完整source原分组精确升级的请求。
7. 跨source的indexed请求被`CONTINUOUS_REQUEST_NOT_IN_SOURCE`拒绝。

上述选择器试验使用真实类型的本地recorded账本和实际选择逻辑，但账本snapshot、归档runtime重验及成员探针的来源准入/进程能力/policy读取是明确test doubles。原请求文件前后不变；没有把模拟SUCCEEDED当成真实信用。真实70的原runtime/收据与当前来源复验由根任务的`d04-indexed-unit-response/ford-retention.json`单列，本报告不冒充重新执行该长链。

本审阅没有更改运行代码、旧70/71请求/响应/终态或固定总账。新增provider/paid/SEC为0/0/0。模型在此新格式下的实际正确性、完整公司—指标结果、统一更新/发布和生产确认仍需相应证据。
