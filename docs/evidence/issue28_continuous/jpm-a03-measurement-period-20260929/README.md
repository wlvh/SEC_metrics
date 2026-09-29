# JPMorgan A03：111% 的实际测量期间与主体

本次只读核对已保存的 JPMorgan FY2025 私有普通 A03 Run、此前的异进程冷读记录，以及同一原年报主文档的原始字节。`audit.py` 不用当前代码去重签旧安装 Run，也不创建新 Result；原件与安装副本的SHA一致，来源身份、Result ID 和旧冷读一致。

原表明确说 LCR 是截至2025年12月31日**三个月平均**。同一表的JPMorgan Chase & Co.（Firm）行报告111%，JPMorgan Chase Bank, N.A. 行报告115%。保存的Observation、Result和公开行均为Firm average、`1.11`，测量期间2025-10-01至2025-12-31；10-K所属财年另存为2025-01-01至2025-12-31，公开行的`fiscal_period`为`QUARTER`。`audit.json`绑定表格相关原始跨度及SHA。这支持当前私有候选没有把银行子公司115%或全年平均冒充Firm的三个月平均；并不重新审阅旧PR34记录，也不证明其他R4坐标正确。

本项仅是一个坐标的原件与已保存Run对照，不授正式生产信用，不证明最新head按其身份重放该旧包。真实provider/paid/SEC调用0/0/0，#47未操作。
