# JPMorgan FY2025 D02：两个原 Result 身份包含年报页眉页脚

对方 #47 的 `e76e2953` 页码修复是线索；本方没有直接继承其历史判读或修后结果。`audit.py` 独立读取 #28 已保存的 JPMorgan FY2025 普通 D02 Run：34个入选摘录中，原块10174、10184、10195 只是 `JPMorgan Chase & Co./2025 Form 10-K` 页脚，10186 只是 `Notes to consolidated financial statements` 运行页眉。四个块都作为 `NOTE_30` 摘录进入原生 Evidence `PASS` 和私有 `PUBLISHED/EXACT` Result。脚本从记录绑定的原年报主文件重验完整资产SHA-256与各原始字节跨度SHA，保留四块身份于 `audit.json`。

当前私有 Result 是 `sha256:7256aa80…`。已有390索引保存的是另一身份 `sha256:3c7230d0…`；其公开 `value` 本身三次包含上述页脚、一次包含页眉。`comparison.json`明确两者 Result ID 不同，所以本次在 `known_result_defects.json` 登记**同一个公司—指标—期间坐标的两个确切旧Result身份**，累计可信排除由17坐标／23身份变为18坐标／25身份。旧Run、Result、来源和390分母不删除，也不把旧 `PASS/EXACT` 说成内容正确。

这只确认四段页面装饰误纳，不能证明其余30段全部相关，不能独立证明有无漏选，也不给 JPMorgan 新D02结果。对方还报告过其它期间的MD&A/附注定位问题，本方没有按公司名或指标名批量撤回；是否影响其它本方原件另查。当前D02 Item8后继仍因逗号误删反例而暂停新原生信用，不能以本次页码线索解除。实际provider/paid/SEC新增0/0/0，#47工作树、运行根、快照和账本未操作。
