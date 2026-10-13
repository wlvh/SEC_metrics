# 已接收 PR247 后继：损坏 D02 回答包不阻断邻居

回应 [PR247 P2 4257796891](https://github.com/wlvh/SEC_metrics/pull/247#discussion_r4257796891) 和接收方 [4257817886](https://github.com/wlvh/SEC_metrics/pull/247#discussion_r4257817886)。实际 main `cfbb457b6ec48fb8408ef09b14b03c3342c56e41` 已接收247，不能重写旧接收或把该修补继续推到已合作者分支。

## 错误和最小修补

`saved_review_input_paths()` 在公司 controller 之前读取 terminal.json，缺文件、JSON损坏或缺 evidence 都会提前终止整批。新增混合请求控制在该 main 前红：三种错误均没有公司输出。

现在只在已有 D02 包准备范围捕获异常，生成一个明确不同的失败 producer，再交既有每指标 updater 记录原错误。有效包继续用原 factory 及七文件输入身份；D02失败不创建结果，也不调用模型或来源汇总，其他已选指标沿原 controller 处理。失败 producer 的不同名字防止此前零必需回答任务被意外复用为成功；包恢复后仍走正常 factory，不把错误缓存成永久结论。

`company_local` 和 `historical_d02_case` 只有这一项公共边界修复。没有另造控制器、关闭校验、删去原失败或把坏包解码成空模型回答。未知指标、年份范围和调用用途的入口检查保持。

## 正常入口的真实保存来源验证

仅将本方原七成员答案集复制到新开发目录，并从该副本删除 terminal.json；原回答仍只读且七成员哈希保持。实际 SEC 来源复用本方原 `issue28-2026-09-13/source-inputs`，没有重取或替换 source。正式 CLI：

```bash
python3 tools/vnext_company.py run --company ford_motor_company \
  --period fiscal-years --fiscal-year-start 2025 --fiscal-year-end 2025 \
  --metric D02 --metric B04 --source-root <完整只读SEC来源根> \
  --saved-legal-reviews <损坏回答的测试副本> \
  --work-dir <新测试状态> --output-dir <公司输出父目录>
python3 tools/vnext_company.py results --company ford_motor_company \
  --state-root <上述状态> --output-root <新独立读取目录>
```

| 实际步骤 | 耗时 | 结果 |
|---|---:|---|
| 首次混合运行 | 4.130s | D02 INPUT_OR_EXECUTION_FAILED；B04 CANDIDATE_READY；公司报告和两行CSV正常产生 |
| 禁止B04来源准备/Calculator的复跑 | 0.699s | D02再次明确失败；B04 NO_SOURCE_CONTENT_CHANGE，原ID和6个结果文件保持 |
| 新进程 results | 0.448s | D02 NO_CURRENT_RESULT/空值；B04数值、单位、期间、出处保持；23状态文件不变 |

B04为 −8,162,000,000 USD，CIK37996，2025-01-01至12-31，Result `sha256:89f9cc9df7dc78e52fcd0a97eb580afa3d793c787e65cc6500529f8a2d4662e7`。Root独立读取保存 Company Facts 的 `us-gaap:ProfitLoss` 原行（申报 `0000037996-26-000015`、frame CY2025、FY2025、val −8162000000），核对原文件SHA及CSV。不是给损坏D02填值，也不是改变B04定义；未声称两个指标证明全部39项。

首次验证脚本错误预期 FileNotFoundError，实际 canonical 读文件入口抛 CanonicalError，故脚本停止但真实 B04 已成功。`actual-mixed-before-harness-type.log` 保留此失败；修正测试的异常类型后通过 `--resume` 读取原 first.json 接续复跑/读取，没有重复首次计算。`actual-mixed.json`、原行核对和 `verify_mixed.py` 记录真实参数/提交/未提交差异及可运行方式。

小状态测试中的B04=100是明确构造数据，只验证公共批次隔离；实际业务值来自上述正式CLI。正常D02非空首算/缺完整答/未决/旧成功保留/恢复与独立读沿 [PR247主记录](../issue28_d02_company_saved_20261013/README.md) 复用，正常factory及相关责任未改，不重跑8秒正向链或旧大材料。

## 共用核心后继及边界

本方接收 #47 的固定 `658e085727e7a2fd46ab2dd55b6a9c75d87e6c73` 无前缀附注修补，[PR249](https://github.com/wlvh/SEC_metrics/pull/249) 是其从实际 main 发布的接收后继。它修复另一条 [4257796903](https://github.com/wlvh/SEC_metrics/pull/247#discussion_r4257796903)：仍要求已定位 note 的真实结束位置，但不再额外要求字面 Note 前缀。普通编号小节/未引用Note40/年份负例保留。Root未并写核心；首个完整Ford缓存、原8页眉位置/45原字段和D03的有限重验是提供方证据，不冒称本方重新复现。

组合短验证覆盖新增坏包三种形状、正常/未决回答、原七文件读取、controller恢复、页眉/无前缀/年份边界；最终结果在 `final-controls-with-failure-identity.log`。新方法位于原CI已有模块，无重复登记或新workflow。修补依赖249接收或明确固定组合；不能借245旧merge信用覆盖658。

新增真实SEC/provider/paid调用0/0/0，原许可、计数、结果/回答/失败历史保持；作者不Ready、合并、采纳、部署或active。这里只修异常隔离及已定位边界，不证明新模型、全部D02/390或完整自动更新。接收方亲复返回场景后解除原线程。
