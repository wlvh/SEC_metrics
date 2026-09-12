# 普通保存来源候选

开发入口从已有实际SEC材料自动准备输入，经同一原生Run验证后生成候选和公共行。当前V14是未冻结的开发草案，默认状态为OPEN。

```bash
python3 tools/vnext_normal_candidate.py --output-root /absolute/new/external/directory
```

默认范围为36项已支持路线：六金融指标、B06、C02/C03/C04、D01/D02、旧22项零AI指标及确定性B10/B11。可重复`--company <配置ID>`、`--metric <ID>`限定开发检查范围。输出目录必须全新、在源码外且不属于正式发布目录。剩余B13/D03/D04及完整更新、发布、回退恢复和旧入口退出仍属总委托，不因当前36项停止。

每个坐标保存原生Run、实际期间、状态、来源选择和错误；`summary.json`保留完整请求集合。主指标有通过源重建的结果时为`OPEN_CANDIDATE`，无可用值但有受控解释时为`WITHHELD_CANDIDATE`，输入或执行故障单独记录。无缺口时为`OPEN_CANDIDATES_READY`，有缺口时为`COMPLETED_WITH_GAPS`。退出0不代表冻结、正式采纳或Issue全量验收。`--freeze`仅在安装规则明确开启后可用；当前草案拒绝该操作。

<!-- capability-anchor: CAPABILITY.normal_saved_candidate_batch -->
<!-- capability-anchor: CAPABILITY.ordinary_integrated_run_graph -->

V14公共验证先核对从原件重建的主指标、确切规格集合、依赖、来源和完整计算图，再按来源模式分派。B03必须包含B01依赖规格及其真实结果/轨迹；删除依赖结果不能因主指标仍可计算而通过。事件的确定性事实也存入Run，来源引用角色和事件集合角色分别记录。文本审阅决定先于最终结果写入。

公共行仍是20字段矩阵与18字段证据。一个B03 Run内的B01依赖不会多投影成第二个主结果；复合比率、现金流等逐项展开参与计算的来源事实。数字证据标为解析事实或归一化观察，未证明的原始字面值留空，不能把算出的比率冒充原文金额。事件计数沿用已批准条目规则，不代表已确认的真实业务事件数量。B12明确为RPO替代口径。

<!-- capability-anchor: CAPABILITY.ordinary_candidate_diagnostics -->

WITHHELD公共行保留请求子指标的具体选择或失败原因；例如前期历史清单冲突不能只留下笼统的计算失败。NOT_MEANINGFUL比值保持空值及原始证据，不会因为正常值缺失而丢失公共行。

<!-- capability-anchor: CAPABILITY.ordinary_amendment_input_scope -->

修订件逐份保留并按输入属性核对。已证明只更正附件链接的有限结构，可让未受影响的原报告数值与事件窗口继续处理；事件日期窗口成立不等于主体连续性或事件来源已完整。Part III识别不自动批准财务范围。删除修订来源不能通过原生Run重建。

财年与实际期间分别保存：Salesforce原文明示2026，其DEI/同申报CF原始2025及冲突仍保留；Macy’s财年2025与截至2026-01-31的时点并不冲突。季度均值不会重标全年，C02申报日期也不替代未知的董事会测量日期。当前Salesforce C03实际走ECD期间匹配，未发现其49,379,252美元金额错误；跨标签差异的SCT后继支持仍需继续完善。

V12/V13已有历史冻结记录，规则和五文件不可同版本改写。新的共享注册表和Run接线使用显式V14；旧数据目录的执行字节和旧引擎/规则仍可冷读验证。不能把新源码复制进V13数据根后重签旧规则。当前V14无FROZEN记录，已完成的OPEN材料和公共行不构成340或390坐标全部通过。

现有正式active保持原状。新增费用与最终生产权限按总委托分别核实，历史关闭额度不恢复。实际运行、首次失败及修复材料见`docs/evidence/issue28_continuous/`；来源组件细节见`docs/normal_source_components.md`。
