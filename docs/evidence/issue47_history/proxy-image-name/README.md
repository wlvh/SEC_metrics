# JPMorgan FY2021 的 C02/C03：封面名称是图片，薪酬表有独立的脚注单元格和业务单元 CEO

## 问题

50 期间批次（闭包 `500ddf5f`）里，JPMorgan FY2021 的 C02 和 C03 都在代理身份这一步失败，理由是 `HISTORICAL_PROXY_COVER_NAME_NOT_ESTABLISHED`。这是实现缺口，不是没有披露。

JPMorgan 2022 年的代理（`0000019617-22-000303`，`a2022proxystatement.htm`，2026-09-30 追加取数时取回）是第九份没有 inline XBRL 的代理。原来那八份是在它取回之前量过的。

- **封面。** 名称说明行 "(Name of Registrant as Specified In Its Charter)" 上方只有一张 logo 图片，alt 是文件名（`logo2008_jpmcxaxblack.jpg`），没有文字。勾选框用的是 Wingdings 字体的 `þ`（勾选）和 `o`（空框），读取器原来不认这两个字形。
- **薪酬汇总表。** 身份过了之后，C03 又停在三处：
  1. 标题写作 "I. SUMMARY COMPENSATION TABLE (SCT)"，前面有节号，后面有缩写；读取器原来只认不带这两样的标题。
  2. 脚注编号印在独立的单元格里，只靠样式（5.2pt、上移）显示成上标，于是被读成几美元的金额。每一行都因此不满足 Item 402(c) 的合计（Total 等于同行其余金额之和）。例如 Dimon 那一行多读进一个 7，合计差 7。
  3. 表里有业务单元的 CEO，写作 "CEO CIB"、"CEO CCB"、"CEO AWM"，原来会被当成注册人的 CEO。

## 修法（两个规则文件；原先作为挂起补丁保存，10-03 已作为正式提交落地）

**封面**（`scripts/vnext/historical_proxy_identity.py`）
- 认 Wingdings 的 `þ`（勾选）和 `o`（空框）。
- 名称说明行上方没有文字（紧挨着的是勾选项）时，只有同时满足以下两条才走新读法，否则仍按名拒绝：
  - 两块之间的 HTML 里只有一张图片、没有文字；
  - 紧接着是 "(Name of Person(s) Filing Proxy Statement…)"。
- 新读法：名称取封面之后申报正文的第一块，跳过表格要求的缴费项和链接（目录）。
- 这一块不在这里就被当成名称，仍要经过原来的 `cover_name_in_effect`：它必须是 SEC 记录在申报日给这个 CIK 的名称，否则按名拒绝（`SOURCE_INTEGRITY_ERROR`）。所以新读法只会取不到，不会取错。
- 身份记录只在这种版式下多一个 `cover_name_basis`。原八份的封面和身份记录逐字节不变，它们的 C02/C03 结果编号也就不变。

**薪酬表**（`scripts/vnext/historical_proxy_compensation.py`）
- 标题可以带节号（"I."、"1."）和 "(SCT)"。
- 一位或两位数的单元格，只在整行按原样读不满足合计、而去掉它们以后满足时，才当作脚注编号（`row_amounts_by_arithmetic`）；去掉了哪些记在候选里（`cells_read_as_footnote_marks`）。按原样就满足合计的行，保留它印出的每个金额，包括印出的 0。
- 职务后面紧跟一个 2–5 个大写字母的单元缩写（AND、OR 除外）时，不算注册人的 CEO。

## 量测（零调用）

`measure.py` → `measured.json`：九份没有 inline XBRL 的代理，用基准提交（`HEAD`）的两个读取器和本树的读取器各读一遍。比较三样：封面和身份记录、每个满足表头条件的薪酬表人员行、C03 的答案。

- 原八份三样都完全相同。
- 只有 JPMorgan 移动：
  - 封面：由拒绝变为读出 "JPMorgan Chase & Co."，与 SEC 记录在 2022-04-04 的名称 "JPMORGAN CHASE & CO" 一致。
  - 人员行：同一张表 6 行全部由不满足合计变为满足，去掉的单元格分别是 7、8 和 9、10、11、12、14。三位业务单元 CEO 不再算注册人的 CEO。
  - C03：只剩 Dimon 一位候选，84,428,145 美元。
- 这里"基准"的薪酬表读取器用的是本树的封面读取器，所以它对 JPMorgan 给的是 `C03_PROXY_SCT_NOT_ESTABLISHED`（停在标题）；批次里实际停在更早的封面那一步。

`route_probe.py` → `route-probe.json`：在恢复根上走历史路线，用的是真代码，不是内存补丁。代码树是登记了恢复根的那一棵，临时放入这两个读取器，跑完已还原。
- C03：`PUBLISHED / EXACT / PASS`，84,428,145 USD。
- C02：输入准入通过，身份记录带 `cover_name_basis`，确定性选择 51 条摘录。

**独立核对。** JPMorgan 2023 年的代理在薪酬与业绩表里用 `ecd:PeoTotalCompAmt` 给 2021 年 PEO 标的总额，正是 84,428,145。用例用另一个正则读取器读这份标注，不经过路线代码。

## 用例与注错

- `tests/vnext/test_historical_proxy_identity.py` 新增 `ANameShownAsAnImageIsTheFirstBlockAfterTheCover`（8 例），覆盖：
  - 真申报读出名称和勾选；
  - 名称仍按 SEC 记录核对；
  - 换成别家名称时按名拒绝而不是取用；
  - 链接不会被当成名称；
  - 去掉图片的空位置被拒；
  - 位置里有文字时走原读法；
  - 缺缴费人说明行时被拒；
  - 原八份记录的键集合不变。
- `tests/vnext/test_historical_proxy_compensation.py` 新增 `TheNinthProxyReadsItsMarkCellsAndUnitTitles`（5 例），覆盖：
  - 真申报的 CEO 总额；
  - 与 2023 年标注一致；
  - 业务单元 CEO 与大写 "CEO AND PRESIDENT" 的区分；
  - 脚注单元格只在原样不满足合计时才去掉（含印出 0 的反例）；
  - 标题形式。
- 四个相关模块（含 `test_c03_across_proxies_reading`、`test_historical_dei`）95 例通过。
- `injections.py` → `injections.json`：14 个注错，在另一个工作树里跑，每个都由为它写的用例抓到。

## 未做与局限

- 这种封面只见过这一份。"封面之后第一块"是按它写的，靠 SEC 记录核对保证不会取错名称；别的版式可能取不到，那时按名拒绝。
- C02 的 51 条摘录没人读过，不能计入接受。C03 有 2023 年代理的标注作独立核对，仍要用阅读工具读过后才计入接受登记。
- 这是规则文件改动：原先作为挂起补丁保存在 `../pending-rule-changes/`，打算等模型出口收据提交之后再应用。10-03 虚拟机重启打断了重封，重封要从头再跑，于是先把补丁作为正式提交落地、重铸快照（见 `../pending-rule-changes/README.md`）。还没做的：在新闭包下定向重跑 JPMorgan FY2021 的 C02/C03，冷读一致后再读、再接受。
