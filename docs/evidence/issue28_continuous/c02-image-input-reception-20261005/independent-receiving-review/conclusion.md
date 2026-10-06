# 限定接收独审结论

结论：PASS_SCOPED_RECEIVING。在本次指定范围内，未发现阻断实际接收的源码或输入表示缺陷。

审阅绑定为补丁 `9ac5a02da789ad81b6c94af90477935854e0c4df` 相对基线 `9099e273a78e0719775698f1c3829f8f70444193`，仅覆盖本证据目录的九个提交文件。该提交另有 `execution-state.json` 变化，且开工时该文件已有工作区修改；它不在本次审阅范围，本审阅未修改它。提供方只通过已存在的固定 Git 对象读取，没有访问其工作树、PR 或状态。

`prepare_image_markup.py` 与提供方 `e6b2bb8e2575b665a8e02290935953e632216f2f` 中 `docs/evidence/issue47_history/jpm-member-symbol-2026-10-05/prepare_image_markup.py` 逐字节相等，SHA256 为 `a1ecc8f1d4785869e55cc8c28b7833a1bad69ccf0fb73513e4d66a4b69361837`。接收目录保持相同深度，实际使用本方的表格解析器和本方原件。原 ISSUE47 记录类型只是保留的提供方来源标记，不能升级为历史来源关系或验收信用。

自己的原件与仓库已保存来源资产逐字节一致：JPM DEF14A，2026-04-06，accession `0000019617-26-000096`，原件 SHA256 `bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476`。旧输入目录的所有已登记 artifact hashes 均匹配。基线、补丁和当前工作区中的旧 mapper、输入生成器、参考及旧回答字节均相同。

指定 `check_actual.py` 已重跑并通过。它核对旧消息内容中的完整 4,106 块与 409 表数据包、请求参数和原任务未变，604 个原始 img 节点的属性、字节范围和 sidecar 原标签相等，以及原有十四处来源引用的位置。十四处记录只用于定位原件，不作为独立业务答案。UTF-8、重复图片、自闭合、表外和 rowspan 正例，以及表格篡改和重复属性拒绝检查通过。原接收测试的 colspan=1 误设已正确替换为原件实际跨度；没有为通过测试改动原件或提供方脚本。

另用不依赖 `_AllTablesParser` 的 stdlib HTMLParser 和独立行列占位计算，重新核对了全部 604 处的属性、精确字节跨度、表编号、单元格起点、rowspan 和 colspan，全部与实际 sidecar 一致。七个无单元格节点全部位于表外。随后在禁网络、禁子进程的上下文重建实际新请求，四份重建输出与已保存实际文件逐字节相等；临时重建目录已由 TemporaryDirectory 退出清理，仅保存必要日志。

实际新请求身份为 `18abb36b70d36cb95052d564f7c3fd7e0373f46ccb612df934841c5926b48f6b`，不能替代旧 `5397bcbfae90ffef4ead2f10ed27df8113d9250ea6f8f2668f17cb85951e9b1e`。旧 mapper 用当前本方来源重新准备输入后，按原完整请求相等检查拒绝新身份，错误为 `C02_TABLE_MODEL_REQUEST_OR_RESOURCE_CHANGED`；响应解析器没有被调用。检查只使用程序占位字节，未复用旧模型回答或创建新的模型回答、原生对象、Result 或 Run。

实际输入的固定本地 tokenizer 计量为 161,921 input tokens，加 4,096 输出预留共 166,017，低于 200,000；payload 为 603,523 bytes，低于 8,388,608。重建与保存计量完全相等。这是离线资源估计，不是托管模型用量、价格或费用凭证。

提供给模型的是全部解析属性及位置的元组表示；完整原标签的拼写、引用符号和原始字节仅保留在原件与主机 sidecar。未提供、读取或解释像素。新增说明明确保留 generic filename/alt、空白单元格不能证明资格、非成员或零的边界。它没有注入预期业务答案。

本结论不覆盖 raw-tags 可选分支的其他材料、任意公司/披露结构、图片像素的业务含义、公司完整性、模型抽取准确率、尚未实现的新身份处理及保存/读取接线、DeepSeek 真实验证或生产信用。当前旧 mapper 的拒绝边界是已证实的必要限制；后续新处理路线应保存自己的实际身份和完整新增 metadata/context，不应删掉旧身份相等检查。没有 provider、SEC 或网络请求，没有账本读取或写入，没有 commit/push，没有嵌套代理。未运行已通过长链或全 suite。

证据日志：`fixed-identity-inspection.log`、`specified-check.log`、`actual-rebuild-and-boundary.log`、`final-preservation-check.log`。`initial-harness-failure.log` 保留独立测试夹具在 import ssl 前替换 socket 类型引起的初始化失败；仅调整夹具导入顺序后完成检查，审阅源码未改动。
