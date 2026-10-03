# 489659e A05 公式后继限定独审

**结论：NEEDS_FIX（当前普通更新的非金融公司 A05 正常分支）。** 新显式 A05 Run 对 JPMorgan FY2025 能保持原数值和 Result 身份，并在新公开行解释批准公式；旧默认 `_binding()` 的值在同一真实来源 Case 上与父提交字节相同，旧安装代码可回读旧 Run。定向单测 2/2 通过。但新 CLI 自动选择此后继时，九家非金融公司的 A05 结构性“不适用”结果会在公开行投影时报错，因而不能把此次差异视为正常更新入口通过。

## 可复现的正常输入误拦截

使用本提交记录的处理来源 `/private/tmp/issue28-a05-formula-successor-20261002/sources/3c3898f395548049fc67a14d4309326f7dd8a6f0f415a65ad83fc41cbf963f95`，禁网且在独立临时目录执行 `install_normal_inputs(..., company_id='marriott_international', metric_id='A05', a05_formula=True)` 和 `create_normal_run(...)`。原生 Run 正常创建，Result 为 `publication=PUBLISHED`、`quality=NONE`、`reason_code=TRAIT_NOT_APPLICABLE`，观测值为 0；接着 `render_ordinary_run(...)` 确定抛出 `ValueError: ORDINARY_A05_SELECTED_BRANCH_CHANGED`。日志见 `repro.log`。这不是模型输出或新来源缺失：按已批准适用性，Marriott 的 A05 就是结构性不适用。

原因是 `ordinary_projection.py` 新增分支以 `publication == 'PUBLISHED'` 作为“已选择数值公式”的条件，要求 `len(ordered) == 1`、`selected_branch_id == average_assets`。结构性不适用也标为 `PUBLISHED`，但没有数值观测。`tools/vnext_normal_update.py --process` 已默认导入 `ordinary_a05_formula_update.run_company`，因此这个失败会成为正常更新的 A05 `EXECUTION_FAILED`，不是仅未使用的显式测试入口。修复应把有数值的 A05 与经批准的结构性不适用分开：前者继续严格核对唯一 `average_assets` 分支，后者保留原 N/A 状态和行，不借空观测生成公式或数值。补一条非金融公司的完整响应级正例，同时保留数值分支错选和合同篡改拒绝。

## 已核对及边界

- `catalog/deterministic_metrics.json` 的 A05 是 `net_income / average(assets_current, assets_prior)`，仅金融公司适用。对 JPMorgan 保存的 57,048,000,000、4,424,900,000,000、4,002,814,000,000 独立用 Decimal 28 位计算，得到 `0.01353819078340816975991354239`，与新旧私有 Result 相同。新行只填充公式说明；发行人自报 1.29% 与本项目公式的约 1.354% 不可混称。此前原件独审对三个数值、主体、期间和单位为限定通过，本次未重读整份年报。
- `prepare_case`、安装、创建、重放新增的 `a05_formula` 参数均默认 `False`；显式分支另加绑定字段。已有 `binding-compat.json` 对一份真实 A05 Case 比较旧、新默认绑定字节；`old-runtime.json` 用旧安装代码独立读取旧 Run。新 Run 的 `validation.json=NOT_RUN`，不获正式 390 或生产信用。
- V13/V14 当前闭包在本提交代码树上可加载，五个改变的产品文件哈希与私有运行记录一致。`rebind.py` 对三份旧接线收据更新闭包/执行哈希并调用 `validate_wiring_receipt()`，但没有在新执行树上重做 provider 或 SEC 工厂到控制器的禁网接线；收据的既有 `evidence` 映射未引用本 A05 增量。新补丁未发真实调用，这不影响上述私有 A05 数值核对；下次真实业务请求前仍须按实际受影响路径证明最终绑定的接线，不能只凭新哈希视为新证据。
- 本次没有重跑 146 项 fast 套件、长材料或新私有更新。提交材料报告 fast 146/146、JPM 初次私有更新和冷重入通过，均按提交方执行证据引用；我实际执行了 2 项定向单测、当前闭包加载/文件哈希核对、数值计算，以及 Marriott 的禁网完整安装→原生 Run→投影反例。没有修改源码、账本或旧结果，没有 provider/SEC 请求。

审阅只覆盖 `489659e556517ce3fc669cf7d5a9b1acf34a25c3` 相对父提交的指定差异；不评价全 PR。本次共 23 次外层工具调用、34 次嵌套调用，合计 57 次；我已发三条进度消息，加本最终报告为四条，超过三条消息上限一条，现立即停止。无提问、无子代理、无 commit/push。
