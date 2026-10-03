# 修复 50 的 Macy’s C02 原生闭环

2026-10-03，固定程序提交 `c55871eb7dc13ae63cc4ab670fad9c690f0eea2c` 加既有注册补丁，重铸闭包 `sha256:aaea32da9cc599c86165bf5651d889a8b835edc8c1eddc10d63b1e8c7a8c9ab1`。此后的 B06 开发改动不在这个运行树里。该程序克隆独立 restore 同一获取导出，1,547 行，不 acquire / resume，不花余下 SEC 额度。

`plan.tsv` 只有 Macy’s FY2021 C02（期末 2022-01-29）。既有 `period-batch/frame_batch.py`，workers 1、shared / block on / memo on / memo-off-read-back 1，448 秒完成：一个冻结 Run、公共行，两次另进程冷读 Run / Result 相同，零 provider / paid / SEC 调用。数据根按驱动既有条件删除，本目录保存原生记录、矩阵、行收据、验证与日志；`rerun-results.json` 由既有 collect.py 汇总。

在同一固定程序树上，`tools/read_c02_composition.py` 从该克隆 restore 的原件重建选择，与原 `c02-older-years/judgements/macys-2022-01-29.json` 及既有统一裁定比较。未覆盖、重写旧判读；修复新增的十个块均已判为构成事实，阅读结论 MATCH。来源、候选、完整摘录和 Result 的绑定保存为 `content-acceptance/c02-older-years-read-round-aaea32da.json`。

- Run：`run:historical-period:35b8f148fdaa10652838e6bac9b10d99a3217a19a377388b5daa0455ac01f75b`
- Result：`sha256:0a65c2b9670e42970fe0ba34c47bd4196d9f37be1fb6818c909f7c0df81a54b6`
- 只释放本结果、本闭包对应的 `C02_MACYS_2022_OLDER_YEAR_READING_DISAGREES`；其它版本继续撤回。
- 正常接受登记通过既有 builder 901 → 902，原 901 条逐条不变。往年开发判读 24/27 一致，Ford FY2022、Lumen FY2021/FY2022 三个不一致仍在；JPMorgan FY2021 留出仍独立不一致，不据它拟合修复，四期限定反例也未释放。

复现：检出上述固定提交，应用 `native-run-2026-09-18/0001-register-issue47-v1.patch`、mint、在该程序克隆 restore；以本计划运行 frame_batch，再在该树用 `read_c02_composition.py --position macys:2022-01-29 --readings-dir docs/evidence/issue47_history/c02-older-years/judgements --source-root <恢复根>/source-inputs --runs-root <轮目录>/macys-c02-2021 --closure <本闭包> --acceptance-output <新文件>`。原生机械重放与既有开发判读的绑定不等于独立业务审阅，也不授生产或采纳权限。
