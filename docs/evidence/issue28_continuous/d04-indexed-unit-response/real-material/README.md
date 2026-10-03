# Ford / Pfizer D04：完整真实结果与原调用材料

本包保存两个 FY2025 完整公司—D04 原生结果：实际模型响应已通过完整请求集合检查、原生 Run / Review 重放与公共行生成，并已有复制包新进程 LIVE 冷读通过的记录。它不是正式发布、部署或全390验收。

| 公司 | 完整请求集合 | 原生 Result | 公共说明 |
|---|---|---|---|
| Ford Motor Company | 11/11；复用原第70次成功，新增72–81共10次成功 | `sha256:9581bcb5f55170cdc084263fc2533f16eb772fd9b56229756d7b61f5bbf11fdb` | FY2025，`TEXT_QUAL`，已检查范围内未披露持续经营疑虑 |
| Pfizer | 11/11；新增83–93共11次成功 | `sha256:489a0c23081f27d8b8123a1493544aed2760ce736fc4fc9e6c22882a01e273ca` | FY2025，`TEXT_QUAL`，已检查范围内未披露持续经营疑虑 |

两个 Result 均保持原 `WITHHELD / TEXT_V1 / NONE / D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE` 状态；公共说明由既有专用完整范围投影形成，不能将 `WITHHELD` 一概理解成实现失败，也不能据此放开其他失败或未决结果。原 Run 保持 OPEN，没有重签、改写或赋予正式发布信用。说明不保证未来财务状况。

## 调用与失败的原有意义

新增72–94共23次provider/paid调用：21次成功D04请求、2次失败B13请求，SEC新增0。原第70次成功只复用一次，不新增请求。

- 第82次 Enphase B13、第94次 Ford B13均保持 `FAILED_TERMINAL`，原错误均为 `B13_CALCULATION_LIMIT_CONTRADICTS_FINDING`。失败不能作为B13可用结果或未披露结论。
- 第69/71次已有单独历史原包，本包不重写它们；第70次在本包仍为其原请求、响应、收据及原执行版本。
- 截至第94次的累计计数为provider/paid/SEC **59/59/35**，对应剩余 **181/181/45**。这是through94对账点，不代表后续活动后的最新总账。
- 本次归档、还原和逐字节比较本身新增调用 **0/0/0**。D-36、零自动重试和原累计上限不变。

## 自包含材料

`material-index.json`将1801个逻辑文件映射到1003个唯一内容对象。`material-objects.tar.xz`为14,484,720字节（约13.81MiB），SHA256为`21e30f6584339db7c335f1499854fb759bd24c4479f48de24c8d2ca86ffc8ca6`。

**没有 `repository_path` 引用。** 后续修改V14/V15草案或运行模块，不会改变本包恢复所需的字节。

- `native/{ford_motor_company,pfizer}-D04/`：各自完整data、Run、公共行、汇总；包括该Run自己的运行模块和Requirement字节。
- `calls/0070/`及`calls/0072/`–`calls/0094/`：原Source JSON、语义请求、实际发出的请求、原响应、执行收据、终态及原执行清单；24份原始runtime `.tar.gz`均保留原字节。
- `execution-evidence/`：实际执行计划/统计/失败记录、两份LIVE复制包冷读记录、原执行及冷读脚本。
- `summary.json`：每次调用的身份、原Source/请求/响应/runtime SHA、使用量、终态及精确累计口径。

原调用终态声明的所有证据SHA已逐项核对，压缩包全部对象已读回验证。私有credential目录未纳入。完整原目录和已有 `.gz` 未修改。

## 实际还原与验证

`restore_material.py`是仓库既有还原器的逐字节副本，无新增打包平台。可在任意新外部目录还原：

```bash
python3 restore_material.py --evidence /absolute/real-material --repository /absolute/unused-repository-path --output /absolute/new/material-root
```

本包无仓库引用，所以`--repository`可以是不存在的占位路径。实际测试采用新进程、全新外部目录及不存在的repository路径；还原结果再与1801个原文件和完整索引逐项比较，结果见`restore-check.json`与`restore.log`。已有LIVE冷读记录位于恢复树`execution-evidence/live/{ford,pfizer}-cold.json`；此次字节一致性归档不重复业务执行、不增加调用或结果信用。
