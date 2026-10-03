# 普通原生结果的完整版本准备

`vnext.ordinary_release_preparation`把多个公司、不同类型的普通原生Run接到已有Projector合并函数，保留实际`PublicationView`前驱，输出可继续交给后续采纳/发布适配的完整矩阵、证据、原生输入与来源。

```python
from pathlib import Path
from vnext.ordinary_release_preparation import prepare, verify

prepared = prepare(
    native_runs=[
        {"data_root": Path("/absolute/native/data"),
         "run_dir": Path("/absolute/native/run")},
    ],
    output_root=Path("/absolute/new/preparation"),
)
verified = verify(
    preparation_root=Path("/absolute/new/preparation"),
    expected_preparation_id=prepared["preparation_id"],
)
```

输入须为已存在的普通`OPEN` Run，且原生完整重放及公共行重建均通过，主结果为`PUBLISHED`。`PUBLISHED`在此是原生结果状态，不等于正式发布。类型、适用性、数值、文字、原因、期间、来源信用及原Requirement身份按原记录保留；没有可用主结果的Run不能进入这份选定结果包。预览适配本身不创建或调用模型，不更改指标含义。

输出目录必须是新的外部目录，不能位于代码checkout或任何active根内。准备时只读当前实际PublicationView，精确复制其完整包作为前驱；每个选定Run及其数据目录独立复制。复制后的来源、Run、Review和结果由当前真实验证器重读。输入Python只作为原始字节保留，执行代码来自当前受信安装。

## 可检查的文件

- `ordinary_release_preparation.json`：确切前驱、选定坐标的结果与原规则、当前范围来源哈希、完整文件索引及准备ID。
- `metrics_matrix.csv`与`metric_evidence.csv`：同一完整版本。选定键按原Projector合并语义替换或追加，未选定行的字段、期间和顺序保持原值。
- `native/NNN/data`、`native/NNN/run`：选定坐标的来源和原生图。每条新增证据的`source_locations`给出包内路径及原文哈希；公共证据原字段不重写。
- `predecessor/<publication_id>`：完整、仍可按原PublicationView读取的历史前驱；继承证据的原路径由这个前驱拥有。

`verify`重新构造完整版本，不只校验自签哈希。即使修改公共数值后同时更新文件索引、矩阵哈希和准备ID，也必须与原生重放结果一致。原数据目录移走后，复制包仍能读取；原文或Review损坏须被拒绝。

## 尚未赋予的信用

准备包固定`publication_credit=NONE_PREPARATION_ONLY`、`switch_available=false`、`full390_acceptance=false`，没有`publication_manifest.json`或指针，不能调用正式切换。`unselected_coordinate_keys`只表示本包未选择的坐标，不能据此宣称它们全部未实现或无披露。继承行也不取得新的期间或验证信用。

普通39项的确切采纳集合、相应执行绑定、统一发布类型接线、旧生产/补数入口退出及集中生产确认仍须继续完成。这里不扩大旧B01/B10年度合同，也不重写冻结R3/R4或旧Run。

完整材料测试：

```bash
ORDINARY_RELEASE_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_release_preparation_material
```

该测试选择Pfizer B01数值和Salesforce C02文字，使用实际完整保存来源创建原生Run，随后验证完整版本、原输入移走、重签虚假公共数值、移除文字Review、恢复后重验及正式指针不变。网络、DNS和HTTP入口全部禁用；不重复Marriott试点，不形成新SEC/provider调用或390全量验收。
