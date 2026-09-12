# 逐笔债券账面额与明确无融资租赁的 B06 来源路线

`b06_note_carrying.py`支持一种新的原件结构：`LongTermDebtTextBlock`包含完整的`ScheduleOfDebtTableTextBlock`，每笔债券分别列出面值、尚未摊销的折价或发行费用以及扣减后的账面额；当期租赁政策明确说明没有融资租赁。它通过`normal_note_debt_results.py`进入既有普通Run、Calculator及公共行预览，B06的经济定义不变。

这是新的有限解析分支。它不修改旧`b06_disclosure.py`/v2、旧规格或已冻结规则，也不把两个不同的来源标签改名后交给旧验证器。仅有标签匹配用于选择待核对的分支，不能批准数值。

核对包括：

- 全部债务表行逐笔对账，当前部分只扣减一次，合计分别与原HTML、XBRL及同申报Company Facts一致。利息费用表保留为另一张表，不与期末债务余额混合。
- 原始命名空间、主体、期间、货币单位及显示符号必须一致。表内“减：流动债务”的负号表示从合计中扣减，不把真实正负债变成负债务。
- 每笔债券的细分原生事实也必须与表中对应年份及金额一致。其他借款不能因为带着债券细分标签就从遗漏检查中消失。
- “没有融资租赁”必须是当期原件中未被引用、未作为链接的公司自身声明。缺少声明、历史声明、其他相反文字或原生融资租赁金额都不能得出零。
- 全部当期相关附注的表行及货币余额陈述保留核对；贷款应收款和投资持有的商业票据有原表的资产用途说明，未知借款行不能套用这些排除。已声明的账面额和费用叙述按其实际显示精度与精确表格金额比较。

当前保存的 Enphase FY2025 原件列出三笔债券：账面额分别为572,194,000、632,183,000和0美元，合计1,204,377,000美元。期末权益为1,087,023,000美元，B06为`1.107959077222837051285943352`。原文明确写有无融资租赁声明。年度附注提供证据，指标的实际测量期间仍是`2025-12-31`这一时点。

源测试保留过一次真正漏检：新增17,000,000美元短期借款挂在债券细分维度下，早期只检查合并事实的实现错误接受了它。现在将该类细分事实纳入独立检查并逐笔对账，原反例保持拒绝。首次Run还揭示年度输入期间与时点观察不一致；原失败保留，新Run明确使用期末时点。测试材料不能被解释为生产采纳或独立审阅批准。

```bash
python3 -m unittest -v tests.vnext.test_b06_note_carrying
python3 tools/vnext_normal_candidate.py --company enphase_energy --company marriott_international --metric B06 --output-root /absolute/new/note-debt-batch
NOTE_DEBT_NATIVE_BATCH=/absolute/new/note-debt-batch NOTE_DEBT_ATTACK_ROOT=/absolute/new/note-debt-attacks PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_note_debt_run_material
```

当前仍为未冻结V14开发候选，默认OPEN。Marriott非正权益保留原来的无经济意义结果；银行、工业金融混合范围、供应商融资及其他未覆盖结构仍需各自证明。新分支不会把这些缺口变成零或给予通过。新来源获取、模型预算、独立审阅、390坐标整体验收及最后生产确认仍按总委托继续处理。
