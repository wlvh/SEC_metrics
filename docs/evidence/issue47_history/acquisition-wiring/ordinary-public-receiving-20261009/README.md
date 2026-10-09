# 原历史SEC账本的公共调用接缝接收

固定公共PR94/20398f3e，接续原一次EX99/零重试，不增加用途/额度。实际原根SEC_metrics-issue47-sec-ledger-resume-20261006保持，只读检查不构造Capture、不加锁或写账本。

原HistoricalCallLedger.snapshot .486s核1547槽+224保守数=1771、blocked为空；原binding限1354保持。新company_online._ledger显式E01上下文/snapshot/check_request 1.476s核有效1354+513=1867、窄用途1772，claims SHAa238db91…1262、2531日志；指定URL通过，错URL及refresh均OUTSIDE_BOUNDED_PURPOSE，counter主要文件/镜像/resume/CSV/manifest前后相同。运输配置身份已验证、不输出contact，旧CSV是当前14列；读库测试不代替真实根核查，不等于GET已执行。

向实际Capture.get请求前路径再做内存预检：不构造Capture/transport，claim/socket调用即失败，原上下文没有requirement_closure_hash，该函数无条件读取该字段而在claim前KeyError。历史claim只用requirement_id；不编造hash或重铸旧包绕过，不报缺新许可。公共#28已收到此具体迁移缺项，修后重做这一受影响预检再决定原获准动作。旧counter和单次机会未消费，原模型35等不动。

所有操作新增SEC/provider/paid/Run/接受0，完整旧计划/响应/slot/失败保留。原许可仍是指定Paramount FY2024附件、最多1GET、retry0、1771→最多1772，UNKNOWN不重试。源只有开发用途，不回填旧Run或复用旧模型额度。代码只在独立接收worktree使用，未修改公共作者树、主分支或实际active。
