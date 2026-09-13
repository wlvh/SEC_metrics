# 普通候选更新检查

`tools/vnext_normal_update.py --process`读取当前已准入的来源，维护最近尝试和最近完整成功候选。它复用现有来源验证、Run、Calculator、审阅及公共行预览；当前仍为零外发开发入口，不获取SEC文件、不调用模型、不发布或切换active。

```bash
python3 tools/vnext_normal_update.py --process --data-root /absolute/source-workspace --state-root /absolute/update-state --company marriott_international --metric B01
```

不指定`--data-root`时读取仓库已有来源；不指定公司或指标时选择当前配置范围。原有只读检查和`--discover-sources`入口保留。正常入口将状态保存在公司目录下的`metrics/<metric_id>`，每个指标独立保留成功引用；一个指标受限、当前输入失败或历史损坏不停止其他指标。每个指标配置固定公司、指标、来源目录和运行规则版本；改变这些配置会明确拒绝，不悄悄重置旧历史。正式部署和代码版本接续尚未由本接口完成。

公司汇总为`UPDATES_READY`、`UPDATES_PARTIAL`或`UPDATES_INCOMPLETE`，各指标仍保留下表的具体状态。非全部就绪时CLI返回2，但继续完成其余指标。`last_verified_candidate`给出经源与Run重验的结果、原始期间、公共行目录以及`current_input_matches`；后者为false时只能将它作为历史结果，不能写成本期更新成功。无法重验时该字段为null。旧版本的整组状态目录会明确拒绝，不会悄悄重新开始；旧材料继续用其固定运行包读取，部署时版本接续仍待完成。

每次检查先重验已有成功候选，再读取当前来源。输入身份包含来源正文、实际期间、Spec及运行规则，不把请求时间或请求身份本身当作财务内容变化。

| 状态 | 实际含义 |
|---|---|
| `CANDIDATE_READY` | 所请求指标的Run与公共行全部通过，更新成功候选引用 |
| `NO_SOURCE_CONTENT_CHANGE` | 完整输入相同，重验已有候选后保留其Run；仍会进行来源读取及校验 |
| `CANDIDATE_WITHHELD` | 有指标未形成可用结果，保存本次Run和失败状态，成功引用不前移 |
| `PREVIOUS_INPUT_WITHHELD` | 相同输入先前已未通过，保留原因，不反复生成相同Run |
| `INPUT_FAILED` / `EXECUTION_FAILED` | 输入或执行失败，保存原因，旧成功引用保留 |
| `UPDATE_BLOCKED` | 配置、历史或成功候选完整性无法确认，CLI报告具体原因 |

状态目录保存不可覆盖的意图和终态、每次候选的数据/Run/公共行，以及单独的`current.json`引用。成功终态在成功引用之前写入。中断后能重验并接续已经完成的候选；没有终态的尝试保留为`INTERRUPTED`，随后在零外发前提下重新检查输入。进程锁阻止并发更新。引用必须与真实历史记录一致，不能靠修改`current.json`伪造完成状态。

测试采用两份已保存、原文不同的真实申报清单快照。相同快照换请求身份不创建新Run；换成后一份清单会创建新候选，即使收入值没有变化。损坏来源、恢复原文、成功引用写入中断、未完成意图、并发、伪造引用和修改成功公共行分别检查。历史快照选择只开放在测试会话的`historical_test_attempt_id`参数中，必须来自受信基线中的不可变请求；不允许提供替代正文或把测试记为实时SEC获取。

```bash
ORDINARY_UPDATE_MATERIAL_ROOT=/absolute/new/update-material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_update_cycle
```

该材料没有证明新财年在线发现、真实来源获取、模型语义判断、常驻调度、全部39项或正式发布完成。新增预算、持续生产权限、代码版本迁移和最终生产确认仍需按Issue #28总委托落实。

实际混合场景通过`ORDINARY_UPDATE_COMPANY_MATERIAL_ROOT=/absolute/new/company-material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_update_cycle.OrdinaryCompanyUpdateTest`验证：Pfizer收入和流动比率独立成功，债务保持受限；重复检查不新建Run，收入输入故障保留原期间且标为历史，后续指标仍完成；篡改收入公共行只阻止该指标。
