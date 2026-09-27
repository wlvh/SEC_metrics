# Southwest C04：真实前期年报补件与私有原生结果

本目录记录一次 **#28 既有独立来源获取许可**下的 SEC 请求，以及随后零网络的 C04 私有运行。没有使用 D04/B13 批次的 SEC=0 额度，也没有调用模型、操作账户或改动生产指针。

- `plan.json` 和 `preflight.json`：当前申报清单将 Southwest FY2024 10-K 主文件明确列为 `prior_annual_primary`，保存来源中原先缺少该确切 URL。最终需求与原账本校验通过；申领前累计为 provider/paid/SEC `143/143/51`。
- `capture.log`：仅对 `https://www.sec.gov/Archives/edgar/data/92380/000009238025000024/luv-20241231.htm` 发起一次真实 SEC GET；原账本槽 195 `SUCCEEDED`、实际 SEC egress=1。收据 ID `sha256:011fb31a9da9684bd3d7613191e9db14905db6aae251dd0f0c45c43cf7678160`，终态 ID `sha256:435e1c688f4c2c7e95deb3248d061531078edbc9b20ccdc81986dd1cfac8ee02`。累计变为 `143/143/52`，没有自动重试。
- `prepare_saved_corrected.log`：真实保存来源经现有显式四形式 C04 入口准备 FY2025（2025-01-01 至 2025-12-31）候选；46条来源证明，结果 ID `sha256:2f06895d80507148edfd7602427abffb8f6918323a48689c26345345c8170fe6`、数值 `0`。这一步尚未产生 Run。
- `create_native_corrected.log`：同一实际来源生成私有 `CANDIDATE_READY` 原生 Run 与公开行，零新增网络调用。私有状态根为 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/private-c04-southwest-20260927`。
- `cold_read_corrected.log`：另一进程禁止网络和子进程，重放原生 Run、输入来源、结果和公开行字节；独立冷读通过。私有状态保留原始失败尝试 `e9270741734746bca33d9bb37d0059d9` 与后续成功尝试 `43ae2e481d324ac9a1db2fc15fc76e9b`。

两条失败日志也保留。第一次 `prepare_saved.py` 实际已完成来源准备，只因证据脚本误读返回结构的 `targets` 键而退出；第一次 `create_native.py` 的演练脚本禁止了原生验证需要的本地子进程，留下 `EXECUTION_FAILED/SUBPROCESS_FORBIDDEN`，随后在相同私有更新状态下恢复成功；第一次 `cold_read.py` 未过滤 macOS `.DS_Store`，在开始重放前退出。它们都没有新增 SEC 或模型调用。最终冷读仍禁止子进程，且没有跳过来源或篡改校验。

**边界：**这证明已保存的当前 FY2025 与已取得的同 CIK 前期 FY2024 年报可以形成资料充分的 C04 `PUBLISHED/0` 私有结果，并证明一次失败后能保留失败、恢复运行。它不证明从 FY2024 的既存 C04 Run 自动升级为 FY2025：#28 来源根仍缺一份当时的、较新年报申报以前实际保存的申报清单快照。本目录未构造或裁剪该快照，也未将此次补齐前期原件描述成真实新财年在线发现。`0` 仅遵循当前 C04 原合同，未扩大为“找不到 Item 4.01 就认定未更换”。
