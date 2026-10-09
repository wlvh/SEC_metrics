# 已迁移零AI指标的普通年报原型

## 交付范围

新增 `scripts/vnext/normal_zero_ai_results.py` 和 `tests/vnext/test_normal_zero_ai_results.py`。本轮原型仅B01与C01；现有V13规则、Specs、源码、CI均未改。没有Run、freeze、新PR、provider/paid/SEC调用或正式采纳。

B01直接复用现有B01 Spec、Company Facts原件适配与Calculator。C01按已批准event catalog计算Item5.02申报事件的唯一键数量，复用完整SourceSet、8-K adapter和Calculator；这不是从文本推断CEO更换人数。普通年份/CIK/原件由normal_annual_input与normal_source_authority自动决定，调用者不能传期间、表格、答案、事实或许可receipt。

## 实际原型

- Marriott：B01，原件FY2025 2025-01-01至2025-12-31，26186000000 USD，3份原始来源；C01同期间，10个8-K的header/primary共23份来源，3个Item5.02事件。两份稳定原生JSON原型保存后由新调用从原件完全重建相等。
- Salesforce B01：41525000000 USD，2025-02-01至2026-01-31；保留原DEI年度标签2025，未按结束年擅改。Macy’s同样保留52周年度2025-02-02至2026-01-31。
- 十公司×2：13数值、1结构性N_A（JPM B01）、6 WITHHELD。Southwest两项为本原型尚未实现年报修订影响核对；Paramount两项为主体接续口径尚未接入。JPM C01保留历史submissions索引/body范围冲突；Salesforce C01保留实际已有hdr.sgml失败请求，不将其当零事件。
- Pfizer C01有真实完整9个8-K来源但无Item5.02，按原生规则形成0；与缺来源时WITHHELD不同。

`stable-prototypes/index.json`索引稳定B01/C01正例和非日历/缺来源/历史范围冲突原型。`matrix-first.json`与逐公司初轮JSON保留探索过程；最终行为由7项测试及稳定原型证明，不把初轮运行时的开发代码版本混称最终冻结身份。

## 验证

7项测试覆盖20实际坐标、原始Company Facts同申报事实、完整8-K与真零、非日历/结构性/主体接续/修订/真实来源失败、JSON重建与重新签hash后改值/遗漏来源、无Git的独立来源目录冷读及原件篡改、调用者不可传答案和B10不能进入该入口。测试期间禁网络，并禁止打开outputs、fixtures、历史矩阵、报告和派生filing inventory，仍能生成结果。

首套33.725s中6项通过，portable测试在正确拒绝原件篡改时因测试期待ValueError而实际BatchWorkflowError发生ERROR；原日志tests-first.log保留。只修异常断言后针对性重跑同portable测试，B01与C01实际异目录重建/篡改拒绝全部通过，29.809s，日志tests-portable-recheck.log。两次setUp均实际重建20坐标，不增加来源调用。没有重跑旧生产批次。

## 可接下一规则版本的接口

`resolve_ordinary_zero_ai_metric(repo_root: Path, company_id: str, metric_id: str)`返回：compiled_spec/spec_origin、实际target/target_period/prepared_input、source_records/source_references/source_proofs/source_admission/source_set_manifests、claims/selection、observations/result/trace/records、input_binding/input_binding_id/component_id以及0/0/0标识。

`verify_ordinary_zero_ai_metric(candidate, repo_root, company_id, metric_id)`从实际原件完全重建，不接受只对外部事实receipt重签。B01的spec_path为现有catalog/metrics/B01_revenue.md；C01复用已批准event catalog动态compile，当前prototype的spec_path=None，spec_origin明确catalog/event_routes.json+C01。后继规则应固定同语义普通入口Spec，绑定catalog叶内容与新模块，并以此重建完整Run图。不要直接把prototype ID当FROZEN Run。

## 22项复用路线及实际差异

- 13项Company Facts路线：R1的B01/B03；R2的A05/A06/A07/A08/A10、B02/B04/B05/B07/B08/B09。复用Specs/确定性catalog、角色和公式、Calculator；需补普通current/prior申报与真实期间，不能再由旧outputs/latest_filings_inventory.csv或旧Result选择。
- 3项accession XBRL：A01/A02/B12。现有catalog输入是current_instant，但Result标current_annual；普通入口必须显式处理实际测量时点与年度归组。旧分支还直接比较源unitRef字符串（number/usd），因此新源单位与命名空间的独立核验不可省略，不能只换年即声称完成。
- 6项事件：C01/E01–E05共用同一批完整8-K原件及中性item claims，分别按现有event_routes投影。C01现已证明该基础路线，后继其他五项可复用。历史R2还从已获取原件补集找出submissions遗漏项；本原型比较安装来源的完整同CIK/期间获取清单，发现遗漏补集时给IMPLEMENTATION_GAP，不能悄悄缩小成功计数。独立data root的清单也须与安装来源相等。
- `public_projection.render_public_rows`已经不依赖旧答案，可复用其20列生成；历史兼容比较函数应继续分开。新普通展示仍需保留实际期间和状态，不修改已执行Spec。
- 不可直接调用`zero_ai_release._r1_source_plan`或`zero_ai_r2.build_r2_source_plan`：前者进入旧release/legacy snapshot准备；后者读取旧Publication、outputs/events.csv和latest_filings_inventory.csv。这里仅复用其独立source-set helper，没有调用旧release/发布入口。
- B10/B11保持原来冻结资格和原响应边界，本原型明确拒绝；后继整合不能用这里的0调用路线恢复模型资格。

## 边界及下一增量

当前数据仍来自安装的既有获取基线，不证明今天SEC最新状态，也不授予真实获取或执行预算。4项修订/主体接续仍明确是开发缺口；2项原件覆盖/请求失败仍带真实原因。最短后续是固定普通B01/C01规则入口、增加其余五个共用事件投影与B03，再复用current/prior SourceSet逐步接余下确定性catalog；同时单独解决修订影响、接续范围及三项instant语义，不把旧批准额或历史结果当新输入。
