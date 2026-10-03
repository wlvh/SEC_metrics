# 定向运行：Marriott FY2022、FY2023 的 C02（运行树闭包 `ed67e401`）

## 为什么跑

C02 共用修复 47（`6bd30c86`，`c02-selector-repairs/` 第 47 节）之后，这两个往年位置的选择与两向判读一致了：名片上的项目符号列表项不再当作董事姓名。但已发布的结果是修复之前算的，两条坐标级缺陷一直撤回它们。登记里这两条的状态没有随修复 47 更新，仍写着“部分修复、选择仍不一致”。

## 跑了什么

运行树是 `ca4d11e9` 加注册补丁，各 Run 记录的闭包为 `sha256:ed67e401…`。来源根由这棵运行树从已提交的 SEC 导出恢复（1,547 行）。驱动是 `period-batch/frame_batch.py`，2 个期间、2 个位置，零 provider / paid / SEC 调用。`rerun-results.json` 由 `../targeted-round-cf166529/collect.py` 汇总。

两个位置都冻结、发布，另一进程冷读、关掉推导缓存再冷读，读到的都是同一 run 与 result。**这不是全量帧**，也不改签任何旧批次。

## 阅读、接受与释放

- 在运行树里用 `tools/read_c02_composition.py --runs-root … --closure sha256:ed67e401…` 按往年判读读。选择从保存的代理重算，与 Run 的候选哈希相同；摘录就是选中块按序。两个位置都是 MATCH（`../content-acceptance/c02-older-years-read-round-ed67e401.json`）。FY2022 选中 78 块，其中 3 块的判断来自统一裁定；FY2023 选中 109 块，没有依赖裁定的块。
- 判读与修复规则是同一批材料，这是回归，不是留出检验。
- 两条缺陷 `C02_MARRIOTT_{2022,2023}_OLDER_YEAR_READING_DISAGREES` 先改正状态（选择一致、结果未重算，并补上修复 47 的说明），再由 `../targeted-round-cf166529/release_on_reading.py` 只对本轮的两个结果和这个闭包解除撤回。此前版本的结果仍被撤回。
- 接受登记 897 → 899，只新增这两条，已有条目一条未变。

往年 C02 仍撤回的位置还剩 4 个（Ford 2022、Lumen 2021/2022、Macy's 2022），当前选择器在判读上仍不一致。另有 JPMorgan FY2021 留出核对的那一条，不修。
