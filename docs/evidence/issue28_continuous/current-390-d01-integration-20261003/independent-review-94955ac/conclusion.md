# 94955ac D01 读取绑定新增差异限定独审

结论：**PASS_LIMITED_DELTA（本次新增差异未发现需修项）**。首轮三个错配均已由正常 `load_current_view()` 拒绝，四个必需证明逐个缺失时也拒绝；原两份精确候选可正常读取。`independent-review-7d1202b/conclusion.md` 的历史 **NEEDS_FIX / 1项P2** 保持原义，本报告只确认本补丁对该接线缺口的修复。

- 精确 SHA：`94955acf434c1ca177718aba35927f205da7ff70`；增量 base：`7d1202b06f426ed3fc479c7be4f075327267971e`。
- UTC 起止：`2026-10-02T23:02:47Z` → `2026-10-02T23:06:08.932294+00:00`。
- 工具调用：**12**（5 次 functions.exec + 7 次 exec_command，outer 与 nested 均计）；普通消息 **1**（本次最终报告），问题 **0**，最终报告 **1**。
- 开始、结束均固定同一 HEAD；六份指定输入的实际字节均与本 SHA 一致，详见 `inspection.log`、`final-verification.log`。开工已有 execution-state.json 本地修改，本审阅未修改。

实际审阅只覆盖 `current_view.py` 的新增联合绑定与必需证明集合，以及 `test_current_view.py` 新增四项真实入口对照。这里的联合绑定，是确认同一公司/指标/期间、Result、Run、需求闭包、安装执行根和验证收据确属同一条已核验运行。读取器先要求四份证明路径完整，再核文件摘要；随后从固定摘要的机械汇总按正式 company_id 取精确条目，比较 Run/Result、需求闭包、安装根及收据完整对象，并核原生 Result 的主体、指标、起止日期和显示 Spec。各对象自身 ID 有效不再足以拼出“已验证”状态。

亲测授权命令：
```text
/private/tmp/issue28-tokenizers-venv/bin/python -B -m unittest -q test_current_view
Ran 12 tests in 0.122s
OK; exit 0
```
日志为 `unit-tests.log`。新增四项均实际进入 `load_current_view()`；只在内存替换待读 delta，其余文件读取、摘要检查和组装照常执行，未修改实现或原 delta。

另独立调用同一正常入口做有限对照，详见 `independent-reader-probes.log`：

1. Paramount 真实新 Result 配 Marriott 的真实 PASSED 收据：拒绝 `D01_DELTA_VALIDATION_IDENTITY_INVALID`。
2. Paramount 新 Result 配原390里的旧 Run：同样拒绝。
3. 保留 Paramount 坐标/前驱，换入 Marriott 原生 Result、对应 ID/收据和显示字段：同样拒绝。
4. 四份必需证明分别移除：四次均拒绝 `D01_REQUIRED_PROOF_SET_CHANGED`；额外证明路径也拒绝。
5. 修改机械汇总预期摘要：拒绝 `D01_CURRENT_PROOF_BYTES_CHANGED`。
6. 分别改变安装执行根、需求闭包、显示 Spec 闭包：三次均拒绝身份不一致。

独立负例共 **12**，均被指定入口拒绝。正常无改动读取实际选中 Paramount `6795449bafa12651099b226e569ad3b2882f72a89cd317adb559c8096058afdd` 与 Marriott `99c76e50d0fb19cd6116a80350a6f1ca38924b5731e812695484d28381b348f8`；亲核两行与各自机械条目的 Result ID、Run ID、收据完整对象及原生显示正文一致，且仍标为保存范围的内容/机械验证、无正式采纳信用。完整入口读取输出仅保存于本目录 `view-read.log`，不把其390行数量当成新完成390内容验收。

复用首轮未变部分：两份精确原生正文/manifest/原期间核对、76条标题原件阅读、两份机械副本七项检查、旧390和prior deltas以及缺陷扣留结论。本次没有重读原件标题、重跑安装验证或重审未变视图全体。输出继续声明 `all390_acceptance=false`、`full_current_head_reexecution=false`、`other_coordinates_newly_validated_by_this_delta=false`、`production_authorized=false`、新增业务调用 `[0,0,0]`。

边界：仅本 SHA 新增读取接线通过，不授其他 D01、新来源/版式、390整体、全部 PR、CI 或生产验收信用。只读实时 Issue28；未发外部评论、未 spawn、commit/push、业务请求、全 fast/长链、tar，也未改 #47/#54 现场或账本。所有落盘都在本独审目录，一个 .md 结论及 .log 日志；无资源超限或任务范围内未覆盖项。
