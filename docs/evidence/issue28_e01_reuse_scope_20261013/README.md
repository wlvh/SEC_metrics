# E01：无关 D02/分派变化后，复用既有稳定扣留

## 已恢复的用户路径

正式 `run --period fiscal-years --metric E01` 现在可以继续读取原 Pfizer FY2023 任务的稳定扣留，不因为未使用的 D02 页眉规则、已核对的 B04/B07 分派或 D02 登记变化再次抽取/计算。独立 `results` 仍显示 `WITHHELD/null`、原期间和冲突原因；这没有解决全年并购计数，也没有将历史条目计数提升为新口径正确结果。

本批原始输入是 [#47 已提交的实际反例](https://github.com/wlvh/SEC_metrics/blob/0d4713de6127785ea5f04130e65978b3726ff786/docs/evidence/issue47_e01_main6efe_receiving_20261013/README.md)，其原失败及三文件差异保留。本方负责公共控制器/比较，历史方负责消费，不新增历史控制器或竞品实现。

## 实际根因与改动

已核对固定 `db403009be17f71fb5ca08c965e07d21e7363fe2` → actual main `6efe086455693abbc0fc9d54cbe54b5286a84877` 的源码：

1. `d02_text_results_v3.py` 的变化只影响 D02 原文/页眉选择，E01 原事件路线及内容确认路线均未调用；它却在共同基础清单里。隔离回归先红。只对 E01 从比较输入移除该项；D02 仍保留并在变化时失效重验。
2. `ordinary_current_update.py` 新增的是 B04/B07 处理文件登记；控制器的检查版本本来就已从业务比较剔除，不把其 digest 变化另算一个实际触发原因。
3. `ordinary_saved_result.py` 只新增 B04/B07 默认分派；历史 E01 使用自身 case 和未改的保存函数。另核对 [PR247](https://github.com/wlvh/SEC_metrics/pull/247) 的 writer，差异仅再登记 D02 explicit case，亦不改变 E01。这两份已知 writer 字节在既有有限兼容函数里显式支持。

兼容仅限 E01、已知旧 comparison 版本、这两种确切已检查 writer 及相同的其余配置。来源根、公司登记/主体、Spec、parser/Calculator、实际 producer、原请求/回答、声明依赖等仍逐项比较。未知 writer 或旧比较版本、其他指标、相关规则/范围变化均不能走这个例外。来源检查和已保存的新口径 E01 scope 检查仍在每次复用前执行，不改旧 Result、原件、回答或账本。

这是已保存任务的有限接续，SHA 用来区分已调查的缓存转换，不是 clean-tree/exact-head 权限门、批准防伪或新的治理平台。未来未知变更仍正常处理；本批没有普遍忽略保存模块或删掉所有哈希。

## 实际验证与副本边界

原实际任务位于历史方开发材料的 `e01-item-conflict-state-20261013/state`。读取时已经有19个文件，包含对方先前构造的禁止计算失败记录；本方没有将它改回17文件或删除失败。只读复制到本方 `issue28-development-evidence/e01-reuse-scope-marker-fixed-20261013/state` 后运行，旧 Result 七文件和原 SOURCE 始终保持。

实际完整来源根仍由原 `company-task.json` 指定；没有重取 Source、替换事实或手工改旧 completed-check。原注册表、请求日志和 manifest 的哈希逐项对照，结果见 `actual-reuse.json`。本方原任务副本只增加正常检查和更新比较状态；独立读取不写状态。

正式用户 CLI 的 producer/source/request/Calculator code objects 设置“调用即报错”，网络、SDK send 和模型/SEC 申领亦禁止。不是把整个函数返回或子进程 mock 成成功。

| 实际步骤（同机器、同副本） | 耗时 | 结果 |
|---|---:|---|
| 首次修后兼容检查 | 0.572s | `PREVIOUS_INPUT_WITHHELD`，明确 E01 兼容说明，零抽取/计算 |
| 再次相同输入检查 | 0.567s | 同结果、零抽取/计算，无第二个结果目录 |
| 新进程 results/CSV | 0.221s | FY2023、CIK78003、2023-01-01至12-31、WITHHELD/null、同完整 Result ID |

两次 run 返回码2是明确有扣留的公司流程，不当作成功或运行异常。Result 保持 `sha256:cd0f882fecd887de87c48ebe35c6020bbdf8a6ace404aba18c4334bff9207553`，原因 `E01_ITEM_METADATA_BODY_CONFLICT`；申报 header2.02 / 可见正文2.01 的关系不反写。原7结果文件、原19任务文件和来源元数据均未变；最终独立读保持本方23状态文件。没有年度计数、没有匹配模型响应信用。

`verify_reuse.py` 给出可直接执行的正式 CLI 复现器，需提供本方/审查方独立的状态副本、新输出目录和原任务只读路径。材料来源见上游记录，不复制原 Source 或接收信用到仓库。

```bash
PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue28_e01_reuse_scope_20261013/verify_reuse.py \
  --state-root /absolute/review-copy/state \
  --original-state /absolute/original-review-task/state \
  --output-root /absolute/new-output
```

定向组合125项/8.677s，零失败/错误/skip，涵盖配置、复用/恢复、E01 source/conflict、公共公司分派和读取。新增控制验证：E01不受 D02 变化影响、D02仍受影响；兼容不改输入；相关解析/Calculator/Spec、公司登记、实际 producer/回答、其他指标、未知 writer/旧比较版本均拒绝。

## 证据和剩余限制

实测本地起点 `25b92f7e35abcdd958eb5bbac5dca110ab0916ea` 加本批未提交差异，`tested-code.json` 记录实际生产文件 SHA；最终提交不伪称已在该 SHA 重跑。源码比对、真实 CLI 执行、读取历史方证据及推断分别说明；代码允许正常编辑，没有资格封存。

`before.log` 是 D02 无关依赖反例，`before-dispatch.log` 是旧 writer 兼容反例。第一轮已经正确复用，但沿用了旧 `FINITE_D04_DISPATCH_ONLY` 说明；该记录在 `actual-reuse-before-marker.log` 保留。修正为 `FINITE_INSPECTED_E01_DISPATCH_ONLY` 后，用新的原19文件副本验证，没有篡改旧运行。开头对“原任务仍17文件”的假设被现场19文件纠正，未执行复制前就拒绝，没有把它登记成程序故障。

当前代码仅修原稳定结论的复用；E01真正内容判断/完整全年结果、其他指标、自动更新和390责任仍未完成。新增真实调用0/0/0，原许可/额度/失败机会保持；作者不Ready、合并、采纳、部署或切active。接收方按实际固定组合复核。

接收main组合：实际main随后接247/248至e16ca316，保存模块为已核对的9f7版本。本方正常合入后再用原19文件的新副本走正式CLI，禁producer/Calculator三阶段仍成立，见main-actual-reuse.log与main-actual-reuse.json；原7结果/19任务/来源元数据保持。main-final-controls.log记录同一main组合125项零skip。没有继承6efe耗时或把247新增登记当一般writer放行。
