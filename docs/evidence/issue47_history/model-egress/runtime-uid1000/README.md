# 固定包在 UID 1000 容器中的开跑阻断

2026-10-03，Codex 执行环境 `/workspace`。开发起点 `68025386`；固定包是 `5640c367` 加注册及出口补丁，再重铸快照。新克隆的 20 个收据绑定文件逐字节匹配；22 个位置的 35 个请求摘要及请求体计数匹配，参考输入合计 3,037,062 token，收据 `sha256:316100f62eb71a66fec467b2366a64e0f4d7eb32453db972fcb84b67eb6defe4`。

`register-approval --approval-url https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5970103848` 成功；GitHub 原始记录作者 wlvh、OWNER、`performed_via_github_app: null`，创建与更新时间同为 2026-10-03T14:29:31Z。8,913 字节与原批准正文匹配，SHA-256 `9a368413797ddef13ecaf98dfa9f4f3b55a6a8db6f035605f761828e38883e6c`。登记仅写在固定运行包，未安装到开发检出。

随后 `python3 tools/vnext_historical_model.py start` 在检查本地启动记录时抛出 `PermissionError: [Errno 13] Permission denied: /root/.local/state/sec_metrics/.issue47-historical-model-cloud-v1.start.json`。当前身份 `uid=1000(agent)`，无 sudo。没有创建启动记录，没有发布标记，没有认领或发出模型请求；本会话 provider/paid/SEC 为 `[0,0,0]`。没有使用、打印或保存对话提供的密钥。

## 可审阅的最小路径修订（未获批准）

`approval-comment-body.proposed.json` 仅把 `budget_root` 从 `/root/.local/state/sec_metrics/issue47-historical-model-cloud-v1` 改为 `/workspace/work/issue47-historical-model-cloud-v1`。其余字节不变；8,898 字节，SHA-256 `63fe811cd5a0de2c7b1bf993ecf04d3172ddbbd672e0cb1b4346fae30854e7e1`。它不是许可，也未安装或执行。

所有者可选：换到可访问原账本路径的环境，沿用原评论；或本人在 Issue #47 发布这份完整修订正文，执行者再按当前机制记录新正文身份、重建固定代码包并登记。执行者不能代发批准、改写原评论或仅凭自己换路径继续。代码、补丁、收据、请求、额度、顺序和停止条件均不因此改变。
