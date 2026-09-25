# D04 历史路线接线（Issue #47）

## 做了什么

普通链路（#28）的 D04 本身不下判断：模型逐组审阅钉定来源的每一个单元（可见文本、原生 XBRL 事实与补充对象、本期全部 10-K/A），每个响应过冻结的逐请求接受（`d04_native_assessment.build_acceptance`：单元普查完整、原文引用逐字、程序自带的句子关系检查），接受后的发现组装成一个评估，分支决定是摘录文本还是"定义范围内无疑虑披露"，最后由 `capacity_text_results` 生成 Candidate、Evidence、Review 与 TEXT_V1 结果。Run 消费的是**已登记**的评估，能重推的一律重推。

本 Issue 把这条路线指向钉定期间，只改必须改的三处：

1. **来源**：`scripts/vnext/historical_semantic_source.py`（规则文件）。冻结构建器通过两个函数读"最新年报"，其后全部是这两个输入的纯函数；后继把输入显式化，函数体逐行照搬。**担保是机械的**：用例把冻结构建器的那两个读取指向同一份钉期输入，要求输出（含 `semantic_source_id`）逐字节相同——更早年份（Marriott 2023）、带 Part III 10-K/A 的前身年份（Paramount 2024，读 CIK 813828 自己的两份申报）、范围内的 B13（Enphase 2025）三例全等。B13 的适用公司从已批定义的标题读，不从 #28 的调用政策读——后者同时装着 #28 的预算与委托，从那里读会让本 Issue 的答案依赖另一个 Issue 的支出授权（与 `historical_capacity_results` 同一理由）。
2. **登记**：`scripts/vnext/historical_semantic_results.py`（规则文件）。#47 自己的登记，按钉期来源作键、写明 `issue_47_v1`，**从不消费为 #28 登记的评估**——那些键在 #28 的 Requirement 与来源身份上，消费它们等于把另一个 Issue 授权的调用记到 #47 的位置下（`../semantic-route-need/`）。接受链读的四个"计划"字段由请求本身推出，与普通计划构建器的算法相同；记录类型写明它是 #47 的请求绑定，**不是 WB-3 调用计划**。每个消费者都在当前代码下从登记的助手输出重推每个请求的 Candidate/Evidence 与组装后的评估，不等即按名拒绝。
3. **Run 接线**：`historical_results` 为 D04 派发、`historical_run` 安装时把登记副本作为额外输入放进数据根并在重建时读回、`historical_text_results.text_api` 把 D04 交给普通路线原样的 `capacity_text_results`。覆盖表把 D04 记为已接线（`WIRED_SEMANTIC_METRICS`）：没有登记评估时尝试按名停在 `HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:LIVE`（类别 `MODEL_REVIEW_NOT_EXECUTED`）——这是缺输入，不是缺路线，也不是缺披露。

## 两种模式

- **RECORDED_TEST_ONLY**：记录调用方提供的输出（测试的合成响应）。只证明从响应到 Run 的管道，从不证明任何申报的内容；**只在调用方点名时才被消费**。
- **LIVE**：批次默认模式；只有创建者日志（`.git/issue47-historical-assessments/`，数据目录与 Run 都写不进去）里的记录才被消费。**今天无法登记 LIVE**。

## 为什么没有 live 调用（`scripts/vnext/historical_model_session.py`，非规则文件）

live 会话按名拒绝，理由有两条且都写出来：

1. **没有许可**：`config/issue47_historical_model_calls_v1.json` 不存在；不借 #28 的额度。
2. **没有出口**：即便有许可，#47 也开不了提供方的 socket。WB-3 调用控制器（`invocation_control._prepare_successor_invocation_authority_from_requirement`）按 id 登记 Requirement 世代——issue_28_v2、R4 修订、issue_28_v14——其余一律拒绝（用例用控制器自己的拒绝**测出来**，不写死）；`tools/check_provider_egress.py` 固定仓库传输调用方的确切集合，唯一的语义调用方 `continuous_semantic_calls._Transport.send` 绑在 #28 的账本与委托上。两个文件都被冻结世代按字节绑定，给它们加 `issue_47_v1` 是改安全边界，需要单独审阅；本模块不绕过它。

## 绑定了哪些文件（`measure_executed_files.py`）

新进程跑一遍 D04 案例、Candidate、Evidence 与审阅单元，列出加载的每个模块与打开的每个规则文件（从第一次 import 之前开始记录，所以导入时读取也算）。`issue_47_v1` 原先未绑定其中 **14 个模块与 7 个数据文件**，全部是 #28 的原生语义路线——来源序列化、逐请求接受、请求构造及其按实测分组（DeepSeek 分词器决定一个请求在哪里结束）——父代 `issue_28_v13` 没有语义路线，所以一个都不是父代的。现已写进 mint 的 `AUTHORITY_ADDITIONS`；另加 B13 构建器导入的 `capacity_quantity_scope.py`（未接线，按"本世代规则文件导入的模块都要点名"的规则）。重跑后只剩会话模块本身未绑定——它不是 Run 的输入，是刻意的。**代价如实写**：#28 改其中任何一个文件都会移动本世代的 closure，和父代变动一样。

## 没有做、为什么

- **B13 适用分支（Ford、Enphase）**：来源已备好并与冻结构建器逐字节相同，但普通链路的 B13 请求合同还在 #28 里修订——基础请求的分类缺陷已在 #28 登记，角色/相关性变体是它尚未接受的离线候选——现在移植等于把模型调用花在其所有者都没接受的合同上。
- **D03**：普通链路没有 D03 的原生 Run 路线可移植（`normal_run_v3`：只消费已登记的 B13/D04）。

## 验证

- 仓库树：`tests/vnext/test_historical_semantic_routes.py` 21 个用例（来源逐字节差分、登记/加载/拒绝、Run 输入形状、live 按名拒绝）；覆盖表与期间结果回归 80 个用例通过。
- 运行树端到端（登记→安装→原生 Run→冻结→独立进程冷读→公共行）：`recorded_d04_run.py`，待正在跑的批次结束后在固定运行候选里实测，结果写入本目录。

## 不主张

任何申报的 D04 内容；live 调用能力；B13 适用分支与 D03。
