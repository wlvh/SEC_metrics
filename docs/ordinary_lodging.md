# 普通入住率与 RevPAR

普通 B10/B11 现在由确定性来源规则接入同一 V14 OPEN Run，保留原指标定义：当前财年、可比物业、全系统、全球范围。结果中的入住率单位仍是 ratio，公共行按原表示转换为 percent；RevPAR 仍为 USD。

<!-- capability-anchor: CAPABILITY.ordinary_deterministic_lodging -->

```bash
python3 tools/vnext_normal_candidate.py --metric B10 --metric B11 --output-root /absolute/new/external/lodging
```

入口从当前保存清单选择普通原件，按既有来源基线和真实请求证明准入。适用公司重新构造原件的全部表格，核对以下关系后才生成观察：

- 紧邻表格的说明明确陈述统计年度，本年表头与之相同；不是用申报年份替代实际统计期间。
- 指标、本年值与同比变化的表头分开；数字与其同列百分号或货币符号对应。
- 可比全系统标题及全球行来自同一目标表、同一经营范围组，不能取公司运营或地域子集。
- 地域脚注完整对应原表成员，排序变化不改变成员；跨页只移除实际页码与关联目录链接对。
- 额外期间、货币、经营范围限定或尚未解释的同目标竞争表不能被忽略。

精确原文、八字段单元格定位、完整网格和源绑定进入原生观察与 Run。共享校验仅在 V14、新结构化规格及完整原文重建一致时接受无 AI 审阅的表格观察；它不制造 AI 响应或批准。重签假数、删除网格、替换旧 AI 规格仍被拒绝。

其他配置公司沿既有 lodging 适用性生成 N_A_STRUCTURAL。新原件采用暂未支持的结构时保留具体来源/实现限制，不能把错误归为公司未披露。

旧 `catalog/metrics/B10_occupancy.md`、`B11_revpar.md`、SourceStrategyRegistry 及历史 AI 资格保持原样。新普通规格在 `catalog/ordinary_lodging/`，属于未冻结开发路线；这不是重新认证旧资格或新来源获取，不启动正式采纳、active 切换或完整390坐标发布。
