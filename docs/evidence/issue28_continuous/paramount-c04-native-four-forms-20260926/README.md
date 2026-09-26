# Paramount C04：四形式保存来源的显式后继原生 Run

本目录只处理已有的 C04 技术缺口：普通 v2 路径仅接受 `8-K`、`8-K/A`，而同一注册人当前保存的材料还包含 `8-K12B`、`8-K12B/A`。这些原件来自原 #28 SEC 总账，四份变体正文/头文件已按第105—108槽验真；本轮没有新 SEC 或模型请求，也未读取 #47 的账本。`base-snapshot.json`用 `git show b4d21130`记录修前未冻结 V14/V15 绑定，旧冻结父级及旧 Result/Run 原件未修改。

先前一次尚未提交的尝试直接扩展普通 `normal_governance_input.py`。需求加载立即报 `Normal candidate rule bytes differ: scripts/vnext/normal_governance_input.py`，表明该文件已由冻结父级逐字节绑定。该尝试的源码及部分需求改动在提交前撤回；本次最终差异改为新增 `c04_registration_successor.py`，调用旧读取器准备年度审计师事实，并以旧 `_filings()` 验证的元数据重建四形式原标签。新模块独立核对完整申报清单、每份 header 的真实 `<TYPE>`、primary/header 的既存请求证明、期间、同 CIK、来源集合及22条 Item 候选。旧 `governance_signals.py`、`normal_governance_input.py`、`normal_candidates.py`、`ordinary_remaining_cases.py` 保持原字节。

显式后继 Spec 为 `C04_auditor_changes_v3.md`；普通 `normal_run_v3` 只有调用者明确传入四形式选择时才进入新路线，默认两形式路线与 `_binding()` 函数体未改。当前未冻结的 v13/v14 快照及父级引用随实际代码同步，最终闭包分别见 `binding-after.json`。这会更新**新创建**运行的需求身份；旧安装包仍按原快照读取，不能把此事说成历史 Run 重签。共享增量需以 `[shared-with-#47]` 标记并由 #47 执行者自行处理堆叠分支；本轮未修改其代码或快照。

第一次禁网安装/运行到主进程成功，但独立冷读发现新后继模块引用了安装包未包含的发现模块，见 `native.log`。修补为在新增模块内复用旧 `_filings()` 做有限形式验证后，另以全新隔离根重跑。`native-repair.log`、`summary.json`、`cold.log`证明六份同 CIK 当前财年事件申报（其中两份注册变体）、12份正文/头文件引用、22条来源绑定 Item 候选进入 C04 原生 OPEN Run 与两份公开格式行；安装副本的独立进程禁网且禁止子进程，回读 Result ID 和公开行字节相同。实际运行根为 `/private/tmp/issue28-c04-four-form-20260926-02/data`，来源根为原账本 `source-inputs`。第一次失败根未改写，成功运行使用新根。

原文中没有已认证的本注册人 Item 4.01，且缺同 CIK 前期年报可比审计师事实。因此结果严格为 `C04_COMPARABLE_AUDITOR_FACTS_MISSING`、值 `null`、公开状态 `WITHHELD`；**没有给0或1**，也不推断没有更换审计师。该 Run 是隔离开发候选，不是正式采纳。没有同 CIK 前期10-K时能否采用另一条充分原件支持的否定路径，仍是业务决定；这次只完成既定四形式技术接线，默认普通自动更新尚未自行选择此后继。

`directed.log`中显式新旧路径及错误选择2项通过；此前冻结来源/解析18项指定正反例和普通Run权限4项通过，终端输出分别由本次执行读取，未冒充全套重跑。`provider-wiring-test.log`和`sec-wiring-test.log`分别在最终 V15 闭包下实际走模拟提供方工厂/控制器、录制 SEC HTTP/失败隔离；两项各1项通过，无外网业务请求。`archive_current_wiring.py`先逐份验证旧证据字节，再将新日志加入新的 provider/SEC 禁网收据，`wiring-final.log`记录当前执行权限哈希通过。真实调用前仍须按当时最终绑定再核验。

原总账在原生测试前后均为 provider/paid/SEC `143/143/49`、192槽；本次新增 `0/0/0`。本目录的运行、来源内容判断、两个收据和共享增量仍需指定 SHA 的限定独审及新 head CI；旧 C04 v2 和其他指标历史成功不从此录制候选继承信用。#47/PR52、生产指针和发布入口未操作。
