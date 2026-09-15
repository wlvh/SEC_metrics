# 普通多坐标完整版本准备：数值与文字原生材料

新`ordinary_release_preparation`复用当前原生Run重放、`render_ordinary_run`、Projector矩阵/证据合并函数和真实PublicationView前驱。没有修改旧年度B01/B10合同、历史Run或正式active，也没有新增发布类型或switch权限。

最终材料测试通过，512.912秒；日志`final.log`。完整包有327个公共行，其中本次选定2个原生坐标，其余325行按准确前驱原字段、期间与顺序继承。该数字不是本期390完成数，剩余388个未选定坐标也不是388个开发失败。

| 选定坐标 | 原生结果 | 原生期间 | 来源与证据 |
|---|---|---|---|
| Pfizer B01 | 数值，EXACT，OPEN Run内PUBLISHED | FY2025，2025-01-01至2025-12-31 | 真实已保存来源；1条公共证据 |
| Salesforce C02 | TEXT_V1，EXACT，OPEN Run内PUBLISHED | FY2026，2025-02-01至2026-01-31 | 完整保存年度/代理来源与SYSTEM Review；30条公共文字证据 |

两者明确保留`PREEXISTING_SAVED_ACQUISITIONS_ONLY`来源准入、原Spec/Requirement、结果ID和期间。是否为390新增结果，应与已有结果ID对账；不能因为新建了测试目录就计为新增业务能力。这里增加的是多公司、多类型结果进入同一可重验完整版本的准备能力。

## 实际正反例

- 两个完整原生Run先创建成功，再复制原输入与Run，组合真实完整前驱；每个新增证据的包内原件均校验实际哈希。
- 移走原输入目录后，仅用准备包原生副本与复制前驱重验成功。
- 修改Pfizer公共数值，并同步重签文件索引、矩阵哈希和准备ID，真实原生组合重算后拒绝：`ORDINARY_RELEASE_NATIVE_COMPOSITION_CHANGED`。
- 删除Salesforce文字的`REVIEW_UNIT`并重签外层文件索引，原生审核图拒绝：`Review decisions contain a foreign unit binding`。
- 恢复原始字节后完整重验成功，实际active指针前后字节一致。

首轮450.062秒已完成正向和重签数值反例，但Review攻击测试错误使用多行JSON写入JSONL，先被JSONL格式检查拒绝，且测试未捕获原生RunStoreError。该失败保存在`first.log`及`first-malformed-review-*`，不当作语义Review反例通过。修后保留原单行JSONL字节，只删除Review记录；复用已经完成的两个原生Run，未重复获取或创建它们。最终测试还补验明确来源准入字段。

## 可复用材料及边界

`material-index.json`与`material-objects.tar.xz`采用仓库既有还原格式，包含最终`prepared/`完整前驱、原生输入、Run、矩阵、证据与准备清单，及摘要和攻击结果。2137个文件映射中2110个直接引用经SHA/size核对的仓库同字节文件，必要新增22个唯一对象，压缩后133,776字节。直接用既有`b13-native-assessment/restore_material.py`实际恢复全部2137个文件，并与完成的完整材料逐字节比较相同，见`deduplicated-restore-check.json`。无需重跑业务。

```bash
python3 docs/evidence/issue28_continuous/b13-native-assessment/restore_material.py --evidence docs/evidence/issue28_continuous/ordinary-release-preparation --repository /absolute/checkout --output /absolute/new/restored-preparation
```

原19MB完整tar留在本地，初次完整归档检查`archive-verification.json`保留历史含义。API与后续发布消费说明见`docs/ordinary_release_preparation.md`。

本包固定`NONE_PREPARATION_ONLY`、`production_authorized=false`、`switch_available=false`、`full390_acceptance=false`；没有`publication_manifest.json`。后续明确的普通采纳/发布适配可消费这份保存的完整原生材料，但需要重新核对当前检查、准确集合与原执行身份，不必另做丢弃式诊断批次。

新增provider/paid/SEC为0/0/0，网络/DNS/HTTP入口均禁用。正常自动获取与更新、39项正式类型接线、旧入口退出及集中生产确认仍继续，不由该准备包宣告完成。
