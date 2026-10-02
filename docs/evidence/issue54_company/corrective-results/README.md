# 公司持续结果出口与已保存 D04 接线收口

接续 e536cdc / PR55；用户的编排层复现仅含模拟的底层计算／来源／投影，本方未取得其 zip 原包。`partial-company-before.log` 独立模拟复现了 B01+D01 → B01 请求导致旧清单失去 D01。修后组件回归也明确模拟财报引擎；真实材料另列，不以短测数量替代完整验收。

已实现：最新请求报告单独保存；公司视图从原 journal／期间指针及 Run 生成；CSV 汇总既有投影并附来源、期间、运行规则、最新请求及有效性。查询不会制造候选，原消费者仍管理成功指针。旧值不能自动成为当前输入成功。精确已确认缺陷按既有登记扣留，公司表置 WITHHELD，原 native 字节保留。单项重放拒绝仍保留其它项；未提供业务缺陷登记不等于没有缺陷。

实际 Marriott FY2025：新独立 state，原核心 B01+D01 首算106.223s；B01-only 新进程17.580s、NO_SOURCE_CONTENT_CHANGE；D01 Run 未丢，修后公司 CSV 两行／两组 native，导出35.346s。首次新出口试验因把本进程 programme root 当成 external data 拒绝，已纠正程序路径检查，原失败材料保留。该材料不验收 D01 业务内容。

D04：原 review-5207290213 的完整六请求 RECORDED_TEST_ONLY，封印身份和旧请求／响应／接受保留。独立 SEC 来源包、独立处理包／trust、原版 V14 只读程序＋独立可写公司 state，生成原 native Run 和 TEXT_QUAL 行。原 Result 的 WITHHELD 发布状态保留；接线沿用原 project_defined_absence，不能称为正式发布或新真实判断。首次拒绝因只读复制的暂存目录权限；随后旧安装器无 current_runtime 参数；再因把 defined-absence 的 WITHHELD 一律阻断。各失败和修后345.981s计算阶段／原始报告均保存。未改原指标核心、未重新登记、未访问原采集 ledger。保存输入换目录重入139.883s、NO_SOURCE_CONTENT_CHANGE，未新增 Run；处理准备最终25.912s，原登记容器／请求响应字节不改。独立处理 trust 重复登记相同身份幂等，旧信任记录不覆盖。

读取 #28 [消费者回执5959346910](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5959346910)：固定2a642e56、Marriott C04 FY2025、其 own52捕获／重复无新 Run／错公司拒绝及1003旧文件保护。复用来源认证／导入／C04内核未变部分，不自动算本提交通过。253/e536相对2a的影响为历史／native独立安装分派、恢复和来源不带判断材料；本次再增加结果视图／汇总及独立 D04 处理入口，消费者应补这些接口，原 C04 算法和 journal 未修改。已在#28回链 [5960148666](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5960148666) 请求可读取的173–178完整 LIVE 材料；未取得时只限制该 LIVE 节点。

#47 固定消费者及历史程序继续沿用60c6b4d6/815c7820。实际追加FY2022 A08为759.946s，公司汇总冷导出383.138s、同时包含FY2022与FY2023；FY2023显示NOT_RECHECKED，未伪装成最近FY2022执行成功。保留原FY2023，不扩大为五年全部指标。其消费者尚待独立反馈。

e536cdc 主工作流37049750196所有16作业终态成功，生成检查37049750282成功；这是旧head，修后最终head CI另行记录。本期不部署 OpenShift，新增真实 SEC/provider/paid 0/0/0。动态UID／实际集群、全36项、独立业务验收及完整 LIVE D04 未测或待取得，不能由本材料推断完成。
