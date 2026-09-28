# `652a250` 限定独立代码审阅

审阅对象：`652a2505881827dabe5eb6267efaf61f0fe66080`，父提交 `070f1c4e`。结论：**NEEDS_FIX**。当前树的七条已知来源标记／授权日期误报确实消失，指定短测通过；但两项排除条件只检查邻近语法，不能证明字面值的业务用途。下述反例均是内存中的独立扫描复现，不声称当前代码已存在这些公司或期间特例。

## 发现

1. **P2｜来源标记字典可掩盖实际 Ford ticker 硬编码。** `scripts/vnext/ordinary_scalability_audit.py:33-36` 只要看到字典项 `{'NATIVE_FACT':'F'}` 就排除 `F`，不检查该字典如何使用。复现：

   ```python
   if row['ticker'] == {'NATIVE_FACT':'F'}['NATIVE_FACT']: pass
   ```

   `F` 是当前登记的 Ford ticker；原匹配器返回 `ticker` 违规，而 `successor_scalability_snapshot()` 对只含此代码的 Python 树返回 **0 行**。因此私有发布在 `ordinary_isolated_publication.py:198-201` 的扫描门会接受这一真实公司分支。应将豁免约束到实际的来源引用构造／使用，并加入“标记字典被用于 ticker 判断”的负例；单凭键名不能赋予豁免。

2. **P2｜授权日期排除可掩盖实际财年日期硬编码。** `scripts/vnext/ordinary_scalability_audit.py:64-72` 只要求外围任意相等比较中出现常量 `delegation_source`，并未核对比较对象确为授权来源字段。复现：

   ```python
   if row['period_end'] == {'user_instruction_date':'2026-09-23',
                            'delegation_source':'policy'}['user_instruction_date']: pass
   ```

   原匹配器返回 `fixed_fiscal_date` 违规；后继完整扫描返回 **0 行**。这里日期明确用于财年结束日比较，却因同一比较中出现授权字段名而被排除。应只识别实际 `delegation_source` 等值核对的字典值，并加入同字典／同一比较含财年用途的负例。

## 已核验边界

- `PYTHONPATH=scripts /private/tmp/issue28_py314_venv/bin/python -m unittest -v tests.vnext.test_ordinary_scalability_audit tests.vnext.test_ordinary_isolated_publication.OrdinaryIsolatedPublicationBoundaryTest`：**9 项通过，9.511 秒**；原始输出见 [directed.log](directed.log)。另用内存补丁向后继完整扫描器分别输入上述两段代码，得到 `successor_rows=0`，同时原 `audit_python_literal` 分别返回 `ticker`、`fixed_fiscal_date`。
- `annual_publication.py`、`sec_pipeline.py`、V13 `baseline_manifest.json` 在父提交与本提交间未变；V13 manifest 两端 Git blob 均为 `13632f33c6b09d168c95b7983e422a993e37d868`。旧年度扫描器没有被改写，V13 字节兼容成立。
- V14 当前加载、执行文件、语义绑定和 provider 离线接线校验通过；闭包为 `sha256:221aa44fde504d3cb41f41bf6b63a885978bbaf6ff535559688454c5495f704c`，执行绑定为 `sha256:33130c0698b7b62ccecebd27a627c726784275183c71f8da715fac21e12dabb4`。`ordinary_isolated_publication.py` 已把新扫描器列入 `IMPLEMENTATION`，私有 `stage` 和回读重算均经 `_compose()` 使用它。三份当前 provider／SEC／ordinary-refresh 收据的执行哈希一致，所列证据文件 SHA 分别 95／50／50 项匹配；这证明接线文件当前可读，不等于新代码经历了真实外部请求。
- 未运行长材料测试、全 fast、完整私有发布、真实 provider／SEC 调用；未审核或操作 #47／PR52。已有 `publication-current.log` 是本补丁前因旧扫描器误报失败的材料日志，不能当作本提交的发布成功。仅写入本目录的结论和短测日志；未改代码、提交或推送。

本次实际底层工具调用：**35 次**。
