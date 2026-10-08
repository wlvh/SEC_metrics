# 4b16b4d 原件重开与包装接缝：限定独立审阅

**结论：PASS，仅本次新入口及恢复旧默认的接缝。** 本次实际执行指定23项短测试及默认/保存验证，另独立检查确切原件引用、数据/程序根、检查后字节变化、保存记录和Result保持。限定范围未发现需修复的新增问题；不是完整B06、公司Run或生产接受。

## 固定版本和范围

- patch：`4b16b4d8513be47d9b108da5cd44205f07073e4c`；base：`adc9c85d3b1713fd198f630e8725d61082e74dd7`。开工实际HEAD：`41bb544fc9800ed4e686f49b41338efa9e36cf0e`。patch至HEAD只有四项证据归档变化，源码/测试均与patch Git字节相同。
- 仅审 `ordinary_reported_lease_scope.py`、`test_reported_lease_successor.py` 和 `ordinary_special_debt_scope.py` 恢复main8588的接缝。读取旧native、路径resolver、SourceReference身份和B06准备函数作为调用上下文；没有重审未变单位、QName、行自身金额算法或完整B06。
- 实际字节核验：旧 `ordinary_special_debt_scope.py` 整文件等于main `8588ccbbb1c91d81e0fb1a89dff3575214282549`；关系解析器及18项旧测试等于 `930a3df29df8dbc8cd519044a23aeb682c09f80c`。继承930的限定PASS；旧4b接续因累计时间停止的NOT_COMPLETED原样保留，没有替它追认动态PASS。见 `byte-verification.log`。
- 按委托只读README末段、successor父方23测试日志及两个JSON。它们用于核对预期，本结论的动态证据来自本次独立执行，未直接把父方日志登记为本代理PASS。

## 接缝判断

新公开prepare入口先复用原partial case，然后从该case各reported component的SourceReference中确定primary/XML唯一来源身份。SourceReference id在原生成器中由原件SHA、公司、URL、申报、文件及角色计算；包装没有创建替代引用。source_proofs必须同时匹配原URL、申报号和SHA，并只允许一个不同的相对路径。同一路径的重复证明合并；两个不同路径即使字节一样也拒绝，不替程序猜选原件。

原件路径通过既有resolver在传入的数据根读取；工业关系重算前，旧native再检查重开的字节SHA及申报身份，并重建主体/期间。本次独立探针分别改变primary及XML内存字节，均以`B06_SPECIAL_SCOPE_ORIGINAL_BINDING_CHANGED`拒绝；错误证明SHA、URL、申报均以`RELATION_ORIGINAL_PROOF_NOT_UNIQUE:primary`拒绝。单元测试还实际覆盖相同路径重复证明和两个不同路径。没有写回原件或读取网络。

实际Ford来源为同一申报`0000037996-26-000015`：

- primary：SEC `f-20251231.htm`，SHA `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`。
- XML：SEC `f-20251231_htm.xml`，SHA `35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe`。

数据根实际为`/Users/lyuhongwang/Developer/SEC_metrics`；程序根实际为`/Users/lyuhongwang/.codex/worktrees/issue28-b06-relations/SEC_metrics`。新处理文件SHA来自程序根ROOT，重开的两原件来自数据根的已保存request_attempts路径，未误用工作树数据。完整URL及路径在`source-and-case-invariants.log`。

包装只更换selection/input_binding内的scope_source及明确debug字段。原case对象未被修改，所有其余顶层字段、原始绑定字段、SourceReference/证明/准入/Spec/期间/expected records/Result/Trace保持相等。新scope body经过既有JSON规范化后重新计算scope_source_id，selection与input_binding引用的scope相等；独立重算的新case与指定脚本保存后读取的整个对象相同。

银行分支只追加`NOT_APPLICABLE_TO_BANK_SCOPE`，不对重开的银行原件计算新关系；其事实和Result仍来自已核验的继承case。23项测试中的银行控制确认没有租赁包含结论、完整性或比值提升。本次检查后字节变化的动态结论限定到确实重用原件计算关系的工业分支，不扩成银行额外原件重算信用。

## 实际执行结果

1. 指定combined unittest：**23/23通过，0.082秒，returncode0，零失败/错误/skip**；进程墙钟0.504523584秒。见`small-tests.log`。18项旧解析器用例随指定小套件运行，未扩大独审范围。
2. 指定`verify_default_and_persistence.py --source-root ...`：**returncode0，11.749576958秒**。默认整个case等于main8588；新case JSON保存/读回相等，2396080字节；新case id为`sha256:99e1ab5cfa317ba1ab9b93f52f703478f9a6b7365d28404fe2133f84d3bd0d45`。见`default-and-persistence.log`。
3. 独立新接缝探针：**returncode0，6.945345542秒**。复用一次实际继承case后，通过新公开prepare入口重开原件，检查整对象保存相等、旧case不变、处理根及五项内存负例。见`source-and-case-invariants.log`。没有重跑四个保存原件单位控制或旧长链。

Result身份仍为`sha256:3cfdb4866a546c8ff41a65bfa14463e0b1717f54a946d417a245144b14cea07a`，Trace身份仍为`sha256:c2f8c972b7916d87a175cab121c27ee35647ac62a37da5650b16d9ce8ebb6d2a`。工业租赁包含关系仅补来源body，追加额0、报告小计21919000000；完整性仍false，B06仍**WITHHELD/value=null**。工业权益及完整债务集合没有由此建立，没有新Run、公司CSV、合并、采纳或active信用。

## 资源和操作记录

本次新spawn UTC `2026-10-08T13:28:09Z`，首次实际clock `13:28:50Z`；截止 `14:58:09Z`。结论写入前实际clock为`2026-10-08 13:33:46 UTC`；未知空闲没有从本次累计时间扣除。最终时钟、工具累计及源码/原件终检另记`final-verification.log`和`resource-final.log`。

指定验证各一次；来源读取及负例均离线。新增provider/paid/SEC/账户请求各0，无#47工作树/账本/运行根操作，无spawn、commit/push或tar，无源码/测试/旧资料/原件编辑。仅在本新目录写一个conclusion及日志；指定保存脚本按原实现使用/private/tmp的JSON。一次rg调用带入两个不存在的辅助文件路径并返回2，随后改用实际存在的函数文件读取；这是只读检索设置错误，不是业务测试失败。

