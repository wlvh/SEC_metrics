# D01：收回无法精确表示的跨页合并

首轮补丁 `1457e99a` 的[限定独审](../collab-d01-source-successor-20261002/independent-review-1457e99/conclusion.md)是 **NEEDS_FIX**：两个风险标题之间只有一个数字块时，复制来的跨页规则会把它们误合为一条；其展示文字也无法由当前 `TEXT_V1` 的单段原始字节跨度逐字表达。原审阅失败结论与反例保留，不改写为通过。

本增量只修改 D01 显式来源后继 `d01_emphasis_source.py`：不再拼合跨页标题。对于已经有确切来源结构证据的“页码—带链接的 Table of Contents—小写续句”布局，在目前单跨度合同下以 `D01_MULTISPAN_HEADING_UNSUPPORTED` 拒绝形成候选；仅有一个数字块时，两条原始标题保持分开，不制造合并标题。今后若确需接受跨页标题，应在后继记录中为两段原文分别定位并审阅，不能把夹着页码和目录的总跨度当作逐字标题。

本次仍限当前 #28 十家保存的年报。`current-ten.json`在新代码下重建十家公司候选，十个候选哈希均与修前已保存对照一致，说明已核对的 Marriott 四条下划线标题和 Paramount 完整 `U.S.` 标题未回退，也没有把其余八家当前来源的标题集改动。`tests/vnext/test_d01_emphasis_successor.py`同时覆盖页码加目录的明确未支持路径、独审的“只有数字块”误合反例，以及旧正向/来源篡改/默认路径。此项没有声称识别所有可能分页布局，也不授予两家新私有结果390或生产信用。

V13/V14及三份接线收据只按新增这一个执行文件重新绑定，闭包分别为 `sha256:306300d4…`、`sha256:3112b476…`；冻结V12、旧Run、旧Result、原账本、#47工作树均不改。受影响的新绑定下，Paramount私有正常更新为 `CANDIDATE_READY`、重复为 `NO_SOURCE_CONTENT_CHANGE`，独立进程冷读一致；测试5项、fast145/145通过。对精确补丁`865d8220`的[限定增量独审](independent-review-865d822/conclusion.md)为`PASS_LIMITED`，原首审`NEEDS_FIX`仍保留。真实调用0/0/0；#28旧可信统计的12坐标/18精确Result扣留不变。新head主CI以实际结果登记。
