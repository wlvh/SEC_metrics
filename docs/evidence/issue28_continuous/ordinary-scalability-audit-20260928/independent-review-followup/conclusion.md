# `dea6e4a` 限定增量独立审阅

对象：`dea6e4a07ea6200b192571a3f81f1710c6b53587` 相对 `652a2505881827dabe5eb6267efaf61f0fe66080`。继承前轮 [NEEDS_FIX 与两项 P2](../independent-review/conclusion.md)，只审本轮指定增量。结论：**PASS_WITH_BOUNDS**。在 V14 当前私有普通发布路径，两条旧反例均不能再借邻近语法漏报；八项豁免只对本轮审过的源文件精确字节有效。未发现本增量的新阻断问题。这不是完整私有发布、真实新财报更新或生产采纳结论。

## 旧 P2 与豁免边界

- 用前轮两个原始反例分别建立临时 Python 树，不带豁免政策：`{'NATIVE_FACT':'F'}['NATIVE_FACT']` 用于 `row['ticker']` 比较，返回 `ticker/F` 违规；`user_instruction_date` 字典值用于 `row['period_end']` 比较，返回 `fixed_fiscal_date/2026-09-23` 违规。真实公司名、ticker、期间同时出现的独立反例也分别被报出。原始结果见 [counterexamples.log](counterexamples.log)。
- 新政策八行的文件 SHA-256、大小、行号和 AST 字面值均逐项核对。五处 `F` 在 B13 来源引用前缀构造／映射，另有审计器自身的标记字典；两处日期在用户授权转录的 `delegation_source.user_instruction_date` 等值核对中。它们不是当前财务结果的公司选择或财年判断。`_approved_exemptions()` 先核对整个源文件哈希与大小，扫描时还要同时匹配文件、行、字面值、违规类型和局部语法，并要求全部已批准项确实被用到。修改获批源文件的短测会在扫描前报 `ORDINARY_SCALABILITY_APPROVED_SOURCE_CHANGED`。因此原先宽泛的语法排除，在本轮已变为当前精确来源的有限豁免。
- 政策本身不是任意运行根的独立信任凭据。私有发布的 `_implementation()` 把政策、审计器及发布器三者同 V14 执行清单的实际文件字节核对；`stage()` 和回读重算都调用 `_compose()` 中的扫描。直接对任意自备 `runtime_root` 调用扫描器，只能得到该根自身的检查结果，不能据此声称获得 V14 发布许可。以后改动任一获豁免文件或政策，都需要重新审阅、更新 V14 绑定和接线；旧批准不自动延续。

## 绑定、兼容与验证

- 当前 V14 闭包为 `sha256:1876c014183369af05b19a2d7e0e8c08c92d2e0b70388084250fedd5eb031c98`，执行绑定为 `sha256:a7033ebf1c2599554bc19546c8947a8e7a54f52643fc4f7990e3610423c87468`。实际加载与私有发布 `_implementation()` 核对通过，当前扫描为零违规。provider 离线收据经现有验证器通过；provider／SEC／ordinary-refresh 三份收据所列 95／50／50 项证据文件 SHA 均匹配。摘要见 [binding.log](binding.log)。这只证明当前文件与离线接线可读，不证明后继真实请求或完整发布成功。
- V13 `requirements/issue_28_v13/baseline_manifest.json` 两端 Git blob 同为 `13632f33c6b09d168c95b7983e422a993e37d868`；`scripts/vnext/annual_publication.py`、`scripts/sec_pipeline.py`、公司登记及旧接线实现未在该提交差异中改动。旧 V13 历史语义和原有年度扫描器未被本轮重写。
- 指定短测 **11 项通过，10.599 秒**，包括两项旧反例、已批准源文件变动拒绝、真实身份／期间拒绝及私有发布边界；原始输出见 [directed.log](directed.log)。未运行长材料、全 fast、完整私有 `stage`／回读、真实 provider／SEC 调用，也未审查或操作 #47／PR52。未打包、commit 或 push。

本次实际底层工具调用：**38 次**。仅新增本目录的结论与三份短日志；仓库已有的 `docs/evidence/issue28_continuous/execution-state.json` 工作树改动未触碰。
