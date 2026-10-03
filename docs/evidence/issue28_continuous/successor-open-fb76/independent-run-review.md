# V13 普通 Run 共有入口：独立实际文件验收

**两份合法金融/文本 OPEN 完整图通过；14 个有效文件负例全部拒绝，未发现本轮范围内的错误接受。** 尤其是旧 `ai_table` A03 规格构成的自洽 `N_A_STRUCTURAL` 图，现在先被安装政策拒绝，不再依赖 structured 分支、模型记录或 Observation 才进入来源重建。

受审草案：`sha256:fb76e3804bc76494f4efa7fa9d8c188f4b55413d0d1de281b3ebf5ce9348324e`，284 execution files。本轮另外记录五份 Requirement snapshot，总计 289 路径，首次及所有补充运行后逐文件哈希完全不变：`stable-fb76-first/initial-code.json`、`final-reviewed-code.json`。所有数据与攻击副本均在本新 `/tmp` 目录；不改共享文件、不冻结 V13、不写正式数据，provider/paid/SEC = 0/0/0。

## 合法实际 OPEN 基线

直接调用 `install_normal_inputs` → `create_normal_run(...,freeze=False)` → 再次 `_mechanically_replay_open_run(...,require_complete_results=True)`，没有使用缓存的验收结论。

| 场景 | 实际结果 | Run |
|---|---|---|
| JPM A04 | `0.025`、EXACT/PUBLISHED，2025-01-01 → 2025-12-31，3 来源，无AI Review依赖 | `run:normal-current:af127e04dbe730506e362bd1a68dde4fd66a95947d12a7f000f9328e256be0d7` |
| Marriott D01 | TEXT_V1、34条原文、4774字符，EXACT/PUBLISHED，2025-01-01 → 2025-12-31，3 来源、1 Review | `run:normal-current:6517e2a283c74d11b8ee2c15b820cbe372201a71c1e0094cabac7f5f41c55de0` |

两份 manifest 实际保持 OPEN，见 `positive-record-check.json`；基线分别保存在 `stable-fb76-first/jpmorgan_chase-A04/` 和 `.../marriott_international-D01/`。内部 PUBLISHED 不构成正式发布，本文也不声称 FROZEN/portable cold-read。

## 实际文件拒绝矩阵

每个负例从对应合法 Run 复制到独立目录，再修改真实文件并走完整 OPEN 图重放。

| 变形 | 范围 | 实际拒绝 |
|---|---|---|
| 删除全部 `spec_file_hashes` | A04、D01 | A04：`NORMAL_CURRENT_RUN_ONE_SPEC_REQUIRED`；D01：更早的 `ReviewUnit Spec is absent from repository` |
| 增加第二个已安装A11规格 | A04、D01 | `NORMAL_CURRENT_RUN_ONE_SPEC_REQUIRED` |
| 从manifest删掉一个来源 | A04、D01 | `NORMAL_CURRENT_SOURCE_SPEC_OR_TARGET_CHANGED` |
| 把实际起始日改成2025-02-01 | A04、D01 | `NORMAL_CURRENT_SOURCE_SPEC_OR_TARGET_CHANGED` |
| 删除一个RAW_BLOB记录，保留manifest | A04、D01 | 既有来源一致性门：`Run SourceReference RawBlob is absent` |
| 只删除一个SOURCE_REFERENCE记录，保留manifest和全部raw | A04、D01 | 新共有入口：`NORMAL_CURRENT_SOURCE_RECORD_SET_CHANGED` |
| 删除D01实际primary body文件 | D01 | `Run RawBlob bytes changed` |
| 自洽旧ai_table规格＋N_A图 | Marriott A03 | `NORMAL_CURRENT_SPEC_ROUTE_NOT_ENABLED` |

这 14 个有效负例包括较早的通用来源/Review门拒绝；不把它们全部冒称为同一行新代码拒绝。新的单规格/路线与来源记录集合门已分别得到直接命中。

### 旧规格绕路的强反例

这不是单纯替换旧 Spec 后留下旧 Result hash。实际过程为：用已保存的 Marriott 正常来源准备 A03 来源集合，换成真实历史 `catalog/r4_v2/A03_liquidity_coverage_ratio.md`（source_mode=ai_table），由当前 Calculator 在真实非金融 traits 下生成新的 `N_A_STRUCTURAL/PUBLISHED` Result/Trace；没有 Observation 或 AI attempt。再以该旧 Spec 构成并重新计算完整 binding/key，创建指向这个新 key 的真实 V13 OPEN Run，附带真实完整来源记录和重新生成的 Trace/Result。普通数据目录另保存此攻击专用 binding，既有原文与合法Run文件不改。

结果在进入旧 ai_table 的分支前被 `NORMAL_CURRENT_SPEC_ROUTE_NOT_ENABLED` 拒绝。完整新图及描述：`stable-fb76-first/attacks/old-ai-spec-structural/`。这证明“用旧非structured规格避开普通来源重建”的分派漏洞在本次受审版本中已被堵住。

## 代码位置与最小长期回归

- `run_store.py:2122–2125` 在所有 `issue_28_v12` 图的共有路径调用 `validate_normal_run_authority`，然后才进入通用图/具体来源模式处理。
- `normal_run_v2.py:226–247` 的 `replay_case` 先要求单规格且路径属于安装政策该指标集合，再从正常输入重建真实来源、具体规格、期间、完整binding和Run ID。
- `normal_run_v2.py:250–260` 进一步要求实际 RAW_BLOB/SOURCE_REFERENCE 记录完整集合与正常重建结果精确相等，包含数量及内容，不只是subset。

建议把本轮旧ai_table/N_A自洽图及缺/多Spec、缺manifest来源、仅漏SOURCE_REFERENCE、改期两类金融/文本图保留为专门的 normal_run_v2 回归；现有 financial_results/text_input 测试多验证组件或准备入口，不能替代这条共有 Run 路径。合法基线只需至少一份真实金融和一份真实文本，不必为每个通用集合检查重复解析全部12指标。

## 命令、首次失败及证据边界

主脚本为 `replay_boundary.py`，实际首次命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/sec_metrics_issue28_continuous/pr43-review/v13-run-boundary-review/replay_boundary.py /tmp/sec_metrics_issue28_continuous/pr43-review/v13-run-boundary-review/stable-fb76-first sha256:fb76e3804bc76494f4efa7fa9d8c188f4b55413d0d1de281b3ebf5ce9348324e
```

第一次主脚本退出1，是测试工具问题，不是合法基线失败：JSONL变形多加了空行，而且最初异常分类没有包含继承RuntimeError的RunStoreError。全部首次文件和输出保存在 `stable-fb76-first.log` / `stable-fb76-first/index.json`，未覆盖。原本已正常拒绝的缺Spec/缺body不会因测试分类写错而变成业务通过。

修正JSONL后，在全新 `corrected-source-record-cases/` 中两次漏RAW_BLOB都被更早的正确引用门拒绝；该补充脚本末尾原先过窄地要求命中新门，故退出1，但实际正确拒绝事实及日志保留。随后在全新 `missing-reference-record-cases/` 中，只漏SOURCE_REFERENCE且保持manifest/raw完整，两项均直接命中新共有集合门，补充命令退出0。

当前 `replay_boundary.py` 已修正上述测试格式/异常分类，并改用可直接检验共有门的SOURCE_REFERENCE缺失；不以重新全跑较贵基线来覆盖首次历史。`reviewed-summary.json` 汇总全部16个有效场景（2成功+14拒绝），排除两份错误JSONL探针的验收信用，保留首次自动分类及人工核对说明。本文没有把这些测试工具失败隐去，也没有将缺规格的早期 Review 错误误称为语义重建成功。

本轮未检查所有12指标的生产完成度、未执行freeze、未激活V13、未验证完整publication。结论限于当前精确草案上的单规格、来源集合、实际期间以及旧规格分派边界；后续若这些受审文件改变，应按差异补回归。

交接后主代理通知：其并行批次在增加 CI 选择器后出现 `tools/run_fast_tests.py` execution-authority hash drift，后续还将调整D02并统一重建草案。本轮安装、负例及最终289文件核对已在该通知前完成；本报告的fb76信用不延伸到之后的工作树或下一草案，本代理未再进行新安装。
