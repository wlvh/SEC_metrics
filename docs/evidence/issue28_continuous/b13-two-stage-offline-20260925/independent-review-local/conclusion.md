# B13 两阶段历史对照护栏：限定差异独审

- 审阅补丁：`79fe67b197c601d387fc9464f7a7ff3358fb65b3`，相对 `99d868f52cf94d42966c28175d840e5a10917a2e`。
- 范围：仅 `capacity_two_stage.py`、`test_capacity_two_stage.py`、V14 `baseline_manifest.json` 的此次差异；继承 `../independent-review-native-repair/conclusion.md` 的旧反例。不重审旧双阶段长链、全 PR 或真实模型准确性。
- 结论：**NEEDS_FIX（P2，新增误拦截）**。这次补丁关闭了已知两条“历史对照 + 当前合同制造产能”句子的错误排除路径，但把同一块中仅属于其他主体的真实产能误判为当前目标主体产能。原 V4 验证器接受的正确排除因此在新增护栏被拒绝。

## P2：目标主体线索与其他主体产能跨分句拼接

限定复现的完整可见块是：

> Our contract manufacturers previously had limited output; a supplier has manufacturing capacity for its own products.

第一分句只说合同制造商过去产出受限，没有目标主体当前产能断言；唯一的 `manufacturing capacity` 明确属于后一句供应商。扫描候选包含该块，第二阶段给出 `other_entity / OTHER_ENTITY / CURRENT_REPORT`，全部来源单元已审阅、无未决。用同一来源和响应比较两个提交的验证器：

| 代码 | `_direct_current_target_capacity()` | `validate_interpretation()` |
| --- | --- | --- |
| `99d868f` | `False` | `ACCEPTED`，`unresolved=[]` |
| `79fe67b` | `True` | `B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW` |

原始复现结果见 `adversarial.log`。补丁在 `capacity_two_stage.py:84-104` 去掉整句的 `previously` 排除后，`direct.search(statement)` 从第一分句取得 `our contract manufacturers`，而循环在第二分句的 `manufacturing capacity` 前找到 `has`；并未证明两者属于同一主体。`validate_interpretation()` 又在 `:548-555` 将这一辅助判断应用于整个块的正确 `OTHER_ENTITY` 结论。另一条“目标主体以前有产能；供应商现在有产能”的混合块也被同样拒绝。建议仅在显式两阶段护栏中把当前产能与目标主体绑定到同一关系或有明确指代的相邻关系，同时保留此次已修复的 `previously ... but they have ...` 当前断言。

## 已核对的边界与证据级别

- 给定短测命令实际运行 **31 项，通过**，见 `short-tests.log`。新增测试覆盖 `Unlike prior years`、`Unlike fiscal 2023` 和 `previously ... but they have ...` 的错误 `OTHER_ENTITY`／`HISTORICAL` 排除，源码与测试联读一致；这些是录制合成来源，不证明真实模型会输出错误标签。
- 独立小样本中，单独的真正其他主体、`used to have` 旧关系与条件性 `if ... could have` 不被新护栏误拦；上述跨分句组合才出现回归。另有“明确 2023 旧期间；但现在有产能”的句子使新辅助判断返回 `False`，但旧 V4 验证器仍报 `B13_TWO_STAGE_UNRESOLVED`，**没有复现错误接受**，不把它列为第二个已证实 P2。
- V14 manifest 两处 `capacity_two_stage.py` 绑定均为实际文件的 SHA-256 `6fc89da94205d6da9f2081cd026615e0f50c1468fe6cd3a5089fab40d09a6d09`、大小 `30846` 字节；三份受审文件与指定提交无工作树差异，补丁 `git diff --check` 通过。
- 只读查看 `../stage3-local-repair.log`：执行方记录 `CURRENT_V5_STAGE3_READ_ONLY_REPLAY_PASS`、原序号 3、新录制调用 0、新真实调用 `[0,0,0]`。本独审没有重放该原件，也不以这行日志证明其他阶段、整家公司、真实模型或生产结果。

本独审只运行短测与隔离的内存构造复现；未发真实 provider／SEC 请求，未运行长测，未 commit/push，未修改账本或操作 #47／PR52。只新增本目录的 `conclusion.md`、`short-tests.log`、`adversarial.log`。
