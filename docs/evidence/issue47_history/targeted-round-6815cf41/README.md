# 定向运行：E01 十二个期间（运行树闭包 `6815cf41`）

## 跑了什么

所有者 2026-09-27 采用"经内容确认的并购公告"之后，E01 的后继路线在 `629f1ed8` 补上确认契约、在 `460695ef` 改正行注释。本轮在带注册补丁的运行树里、按默认 LIVE 安装，把十二个有原件的期间各跑一次（`run.sh`，驱动沿用 `../targeted-round-30a7934b/targeted_runs.py`）：安装、原生 Run、冻结、公共行、另一进程冷读。零 provider / paid / SEC 调用，没有消费任何记录模式的确认。

**这不是全量帧**，也不是 base 合并（`469b437a`）之后的闭包；结果编号只依赖 Spec 与输入，不随父代闭包移动。

## 结果（`rerun-results.json`）

| 答案 | 期间 | 数 |
|---|---|---|
| `PUBLISHED` 0（窗口里没有 1.01/2.01/8.01 候选条目，路线自己的匹配器答 0） | Enphase 2025 | 1 |
| 按名扣留 `HISTORICAL_E01_CONTENT_CONFIRMATION_NOT_REGISTERED`（有候选条目、没有登记的确认） | Ford 2025、Lumen 2025、Macy's FY2025、Marriott 2025、Paramount 前身 FY2024、Pfizer 2025、Southwest 2025 | 7 |
| 来源缺口 `HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED` | Marriott 2023、Marriott 2024、Paramount 2025、Salesforce FY2026 | 4 |

十二个 Run 全部冻结、出公共行，另一进程冷读得到同一 result_id。

## 接受

Enphase 的 0 由 `tools/read_e01_candidates.py` 独立读出（`../content-acceptance/e01-content-confirmed-read.json`）：它从账本里最新保存的 submissions 索引列出窗口里的 8-K，逐份从各自的 SEC 头文件读条目代码，不调用路线的来源发现、声明构造或条目读取；两种窗口读法下都没有候选条目、头文件全在，才接受。接受绑定在后继路线的 Spec 闭包（`49ada0cc…`）上；旧口径下对同一窗口的接受（`7d5864cc…`）照旧留在登记里，互不授予。登记 183 → 184。

七个扣留的窗口需要真实的内容确认才能产出值，那是模型调用申请里的 E01 授予（`../model-egress/call-application.md`），本轮没有、也不能替它回答。
