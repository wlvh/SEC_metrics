# Enphase FY2024 B06 的原生阅读闭环

2026-10-03，固定 `32f9696ed146d01bcbbc21916cf6e35b35978f2f` 加既有注册补丁，重铸闭包 `sha256:421eb9213b6d9f2e3bc3f7e31bc227019450673789c28517660437288599e5ac`。该程序克隆自行 restore 原获取导出，1,547 行；没有 acquire / resume，也不恢复 SEC 余额。

`plan.tsv` 只跑 Enphase FY2024 B06（2024-12-31），既有 frame_batch、workers 1、shared / block on / memo on / memo-off-read-back 1。372 秒完成：一个冻结 Run 与公共行，两次另进程冷读同一 Run / Result；数据根只在驱动原有全部条件成立后删除。本目录保存完整原生记录、验证、行收据、矩阵和日志，零模型/付费/SEC请求。

Run `run:historical-period:106f9f4d2a8b81cd3fb5f82b85122e91f2d0e00fe38cbf5acfe378d951223613`，Result `sha256:fd16acda5e3c00d11d5324eb14a3fb81c03ce60cefb91624627606616bd2472a`，`EXACT / PUBLISHED / PASS`，值 `1.563451362278755750189672227`。

随后在同一固定树上，既有 `tools/read_debt_to_equity.py` 从该克隆恢复的实际申报原件重新读债务、融资租赁处理及股东权益，绑定上述 Run / Result / 闭包。它不导入债务路线，得到与建 Run 前已保存参考相同的债务 1,302,380,000、权益 833,016,000、明确无融资租赁陈述及比值，MATCH；新阅读另存 `content-acceptance/debt-to-equity-read-round-421eb921.json`。正常接受登记902→903，原902条逐条不变；旧扣留与全部原运行保留，不重签、不用新值覆盖旧版。

规则边界、50期间影响（49份JSON投影不变）、10新用例、8既有原件反例、13级联用例及9个具名注错见 `b06-older-years/note-forms/`。这次增加一个往年可自动完成的数值，仍有其它往年版式/范围缺口；开发阅读和机械冷读不等于外部独立业务审阅或生产采纳。

重现：固定本提交，加 `native-run-2026-09-18/0001-register-issue47-v1.patch`、mint、在此克隆自行 restore，再用本计划调用 frame_batch。在此树以 `read_debt_to_equity.py --position enphase_energy:2024-12-31 --source-root <恢复根>/source-inputs --runs-root <轮目录>/enphase-b06-2024 --closure <本闭包> --output <新文件>` 绑定阅读。可在 run_checks_replay_once / derived_once_per_state / xbrl_parsed_once 的既有只读块中运行相同 CLI。
