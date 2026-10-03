# 31beeab D01 页眉修复限定独审

**结论：限定范围通过；未发现新增 P1/P2。** 本结论只接受本方显式 V3 规则接收、普通创建/原生重放的分派、版本绑定、旧结果扣留及相应局部开发验收。此为同族子代理代码审阅，不冒充独立人工验收，不授新 Result 的390、完整业务或生产信用。

- 精确受审提交：`31beeab5486a30366afa395124c7ecbb492c93b8`；父：`9e37beb951903559782784b457f4d2a3e67342b8`。
- 固定提供方：`af29ab2f41f40a442c13a3453c97d2c476f3536b`；只读其 `pending-rule-changes/d01-running-header.patch`。提供方仍未正式应用的状态未改变，也未继承其验收。
- 起止 UTC：`2026-10-03T04:24:24.688166+00:00` → `2026-10-03T04:33:14.187197+00:00`。
- 工具39次：16次外层 `functions.exec`、21次 `exec_command`、2次 `write_stdin`。普通消息2条（开头说明与最终报告），问题0。未spawn、commit、push、业务/账户调用；新增provider/paid/SEC=`0/0/0`。写入仅此目录的结论和日志。

## 本次独立核验

1. 从旧普通Run所带原件直接读 SHA `4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23`、跨度`1691112:1691126`及分页/Item1B上下文。该行是独立页眉。旧 Result `994427388d20f9ee0aef09c080a0e1f5b8420fcb5f4fd276a6489734193c1242` 与原390索引身份、全文相同，确切扣留有依据；其他D01不因同名扣留。
2. 提供方的双部分标签替换与本方逐字相同；本方编译器仅准两个已知顶层函数，保持磁盘源码/已加载代码相符与每处替换恰好一次的守卫。V3相对固定父V2只有说明、策略名、选择器导入及两处推导调用的差异。冻结 `run_store.py/risk_signals.py/text_results.py` 和 `_binding()` 函数源码保持。旧D01两方法删去新增显式委托后，语法树与父版本相同。
3. 默认 `text_api('D01')` 仍为原API；新策略明确选V3，旧原生验证器收到显式V3时，Evidence和Result重放委托正确。新包装器用 `metrics/D01-header-v3`，其他指标保持委托与请求顺序。独立反例验证已有journal配置不能静默换策略、错误指标/错误类型被拒，带Parts词的真实标题及未支持的逗号/ampersand/句点写法保留。
4. 实际加载V13/V14、验证完整execution authority与全部new-rule hashes：V13闭包`d31a37a420b5a1e16b9d41de794388d283290a15636d83f27cf74863659f227a`，V14闭包`b71ab42d71daa5c50fe570627399b1a49be696bae27a85a3c7e460eb7a39a911`；父五文件、父闭包及依赖集合一致，旧Requirement目录无差异。
5. 真正安装路径为`/private/tmp/issue28-d01-running-header-v3-20261003-final/jpmorgan_chase/metrics/D01-header-v3/attempts/bb9e9ce65d9f4fdfa3547b885fcae875/data`。404个执行/规则文件与受审源码逐字相同，安装V13五文件一致，原件字节相同，保存绑定明确V3。实际新Result `f8da54962750aa727051d66ba699bae53afbf21e2ce19a51abd023666f683f89` 的56行恰为旧57行删去末页眉；保留56条Claim的文字、顺序、块、原始跨度与跨度SHA均相同。
6. 实际调用当前接线验证器得到`CONTINUOUS_OFFLINE_WIRING_MISSING_OR_CHANGED`，拒绝后原收据字节保持，SHA为`79185f6e09a9625f4f859b4b79c9d7d9a62a02e4e83763e96b10187e3c67d7bc`。登记为STALE拒绝是诚实状态；没有要求或发出未授权真实请求。原账本、来源log、active等10项当前SHA仍与材料保护记录相同。

## 实际短测及复用证据

亲自执行指定短测9/9、390读取短测19/19，加本次独立反例6/6，均通过。日志：`short-tests.log`、`current-view-tests.log`、`independent-counterexamples.log`。

151入口fast、十家源材料比较、180.243秒CLI、60.705秒同源重入、53.467秒安装冷读采用受审提交中的既有日志，未重跑长链。核验fast的151条return code均0，CLI保存成功候选、同源重入不新增Run，冷读为OPEN/VERIFIED_OPEN_PREVIEW。安装身份另亲自按上述404文件验证。十家比较仍属开发/回归语料，不能改称留出验证。

原V13政策镜像失败、V14规则集合失败、获取根旧政策拒绝、原生重放`D01_EMPHASIS_POLICY_INVALID`失败的日志均保留。当前修复使用新的私有journal，不把原失败改成成功。旧错误释放列表为空，固定提交声明新候选`current_390_credit=false`及`production_authorized=false`，尚不能以本审阅解除旧错误或替换正式current/active。

## 精确范围与停止条件

范围为所列D01页眉后继、D01显式委托、`normal_run_v3.py`、`ordinary_remaining_cases.py`、`ordinary_update_cycle.py`、新包装器、正常CLI、V2配置、V13/V14实际绑定、短测与本次缺陷映射。未重开旧D01标点/两标题修复或390产品scope审阅，未扩大通用解析器/共享重构，未操作#47/#54现场。

下一条真实调用前仍须完成受影响的最短禁网factory/controller接线并验证最终收据；这是保留的调用前置，不能改哈希追认。当前没有必要通过真实请求来证明本次离线页眉修复。

审阅时工作树已有执行状态修改；按精确提交读取其状态声明，未写该文件。更多证据见 `binding-and-installed-identity.log`、`source-and-evidence-read.log`、`peer-diff-and-exact-change.log`、`review-session.log`。
