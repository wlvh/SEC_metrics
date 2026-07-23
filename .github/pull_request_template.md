<!--
PR body 原则：

1. 只写本 PR 已完成事实，不写计划。
2. 文件清单来自真实 git diff。
3. 测试策略和未运行项以 TESTING.md 为准。
4. 用户可见变化对照 interact.md；架构变化对照 architecture.md。
5. source/artifact/terminal publication 变化必须记录 provenance 不变量和负例。
6. 每轮 review / 修复写入“Review / 修复记录”。
-->

## 1. 背景与目标

---

## 2. 实现方案

<!-- 核心思路、信任边界、关键取舍；不要逐文件复述。 -->

---

## 3. 变更范围

<!-- 必须来自 git diff --name-status <base>...HEAD。 -->

| 文件 / 目录 | 变更类型 | 说明 |
|---|---|---|
|  | 新增 / 修改 / 删除 / 历史化 |  |

---

## 4. 文档影响

受影响文档：

- 无

说明：

-

<!--
能力边界：capability_contract.json → interact.md → business guide。
模块/状态/数据流/provenance：architecture.md。
测试/副作用/未运行项：TESTING.md。
文件地图/阅读路由：AGENTS.md。
生成 README/report：修改 generator 或稳定 post-processor。
-->

---

## 5. 用户与架构影响

用户可见变化：

- Yes / No
- 说明：

架构变化：

- Yes / No
- 说明：

Source / artifact provenance 变化：

- Yes / No
- source-input closure：
- artifact closure：
- stale-proof invalidation / fail-closed 行为：

---

## 6. Review / 修复记录

<!--
重复问题必须记录：较早声明为何不足、本轮固定的不变量、反例矩阵与可原样执行命令。
-->

| 轮次 | 来源 | 问题摘要 | 判断 | 处理结果 | 证据 |
|---|---|---|---|---|---|
| R0 | 初始提交 | N/A | N/A | 初始实现 |  |
| R1 | Codex / Claude / 人工 |  | 真实存在 / 不成立 / 可暂缓 | Fixed / Won't fix / N/A |  |

---

## 7. 测试证据

| 层级 / 目的 | 原样命令 | 实际结果 | 证据路径 |
|---|---|---|---|
| 快速回归 |  |  |  |
| Provenance 专项 |  |  |  |
| Capability alignment |  |  |  |
| Golden / repair / checker |  |  |  |

未运行项与原因：

- 无

说明：quick unittest 不能替代 Golden、repair gate、snapshot checker 或完整场景；light 和无 Git provenance 不能写成 full validation。

---

## 8. 已知限制与回滚

已知限制：

-

回滚方式：

-

---

## 9. 最终自检

- [ ] 当前分支不是 `main`，base 为 `main`
- [ ] 已执行真实 `git diff --name-status <base>...HEAD`
- [ ] 已运行 `python3 tools/check_capability_contract_alignment.py --base-ref <base>`
- [ ] 变更范围与 diff 双向一致
- [ ] PR body 不包含历史草稿、旧分支名或未落地计划
- [ ] 已按 `TESTING.md` 记录命令、结果、证据与未运行原因
- [ ] source closure 负例覆盖 dirty/untracked/tree mismatch/equivalent commit
- [ ] artifact closure 负例覆盖 missing/unexpected/size/hash tamper
- [ ] stage 11/12 不会留下新 artifact + 旧 provenance
- [ ] postflight failure 会 manifest FAILED、report NO-GO、非零退出
- [ ] 用户可见变化已对照 `interact.md`
- [ ] 架构变化已对照 `architecture.md`
- [ ] 每轮 review / 修复已记录
- [ ] PR 默认 draft；ready 状态有明确授权和发布级证据
