# 第 94 次已拒响应：独立来源角色拒绝覆盖诊断

原始 Ford 请求、完整来源、响应与 FAILED 终态只读保存；本目录变体仅为合成诊断，零 provider/paid/SEC 调用，不构成真实成功、完整 Run 或坐标结果。

- 原响应拒绝 `B13_CALCULATION_LIMIT_CONTRADICTS_FINDING`。
- 仅去掉矛盾的两条 production-not-present limit，保留 423/697/699/700/701/849 的质性句 `ACTUAL_PRODUCTION`：真实 `validate_response` 接受且无未决。
- 改六条质性生产为 `OTHER_CONTEXT`、保留 476/669 行业容量 `TARGET_REGISTRANT`：仍接受且无未决。
- 将两条行业句改合法 `OTHER_ENTITY` 主体且保留原引用：也接受。

因此当前内容守卫的数量检查只有“读出明确数量就要求正确分类”的方向，缺少“数量类分类必须有来源量证明”的反向要求；行业主体分类也缺独立支持证明。原失败没有变成生产误输出；完整 Run 尚未探测。建议复用已存在的有限量证明，并将不支持的量句式保留具体实现未决，禁止把任意数字或模型理由当成数量证明。

`result.json` 保留六原文件 hash、实际 HEAD、受测模块 hash 与各变体结果。`check.py` 可离线重跑；当前仅调用真实 validate_response，不改原文件。
