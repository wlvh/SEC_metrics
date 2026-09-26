# Marriott C04 首次真实来源刷新

在已推送`2f3a36da`、限定独审`PASS_WITH_BOUNDS`及当前接线收据通过后，原Issue #28账本用`tools/vnext_ordinary_refresh.py`执行了一次业务申报清单GET，`max-sec-requests=1`、`max-provider-requests=0`、SEC自动重试0。URL为`https://data.sec.gov/submissions/CIK0001048286.json`，它在执行前的Marriott当前C04原生来源证明中。原账本第193槽真实SEC终态`SUCCEEDED`，累计由143／143／49变为143／143／50，调用归属0／0／1；完整收据、原响应和新增来源保留在原账本，`real-first-summary.json`比对了提交报告与不可变收据/终态。没有模型请求、账户操作或生产发布。

新清单改变来源身份后，C04形成新的`CANDIDATE_READY`、原生`PUBLISHED/0`候选，Result为`sha256:d41ffcee4edd8898ab66931441b7cdc850c64b589fa9e2974d4b87cb59aae70e`，旧成功尝试仍被引用。该结果只表达规定范围内的审计师变更口径，并非完整390或正式采纳。整体刷新仍为`UPDATES_INCOMPLETE`：此次只准一个SEC槽，Company Facts还未在本轮刷新。

来源变化后重新运行发现与C04输入核对，29项当前发现的URL仍各在C04来源证明内，Company Facts亦在内。`after-first-source-map.log`原先断言“下一次普通调用会直接选择Company Facts”失败；实际`_pending()`会在新一次调用里重置已尝试集合，再次先选申报清单。**不要原样再运行一次`max-sec-requests=1`，否则会重复付费获取已取得的URL。** 这是有界调用跨次恢复的程序缺口，不是新来源真实性失败或用户许可不足。该失败日志保留；下一步应在原账本已存收据上做受限续接，或由现有控制器安全地证明跳过前一URL，再申领真正待刷新的Company Facts。未来新清单若列出新URL，需重新核对来源范围，不自动沿用本次29项集合。

首次真实调用的原生新旧版本独立禁网冷读见`cold-read-real-first.log`。本目录不打包账本原件，不重签历史，不把一条成功GET或C04候选当作本轮元数据刷新完成；总上限240／240／80仍不变，SEC剩余30，模型/付费剩余各97。B13 V6停用、D03无真实调用及正式生产边界继续有效。
