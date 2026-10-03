# 2c4d236 历史分片回修限定独立审阅

受审提交 `2c4d2361280ed0a18f293007aefa0ca55018c843`，直接前驱 `46912cec61e981fc89750db27447710dba952aa2`。只审 C04 四形式后继的历史分片日期核对、年度事件读取闭合，以及修后绑定和证据的追加性。结论：**PASS_WITH_BOUNDS；原审阅指出的已加载分片错误接受路径已关闭，未发现本补丁范围内的新阻断。** `independent-review/conclusion.md` 对旧 SHA 的 **NEEDS_FIX** 保持原义；本结论不追认旧 SHA，也不是全 C04、全 PR 或生产验收。

## 修补判断

- `c04_registration_successor.py:63-68, 101-106` 在形成年度事件前，把每份已加载历史分片的四形式原标签行交给冻结的 `history_body_alignment`。它按每行实际 `filingDate` 核对索引 `filingFrom/filingTo`，矛盾即抛出 `C04_REGISTRATION_HISTORY_BODY_ALIGNMENT_CONFLICT`。因此旧读取器过滤 `8-K12B` 后看不到的矛盾，不能再进入 C04 的 0 判定。
- `c04_registration_successor.py:118-174` 对索引日期与本年度重叠的分片读取事件正文，并将逐项读取的 accession 与已加载元数据生成的年度 events 集合做相等检查。重复或遗漏均失败；对于已加载且日期一致的分片，年度事件不再能因索引过滤而静默消失。
- `test_c04_registration_successor.py:47` 的反例使 2025 年 `8-K12B` 落在索引宣称的 2024 年分片中：旧 `_filings` 看不到该行，新检查拒绝；把索引修成 2025 年后接受。默认 Marriott 两形式路径和显式后继仍在同一指定短测中通过。本人运行 `PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_c04_registration_successor -v`，**3/3 OK**。反例只执行 helper，未构造审计师同名的完整原生 Run；源码调用顺序证明拒绝发生在数值判定之前。

## 保存证据与身份

只读加载当前 V13/V14 Requirement 得到闭包 `sha256:2620e1c13900bdfd7bb501b7a3ff9c2aece37ec25cb22a03d9a78e8d7872f300` / `sha256:2ac87f016ea8f356298cc206ddfb9f71fca43adbdd9956d80b9b5a16bd7f9c1f`；V13/V14 基线均绑定实际新模块字节。V14 执行权限哈希为 `sha256:f17a202a240d606ccc405e4ab1b4a63976cba40992fd868546055d5c42483bb2`，只读 `validate_execution_authority` 与 provider `validate_wiring_receipt` 通过；新 provider/SEC 收据各 49/14 个证据哈希逐项匹配。两项接线测试的通过和零新调用仅取自保存日志，本次未重跑约百秒测试。

新隔离运行根 `/private/tmp/issue28-c04-four-form-20260926-03` 仍在。其安装模块哈希与当前源码一致；Run manifest 的 ID 与 `summary-shard-repair.json` 一致；records 有六份事件的 primary/header 引用、22 条 Item claim、零条 Item 4.01，唯一 C04 Result 为 `null / C04_COMPARABLE_AUDITOR_FACTS_MISSING`。两份公开行的字节哈希与新摘要一致。新摘要与运行根摘要仅差冷读成功后的 `cold_read` 字段。新旧 Result ID 和公开行哈希相同，Run ID 不同；旧 `summary.json`、`native-repair.log`、`cold.log` 及旧 provider/SEC 收据相对前驱未改。保存的 `cold-shard-repair.log` 报安装副本冷读成功，本次没有重跑该进程。

修后材料以新文件、新运行根追加，旧失败审阅与旧运行证据均保留。需要精确表述的是：**新收据不是前一份 C04 收据 evidence 字典的严格超集**；它以修后接线、原生和冷读日志替换对应的旧 C04 日志引用，旧收据和日志文件仍独立保留。当前收据自身的全部引用已核哈希，未发现无效指针。

## 未覆盖边界

本修补只证明**已加载**历史分片的索引与四形式正文一致，以及这些已加载元数据中的年度事件都被读取。若索引错误使整份历史分片在旧基线准备阶段未被加载，本次检查无法看见其正文；这属于更宽的来源完整性边界，不能由当前六份 Paramount 正例推断已解决。Paramount 保存原件仍缺同 CIK 前期可比年报，故本次 `WITHHELD/null` 不证明可给 0。没有重跑长原件链、独立冷读、provider/SEC 接线测试或真实请求；没有审全 PR、#47/PR52、生产采纳或正式发布。

实际工具调用：16 次顶层 `functions.exec`，内部 38 次 `exec_command` 与 1 次 `apply_patch`；无其他工具调用。仅新增本 `conclusion.md`。
