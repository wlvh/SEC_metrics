# C04 相邻财年录制演练：旧期输入未成立

沿既有[相邻年报原件清单](../c04-adjacent-year-inventory-20260927/README.md)选择 Marriott FY2024/FY2025。两份年报正文属于已保存原件；原 #28 来源根没有较新年报提交之前保存的 submissions 响应。本演练在禁网录制根中，从 SHA-256 为 `e3eeefe33c9c7351788d22a96ca36d061230cd2dacadbf44ed6ef79035742bd8` 的真实保存 submissions JSON **构造**一个旧时点版本：只移除较新年报申报日期及之后的 recent 行。构造体 SHA-256 为 `5b542458aa0fa1c759eb2ff6d40b9f03520521103253ebbfaab7c5c132a2b8aa`，不是曾由 SEC 实际返回的原件。

`rehearse.py` 使用项目原录制 SEC 会话、真实来源发现、C04 后继更新控制器与原生 Run，禁用 socket/DNS/HTTP，先登记构造的旧元数据，再登记真实保存的当前元数据。`run.log` 和 `result.json` 保存三次结果：

1. 旧元数据下，C04 为 `INPUT_FAILED / C04_REGISTRATION_BASE_INPUT_UNRESOLVED`，没有旧期成功候选。首次日志只写了顶层状态，`prior-diagnosis.log` 另从同一材料限定重跑旧期并读到真实 terminal 错误；它也列出了约20个待获取 URL，包含前期目录、代理材料及当期事件正文/头文件。仅凭该列表尚不能把所有缺件逐一确认为唯一根因。
2. 换回真实当前 submissions 后，FY2025 C04 生成 `CANDIDATE_READY`、原生 `PUBLISHED/0` 私有结果；这与现有当前期能力一致，不算新增公司或390坐标。
3. 重复触发为 `NO_SOURCE_CONTENT_CHANGE`，保留同一成功候选身份。

所以本次**没有证明**旧成功版本→新财年成功版本的更新或旧期失败恢复，也没有独立进程冷读。测试根是暂存目录，结束后已清除；`result.json` 中的临时 `rows_root` 仅为当次执行路径，不能再回读。执行时录制账本计两次模拟 SEC 请求，原真实 provider/paid/SEC 总账增加为 `0/0/0`。没有把裁剪元数据冒充真实历史响应，也不为演练补抓约20个旧期文件。要得到真正跨财年验收，还需具备已认证的旧时点完整来源及后来新年报的真实变化序列，或在另一个已保存且完整的相邻财年对上演练。
