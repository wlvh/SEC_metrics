# C04：稳定来源路径下的两份合法保存版本

本方使用已安装的固定 #54 `2a642e56a8e2f88c884c92cd350cf742f5dd8cfa` 普通运行时，补查此前未覆盖的**合法来源版本切换**。本次最新读取的提供方为 `303d751f29e57dc68ab7848b6b184dc4ab8c4b83`；其 D04 后继不要求重装或重跑此未变 C04 消费代码。运行时 `issue_54_v1` 闭包仍为 `sha256:a696cae10ff914708fcf8f4f7dce0f19ae2ba8523a0eff1ff47eeb62a27a598c`，五文件与既有安装逐字节相同，见 `runtime-identity-reuse.json`。本方实际执行树为 `decd85a245534ed05b3536ba9b92100d74311c48` 加本目录未提交测试脚本，不能称作后续提交SHA已经执行。

## 实际输入与结果

准备端从原完整基线导出 Marriott C04 原件包；另一份直接复用先前已经认证的完整52次捕获公司包。两者的原日志 SHA 分别为 `709b97c9af73ced88571d2b69b226e2a197fa2ec9223c16a11f2420b3605bec2` 和 `1c9f81687e591f07f745ca5bf4543af70ef26af146cc7746859d515a1d4e18e6`。没有从52次历史删行生成“旧版”，没有拼接旧/新原件、重编号、重复获取或新增额度。源包不含旧AI登记、`records.jsonl`或模型回答；信任来自独立的准备端 `source-trust`，不是包自行授信。

公司状态根是 `/private/tmp/issue28-company-consumer-20261003/state-marriott-c04-source-switch`，两次安装的实际 `source_root` 均为其 `source/`。`company_handoff.install_company` 与 `company_compute.compute_company` 共享公司锁；C04 专用 journal 固定于 `updates/metrics/C04-registration-v3/`。本次串行执行证明该路径内的版本切换，不声称已经实测多进程并发、存储故障或 OpenShift 挂载。

| 实际动作 | 耗时 / 结果 |
|---|---|
| 原基线导出 / 安装 | 2.790 / 0.539秒；没有新捕获 |
| 原基线 C04 计算 | 31.338秒，`CANDIDATE_READY`，Run `b3c4c8fd…`，Result `a5517d36…` |
| 52次捕获公司源安装 | 0.825秒，同一稳定路径；原 checkpoint `b3b341c8…` → `ba44ffa2…` |
| 更新后 C04 计算 | 42.763秒，`CANDIDATE_READY`，前驱为原成功 attempt；Run `8e44490b…`，Result `d41ffcee…` |
| 再次触发 | 12.641秒，`NO_SOURCE_CONTENT_CHANGE`，同成功指针，无第三份 Run |
| 独立进程重放旧 / 新安装 Run | 7.533 / 8.349秒，原生重验及两份公开CSV逐字节一致；各 attempt 文件前后SHA保持 |

两个结果都属于 FY2025、数值为0。这里没有新财年输入，不把来源版本差异当作跨财年更新；也不把运行重放等同于对审计师事实重新进行全面内容验收。新结果与先前已生成 `d41ffcee…` 同身份，并非新增正确公司结果或390坐标。Run 保持私有 OPEN，无正式采纳。

## 本次信用与复用

本次程序路径为 `company_compute.compute_company` → `c04_update_cycle.run_company` → 已有 C04 四形式后继 → 原生 Run/公开行。旧 Run 保存自身完整输入和规则快照，切换运行时来源视图不会改签旧 Result。`cold_read.py` 在切换之后的独立进程重建旧、新安装输入并逐字节对照行，区别于只看当前汇总JSON。

实际写入限于本方外部准备包、独立信任根、公司状态根与测试日志。计算/导入进程使用既有 Python 文件和网络守卫，拒绝读取原 checkout、真实调用账本及准备 Git 树，拒绝程序目录写入；`-B` 禁止缓存写入。原账本顶层文件、来源日志及正式 active 前后SHA相同，provider/paid/SEC真实新增为 **0/0/0**。这不是内核级隔离、动态UID、只读挂载或 OpenShift 集群实测。

复用此前首次 C04 计算、无变化重入、错误公司导入失败保留与恢复材料；没有重复执行这些未变场景。本次新增验证只覆盖两份**合法真实保存来源版本**在同一更新历史中的切换、前驱保留及双版本冷读。未修改 #54 工作树/算法、#47分支、真实账本、调用用途或生产入口。无新产品源码，父会话材料执行不冒充新的限定独审。

实跑脚本为上级 `consumer-c04-source-switch.py`；原始阶段日志、`summary.json`、`cold_read.log` 和运行时身份文件区分实际执行、既有身份复用与尚未验证边界。旧原件与两份完整来源日志保持原身份，不将单公司目录解释成独立真实额度。
