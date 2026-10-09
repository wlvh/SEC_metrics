# C02新表格输入接收限定差异独审

结论：**PASS_LIMITED_INPUT_RECEPTION**。在指定输入表示与显式普通来源入口范围内，未发现需要阻断接收的 P1/P2 问题。该结论只证明受审代码将认证的保存原件转为完整文字块和展开文字/表头格，并保留资源不足及未解释图像的限制；不授模型语义、原生 Result/Run、真实执行、指标完整验收或生产信用。

## 固定身份与范围

- Base：`05d11df29bb5a09e4da45629e024d1fd554c7b8e`。
- 审阅提交：`51ccf5886913bca1a5fbb1ea02f5e25fe80665b8`；开始及结束时的 HEAD 均为此提交；四个范围文件工作树字节与此提交逐一相等。
- 提供方：`417ccfb788f39f53e5ef2b2d825a3fa46efc11bf:tools/prepare_c02_table_context.py`。只用 `git show` 读取固定源码，没有 checkout、修改其分支/工作树、运行其历史 CLI 或操作其账本。
- 受审文件：`scripts/vnext/c02_table_context_417ccfb7.py`、`scripts/vnext/c02_table_development_input.py`、`tests/vnext/test_c02_table_development_input.py`，及 `tools/run_fast_tests_v2.py` 唯一新增的末尾 selector。
- 此次直接审阅依据：实时 Issue #28（含第5.8节）及指定补丁、其调用依赖和实际源字节；没有沿用执行者的通过结论。

## 检查与证据

1. **来源认证通向实际输入。** 普通入口先走原 `prepare_normal_business_text_input(C02)`：固定保存来源基线、请求/头文件、元数据选择、主体/期间及原件字节认证；之后由 `governance_source_document` 再核原始字节散列、实际 SEC 地址、主体与 DEI 表单。该新入口没有跳到历史 selector 或用旧答案补输入。完整源状态不足、来源准备受阻和治理源不唯一均拒绝。`development_request` 是低层表示函数，其文档明确要求调用者另外认证原件；单独调用它不能获得源真实性信用。
2. **完整表示保留。** 所有文字块按 B 索引保存，重复文字不折叠其块编号；所有表按原件顺序进入，表格有无任务关系不影响保留。编码前使用既有可逆完整网格检查，之后逐块、逐表、逐展开坐标比较文字/表头。行列错置、删除块/表、重叠跨度、错误父原件均由指定测试覆盖。空白且非表头的原始跨度、HTML实体拼写、样式、图像不属于新模型表示保留承诺；完整原件及原网格仍在本地返回材料中。
3. **实际依赖和固定接收。** 从真正的普通入口捕获72个已导入本仓库 Python 文件；全部运行字节与受审 head 对齐，其中70个既有依赖与 base 字节不变。提供方五个纯函数和 FORMAT 的六个完整语句源码片段逐字节相同；接收文件在 FORMAT 之后多一个 LF 分隔符，不改变函数/字符串内容。接收范围散列为 `5ac1d26dad3d9f5def9f1155c222828502d27d6ab117ccef89f1433b2d1f9a1d`。未接收历史准备/CLI/抽取/采纳。V13/V14既有 Requirement JSON 不含新路径，旧运行入口不因这次输入开发自动获得新请求绑定。
4. **资源限制。** 目标输入使用 `tokenizers==0.22.2` 和经散列核实的冻结资源、200000上下文及4096输出保留。实际225k附近的超限输入返回 `fits=false`，保留完整任务和表示；本次实际为224584上下文令牌。超过8MiB请求、错误 tokenizer 版本、越限表格列跨度分别明确拒绝。没有裁文字、忽略部分表格、提高限制或发送请求。GitHub fast job已安装同一冻结 tokenizer；新增 selector 是唯一调度变化，未删改原 selector。

## 禁网实际重建

直接从本方原仓库保存来源调用新 `prepare_ordinary_table_development_input`，未运行 `check_current_input.py` 或旧长链。macOS sandbox 禁止网络，Python审阅钩子另外禁止 socket、子进程及写入审阅目录之外的文件。

- 公司：JPMorgan Chase；DEF 14A，2026-04-06，accession `0000019617-26-000096`。
- 原件 SHA256：`bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476`。
- 原生保存来源绑定：`sha256:41d151d6be449e17fa8b082788e8114b1a693cae15eaa24657d5dccdbc6fb517`。
- 4106文字块的原字节跨度散列全部核对；409表、38409展开格的文字/表头全部相等。另以独立 HTMLParser 数到409个原始表起始标签。
- 重建4.837秒；9个完整材料字节分别与私有保存材料相等。依赖散列来自本次实际导入，非读取执行者依赖清单后默认接受。
- 请求 SHA256：`5397bcbfae90ffef4ead2f10ed27df8113d9250ea6f8f2668f17cb85951e9b1e`；530507字节；129805输入令牌，加4096为133901，`fits=true`。均为离线参考估算，不是 hosted usage 或费用证明。
- 年度容器与董事会测量时点在提示中明确分开；没有将2026代理材料自动说成2025-12-31董事会快照。

## 图像限制仍成立

独立读取本次原件第116表，确认其中14个 `<img>`，图像源为 `jpm-20260402_g49.jpg`。新表示保留相关文字、列位置及 C/A/B 字母，但这些图像没有进入文字/表头格并被解释。对应空字符串不能证明非成员，不能以文字格重放相等推导整份财报关系覆盖完整。FORMAT 明确声明未解释 source images，并要求无支撑关系保留未决。这个限制阻止完整语义信用，未构成对本次明确的“文字/表头输入接收”范围的错误接受。未对图像像素作成员语义判断，也未用第22表的文字佐证推成全面覆盖。

## 测试结果与未覆盖

指定命令在禁网 sandbox 中执行：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts TMPDIR=<本审阅目录>/tmp sandbox-exec -p '(version 1)(allow default)(deny network*)' /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_c02_table_development_input tests.vnext.test_compact_table_payload -v
```

12项全部通过，7.044秒。另5项有界边界检查通过：真实上下文超限保留、8MiB超限拒绝、tokenizer版本不适用拒绝、解析资源越限拒绝、实际原件字节篡改拒绝。它们不产生模型回答或业务 Result。

未覆盖：完整 C02 抽取及漏选/误纳语义、图像解释、所有公司/年度版式、实际 DeepSeek一致性、原生 Run/Review/Result整条链、真实调用/更新/统一390验收、该新提交完整CI终态、正式采纳/发布及全指标独审。未运行旧长链；没有SEC/provider业务调用、提交/推送或生产写入。

审阅辅助脚本有3次自身错误，分别为提前替换socket类使ssl导入失败、独立HTMLParser辅助方法与其内部offset属性同名、源码范围比较误包含文件结尾的一个额外LF。失败日志保留；修正仅审阅辅助脚本，未改被审源码，随后上述实际重建、版本核对及边界检查完成。不能把这些辅助错误写成产品测试失败或隐去后称首次通过。

## 记录与硬边界

- 开始时间（首次工具记录，UTC）：2026-10-04T09:22:55Z。
- 完成时间（最终核对和结论写入，UTC）：2026-10-04T09:33:46Z。
- 实际工具量：15个 `functions.exec` wrapper + 15个嵌套 `exec_command` = **30次**，按保守计数；没有其它工具或子代理。
- 普通消息：**3条**，开头、一次进度及最终报告；0问题。
- 硬上限：80工具、90分钟、3消息，均未超。
- 仅写本目录的一份 `conclusion.md` 与日志；空的测试临时目录已移除。没有 tar.xz。原工作树 `execution-state.json` 在开始时已修改，未触碰；最终状态只另外出现本审阅目录。
- 本次业务调用：provider/paid/SEC **0/0/0**；模型回答、原生结果和生产权限均为False。

日志：`targeted-tests.log`、`actual-rebuild.log`、`version-and-dependencies.log`、`additional-boundary-probes.log`；辅助错误日志分别为 `harness-init-failure.log`、`harness-table-parser-failure.log`、`helper-range-comparison-failure.log`。
