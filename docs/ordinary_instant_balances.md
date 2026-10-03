# 主体接续后的期末余额

普通 B08 流动比率和 B09 现金储备沿用原目录：只需要当前主体在期末的余额，目录明确允许主体接续。程序此前在读完来源后，一概用接续关系阻断全部普通 Company Facts 指标，增加了目录没有要求的限制。

当前接线只在原目录允许接续、结果为时点、所有组成均属于当前申报时使用这一分支。数据仍由当前主 CIK、当前 accession 和当前时点限定。全年业绩、跨期比较和债务完整性不能从这些余额推导。

## 修订与原件的关系

新 `instant_balance_amendment` 单独验证原报告期末余额在有限修订后的输入资格，不改变旧 `annual_amendment_scope` 的结论。Part III 修订必须同时具备：

- 完整且未引用的说明，明确原报告主体、期间、申报日、修订号、只补充 Items 10–14 的用途和未另行修改的声明。
- 同主体/期间、正确命名空间及转换规则的原生“财务报表错误更正”未勾选标志，与封面可见声明一致；重述提示也未勾选。
- 完整 Part III/IV 和相应 Item 结构、只有治理类原生事实、明确且未引用的“未附新的财务报表”声明。
- 全文没有未解决的余额披露或财务更正语句。只有完整匹配的有条件薪酬追回条款可作为条件性引用保留，不能仅因出现“in the event of”就忽略其余文字。

该证明的指标集合仅为 B08/B09。旧输入证明仍不批准 Part III 修订后的普遍财务数值；B06、治理/法律判断和全年可比性继续分别验证。未知修订、明确更正、引语或新的余额披露仍保留未解决状态。

## 实际原件与验证

Paramount 当前注册人的原件和同申报 Company Facts 在 2025-12-31 一致：流动资产 133.20 亿美元，流动负债 105.99 亿美元，现金及现金等价物 32.74 亿美元。因此期末流动比率为 `1.256722332295499575431644495`，现金为 `3274000000 USD`。原件同时包含前身/后继期间，并不使全年业绩可比。

来源反例保留了首次误放行：早期检查器漏识别“financial restatement”名词短语。修后要求完整条件性条款，并拒绝已发生重述、正文别处的更正/余额、勾选更正/重述、额外用途、错原报告日期、引用声明和新增财务原生事实。原始失败、原件检查和后续实际 Run 证据分开保存。

```bash
PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_instant_balance_amendment tests.vnext.test_normal_companyfacts_results
python3 tools/vnext_normal_candidate.py --company paramount_skydance_paramount_global \
  --metric B08 --metric B09 --output-root /absolute/new/instant-runs
INSTANT_BALANCE_NATIVE_BATCH=/absolute/new/instant-runs \
  INSTANT_BALANCE_ATTACK_ROOT=/absolute/new/instant-attacks \
  PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_instant_balance_run_material
```

Run 仍为未冻结的开发候选。真实来源限制、未解决的其他指标、独立审阅和完整生产验收继续保留；不产生新增获取、正式采纳或 active 切换权限。
