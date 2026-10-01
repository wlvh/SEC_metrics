# 32faa26d B02 普通路线限定独立审阅

**结论：PASS_WITH_BOUNDS。** 对 `32faa26d87b47a882e13145e450e565df0eaa1d3` 相对其父提交的指定范围，没有发现可复现的 B02 错误接受、合法改名误拦、普通入口漏接或当前绑定失配。本结论只覆盖 B02 普通 Company Facts 接线、V13/V14 当前可变绑定、三份离线收据与 AGENTS 协作节；不是全 PR、真实新财报 Run、生产采纳或 #47 历史结果的验收。

## 代码与结果边界

- 固定只读来源为 #47 提交 `48b46a2d742eb3e3b8bd5a6404908745046b5d2f`。本地 `paired_measure_v1.py` 的 `_paired_concept_lists`、`_claim_view`、`paired_measure_problem` 去掉说明文字后的 AST 与该提交 `historical_results.py` 三函数一致；原因码改为普通路线专用的 `NORMAL_PAIRED_MEASURE_NOT_COMPARABLE`。函数只检查已批准图选出的两年 claim，不重选目录概念或用目标年报的重述值替换上期原值。
- `normal_companyfacts_results.py:209-240` 在 B02 已选图之后调用检查。若不同标签且目标申报没有用本期标签报出与上期选中值、期间、单位均相同的比较值，则只把 B02 改为具名 `WITHHELD`，清空它的 claim/observation；其他指标仍各自处理。`normal_run_inputs.py:42-49` 和 `normal_run_v3.py:148-161` 把该普通结果送入正常 Run 输入，政策配置亦包含 B02。
- 已保存 Pfizer 原件的 3 个短例覆盖 FY2023/FY2024 错误混用被拦、FY2022 有本期申报桥接的合法改名通过、相同标签无需桥接。当前 FY2025 普通输入及故障注入的提交日志显示原 `Revenues`/`Revenues` 的 B02 保持 `PUBLISHED/EXACT`、注入失配后 B02 扣留且 B08 不变。后两项为对已有日志的只读核对，并非本审阅重跑；FY2023/FY2024 的短例直接调用检查函数，不是以那些年作为普通最新财报做整条 Run。

## 绑定与收据

- 只读重新加载 V13/V14 Requirement 并执行 `validate_execution_authority`，两者通过；V14 的 `validate_semantic_rule_bindings` 与 `validate_wiring_receipt` 也通过。当前闭包分别为 V13 `sha256:95aab27d7dbf1b0c862e495b06828ad8119ddbc87025687f50503a2a3ff353f3`、V14 `sha256:afa5edc728d8e12a46edcbb1c8361f181c6ad0a8c3005ad24022c31c8ee6683a`。两份清单都按实际 SHA-256/大小绑定新模块及修改后的普通 resolver；V14 父绑定和 transfer 指向更新后的 V13。
- provider、SEC、普通刷新三份收据的 execution authority 均等于当前 V14 的 `sha256:d124c14e5dbcf9b17481c1260b23af9955735f05a18d030faef873d846c4a2ba`。逐项只读重算其证据文件哈希，分别 95/95、50/50、50/50 匹配；收据均仍写零调用。收据重绑不证明新的真实业务调用或旧安装根冷读。
- 本地 AGENTS.md 的唯一 `COLLAB-28-47-v1` 标记内文字与实时 Issue #28 正文逐字节相同（均 6532 bytes；SHA-256 `26dae6cd9b8f6e890c895231833a1e1218f7e67c0dcb238e10ab376e128d823a`）。未操作 #47 工作树或账本。

## 验证与限制

独立运行 `PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -m unittest -q tests.vnext.test_normal_b02_paired_measure`：3 tests，exit 0。提交内现有日志记录普通当前输入 1/1、Company Facts 来源测试 11/11、fast selectors 143/143；这些长测未在本审阅重跑。`execution-state.json`、`continuation.md`、C02/E01、其他业务路线与全 PR 均不在此次裁定范围。

桥接规则只证明目标申报中存在数值、单位和期间一致的比较事实；同一个标签跨年改变会计含义、两个不同量恰好同数，均非本规则可单独识别。这是固定 #47 实现已明确的能力边界，此次没有证据显示它在上述普通 B02 样本产生错误结果。V13/V14 当前目录已换闭包；旧 Run 应按其原安装根的冻结规则/字节读取，本次未对旧根做冷读，也未重签旧结果。

实际工具调用：20 次 `functions.exec`、60 次内层工具调用（含写入与文件核对），按双层合计 80 次；未 commit、push、发真实 SEC/模型请求或修改 #47。
