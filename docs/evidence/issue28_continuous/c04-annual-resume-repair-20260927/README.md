# 缺失年报主文件在C04单条来源续接前不再被完整case预检挡住

`a5a3ceba`限定独审的原`NEEDS_FIX`保留：首次submissions更新能够发现唯一未保存的本期10-K主文件，但第二轮`resume_from`在捕获前仍无条件重建完整C04 case，因同一`SAVED_SOURCE_MISSING:<年报URL>`而停止。当前回修让这个**确切**缺件在续接捕获前复用首次准备的来源边界：请求URL须出现在经过原SEC槽、报告、当前历史及待办重建认证的`allowed_next_urls`；当前发现须由已验证同CIK submissions明确该主文件，项角色/状态精确为缺失的`current_annual_primary`；准备错误必须就是这个URL。正常已保存来源仍走原完整C04 `source_proofs` 检查。其他语义、主体、来源错误不能走缺件通道，底层SEC控制器实际发请求前仍会持原账本锁重新验证官方URL、声明与计数。

`fast-resume.log`为4项短测试通过：一个模拟且未登记执行信用的“已认证前次报告”让第二轮选中缺失年报URL并交给模拟的source-only捕获；非缺件错误未捕获，角色/URL及未验证submissions反例拒绝。**前次报告验证与SEC HTTP在此测试被替身替代**，故不宣称取得了真实新财年的原件，也不宣称完整新财报自动更新。已通过的当前FY2025 Marriott混合两条不同录制来源、旧C04-only续接及真实第193—194槽在本补丁未改变的路径保留原证据；不重跑那些大材料。

V13身份与旧包不变，未冻结V14当前执行绑定及provider/SEC/刷新收据见`binding-current.log`。本增量真实provider/paid/SEC调用0/0/0、原账本仍194槽143/143/51，没有新公司结果或生产操作。补丁SHA的限定独审、新head CI与完整新年原件/Run验收分别仍待完成；不触碰#47/PR52。
