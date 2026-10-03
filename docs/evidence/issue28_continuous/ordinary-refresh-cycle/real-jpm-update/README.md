# JPM真实普通更新与固定实现下的重复触发

本包保留JPM/A08已有坐标的真实来源刷新：正常发现和获取入口取得10份SEC输入，原生Run和公共行返回`UPDATES_READY`。FY2025结果为`EXACT`、ratio `0.9115807340506899405928145595`，Result ID为`sha256:ec18c3291d84095ae0b72dda804584b833d3541d09ed3bdbdaa640c0f87021cb`。

这是已有坐标的更新验证，**不是新增第3个完整公司—指标坐标**，也不是正式发布或390验收完成。

## 固定运行时与历史保留

成功尝试`1c790b639d3741579d8016c55e5a9866`与重复触发`f2cda474084e4190a9c0b93104bcf1ec`绑定同一Requirement closure：

`sha256:3bc83d8a60995bb38ed2843eb2e2d51476ab57f1740ee0b6b6eea8c936f23dbc`

重复触发返回`NO_SOURCE_CONTENT_CHANGE`，继续引用原成功ID，`new_candidate_created=false`，来源和模型新增调用均为0。该记录只验证这版固定实现；后来主代码或绑定升级不继承此次repeat验证。

`execution-evidence/current-real-ordinary-update-first.log`保留修复前初始化失败：获取侧试图向不可变source-inputs安装已变化的`ordinary_public_projection_v1.json`，在第一个SEC请求前被`Immutable receipt bytes differ`拒绝。原失败没有删除或改成成功。

## 实际调用账

- 原固定calls/0095–0104全部SEC成功，每次零自动重试；provider/paid/SEC新增 **0/0/10**。
- through104累计为 **59/59/45**，对应剩余 **181/181/35**。这是明确的历史对账点，后续活动继续计入同一总账。
- 本次归档、实际还原与SHA比较新增 **0/0/0**；不重跑业务、不改总账。

## 自包含归档

`material-index.json`将795个逻辑文件映射至673个唯一对象。`material-objects.tar.xz`为8,352,516字节，SHA256为`64aeadc52f0c407ece27feda0ccfecf94519936731a0c92e1f2abcf1fb64be74`。

没有`repository_path`引用，后续仓库变动不影响还原：

- `state/`保存完整原更新状态目录，包括成功候选data、Run、公共行、来源与获取检查点、原运行代码/Requirement，以及repeat历史。
- `calls/0095/`–`calls/0104/`保存全部原SEC计划、收据、请求终态、原body/headers和原执行清单；原runtime `.gz`字节不变。
- `execution-evidence/`保存真实协调入口结果/日志、失败初始化日志，以及同一3bc固定运行时repeat JSON/日志。
- `summary.json`保存精确结果、尝试身份、调用原件SHA和计数口径。

没有复制会继续增长的固定source-inputs整根或任何private-credentials目录；候选自身包含它实际需要的完整原件、源码和检查点。原固定目录、原Run、原调用及原压缩包没有修改。

## 实际还原

`restore_material.py`是既有还原器的逐字节副本：

```bash
python3 restore_material.py --evidence /absolute/real-jpm-update --repository /absolute/unused-repository-path --output /absolute/new/material-root
```

实际使用新进程、新外部目录及不存在的repository占位路径还原，然后逐项比较795个原文件的字节、SHA、大小和完整状态/call文件树，见`restore-check.json`和`restore.log`。这份归档不授予部署、active切换、长期运行或正式采纳权限。
