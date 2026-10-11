# 限定独立审阅：reported consolidated revenue V2

结论：**REQUEST_CHANGES**。直接读取原件已经报告的总额、Macy FY2023 的实际原件和旧 V1 默认行为均得到限定验证；新增 V2 的可见日期检查仍有一项错误接受、一项错误拒绝，不能给该差异通过结论。

审阅 base：`209cdcdd48520d02eb8715a4118217a216262b8a`。审阅 patch：`331bffbb9baef1601b2b915f8b1518bb60b2a385`。三份目标文件均核对了 HEAD blob 与工作树逐字节一致。

范围仅为 `scripts/vnext/selected_reported_revenue_v2.py`、`selected_revenue_scope_v1.py::_statement_scope` 的显式 `adjacent_heading=False` 分支和 `tests/vnext/test_selected_reported_revenue_v2.py`。已审 peer `0c6cd6c53f555851f8e0f7e526c2d96f54d44df9` 的 `historical_fiscal_labels.py` 只核对所需依赖与调用接缝，不重新审核财政标签修补。该依赖逐字节相同，SHA256 为 `280c8dffebfdbd4a302e18270415fc2b6afb00d75a432dcce804b608dadedf4b`。

## [P2] 拆开的月日说明与年度列不核对，冲突仍获完整期间信用

位置：`scripts/vnext/selected_reported_revenue_v2.py:62–65`；相关新增正例 `tests/vnext/test_selected_reported_revenue_v2.py:50–56`。

`_column_period` 对独立 `2025` 列返回 `date=None`，把另一行 `Year Ended December 30,` 当作允许的描述文字。V2 只检查列年份和 `column.date`，随后 `_statement_scope` 又允许该月日说明，因此明确的可见期末冲突被略过。

有限复现使用现有 `originals()` 原样事实，只把可见 `Year Ended December 31,` 改成 `Year Ended December 30,`。native period 保持 `2025-01-01` 到 `2025-12-31`，结果仍为 `REPORTED_CONSOLIDATED_TOTAL`，`complete_scope_proven=True`。这不依赖改金额、概念、公司、原生上下文或 label record。

新增 fiscal 正例亦保留 `Year Ended December 31,` 和年度列 `2023`，却把 native period 改成 `2023-01-29` 到 `2024-02-03`，仍通过。这应是冲突反例；Macy 的实际原件可以继续用纯 fiscal 列，没有必要以该相互矛盾的构造作为正例。

应在这个来源函数的有限范围内核对与当前列关联的明确月日/日期描述；纯 fiscal-year 列仍可由完整 native period 证明。不能用匹配的 native context 消除已经出现的可见期末矛盾。无需新增通用财政语言平台。

## [P2] 正确完整日期也被误报为日期冲突

位置：`scripts/vnext/selected_reported_revenue_v2.py:64`。

`_column_period` 对 `December 31, 2025` 返回 `datetime.date(2025,12,31)`；本行直接与字符串 `period['period_end']='2025-12-31'` 比较，类型不同导致真实相等日期必然不匹配。

有限复现把现有 fixture 的年度列 `2025` 改成完全一致的 `December 31, 2025`，结果为 `SELECTED_REPORTED_REVENUE_VISIBLE_DATE_CONFLICT`。改成真正错误的 `December 30, 2025` 也得同样错误，所以已有错误日期测试无法检出该误拦截。应在 V2 局部统一日期类型，并覆盖正确和错误完整日期各一个例子；若完整日期有明确的支持边界，应据实标为未支持，而不是宣称与实际日期冲突。后续还需确认匹配日期能通过 V2 的局部标题/表头检查，不能只修早期比较后就声称正向完成。

## 已完成的有限验证

- 指定命令 `python3 tests/required_unittests.py tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1`：29 项，0 failure、0 error、0 skip，0.246 秒。测试通过不覆盖上述两个日期问题。
- 实际源 driver 重新读取固定 Macy 原件并验证 SHA256 `50ea8e3119bf4e07e0ee54e29e2f844289afc6197d584594e6f8ed4325282b29`；报告总额为 `23866000000` USD，完整 native period 为 `2023-01-29` 到 `2024-02-03`，fiscal column 为 2023。生成 scope 与原 `actual-source-final.json` 完全一致，约 1.19 秒。该结果取已经报告的 `us-gaap:Revenues` 总额，没有手加 NetSales 和 extension OtherRevenue，也没有把 extension 改为 approved concept。
- driver 原本会覆盖父 receipt。本次只在执行字符串中把唯一输出 sink 换成 `/dev/null`；driver/实现/测试均未改。父 receipt 的 SHA256 前后相同：`75967d328d96b25f711931e315789040fb6c745d171101487b058b49bf493a1d`。原件及 #47 树只读。
- 旧 V1 默认函数与 base 原代码分别对完整正例、没有全利润表的反例和零组件正例运行，结果字典含 scope hash 完全一致。23 项旧测试也全部通过。
- 阅读新增标题表分支：只取紧邻前表，拒绝其中已有原生数值事实；完整标题表网格文字与索引块文字必须吻合，索引块只允许原生公司名、合并利润表标题及明确单位。既有未知标题表、夹入段落、未覆盖 plain TD 外公司名、局部收入排除、单位冲突及 XML 总额冲突反例均实际通过。
- label record 接缝检查 primary SHA、主体、accession、实际起止日和 raw DEI year，并调用已审 peer 的 actual-definition-scope 检查及已有 fiscal selection。已有另原件 SHA、错误 selected year、条件性定义及完整错误日期反例实际通过。这是有限接缝验证，不重新给历史财政模块全审信用。

## 独立日志与边界

- `review-reportedtotal-331bffb-tests.log`：指定测试原始输出。
- `review-reportedtotal-331bffb-actual.log`：实际原件 driver、原 receipt 不变及 exact scope 比较。
- `review-reportedtotal-331bffb-probes.log`：两项日期发现及 baseline 的有限 in-memory 原始复现。
- `review-reportedtotal-331bffb-binding.log`：V1 默认结果对照、已审 peer 字节一致及审阅 HEAD/工作树校验。

只写入本 independent-review 目录的这一份 Markdown 与四份日志。未修改实现/测试，未 commit/push/spawn、访问网络/SEC/provider/账户、写入 #47 源/状态或覆盖父 receipt。未执行公司/Calculator/Run/保存读取大演练；本次仍是纯 source 审阅，没有新增业务、生产、采纳或完整公司接受信用。README 已明确这些边界。范围外事项保持未审阅，不推断其正确性。
