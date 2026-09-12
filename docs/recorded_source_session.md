# 普通来源更新的测试会话

`ordinary_source_session.recorded_source_session` 在源码和正式发布目录之外验证来源更新的记录路径。它只支持明确的测试模式：复用已经核验的原文，通过现有 SEC 客户端的持久化方法和日志追加方法生成记录，不调用 HTTP，也不能授予真实 SEC 信用。

会话核对旧日志的完整字节前缀，每次追加前保存意图，追加后保存终态并核对唯一新行。内存中保留本次真正写出的终态身份，因此调用者补造一份自洽日志或修改终态文件不能加入这个会话。未知结果、已失败终态和测试次数耗尽都会阻止后续追加；原件或旧前缀变化、路径别名也会拒绝。

`session.prepare_annual_input()`将新记录交给未改动的基础年度输入读取器，再核对其请求证明；该方法本身不创建Run。下述安装目录登记机制把它接到当前普通财年解释及Run，来源仍是测试重放。旧固定基线校验器保持原样，继续拒绝这些测试追加。

`compare_annual_inputs(previous=..., current=...)` 只比较已经由调用方验证的输入：区分申报变化、修订集合变化、期间解释变化、来源内容变化、选择倒退和内容未变。请求身份、请求头时间、目录等变化不等于财务输入内容变化。此比较本身不授予来源真实性或发布权限。

早期隔离材料保留984行旧日志，追加三份已保存原文后，由基础读取器和Calculator得到Marriott收入`26186000000 USD`及`NO_SOURCE_CONTENT_CHANGE`。这一历史版本尚未创建Run，其原记录保留在`docs/evidence/issue28_continuous/recorded-source-session/`，不改写为后续接线结果。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_source_session
```

## 将已登记请求交给普通计算

`ordinary_source_authority.register_recorded_session(session=...)`只接受实际创建会话的对象。它重新核对旧前缀、原件、全部新增意图/终态和来源证明，把校验记录写到安装目录固定的`.git/ordinary-source-authority/recorded/`。输入目录不能指定执行记录的位置，也不能靠自签JSON或一份自洽日志取得登记。失败、未知或未登记记录不能成为计算输入。

当前普通财年、零AI、Company Facts、accession及酒店来源适配器使用这个新入口。旧日志完整未变时仍调用原验证器，返回原来源身份；有新增记录时逐项核对安装目录拥有的记录。测试响应仍须对应原清单里已经验证过的SEC原文，`source_credit=RECORDED_TEST_ONLY`及`real_sec_credit=false`不变。

`normal_run_v3.install_normal_inputs(..., source_root=...)`从外部来源目录复制数据，从安装目录复制固定代码和规则，并把来源校验记录及其所有原文/请求头依赖一起安装。创建及重放Run都要求安装记录存在；冷读使用运行包中的记录，不依赖原进程内存。与既有B06安装边界相同，这保护调用方提供的数据，无法对抗同时替换受信代码及其执行历史的操作者。

```bash
python3 tools/vnext_normal_candidate.py --source-root /absolute/admitted-source-workspace --company marriott_international --metric B03 --metric B08 --metric B09 --metric B10 --metric B11 --output-root /absolute/new/candidate-batch
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_source_authority
ORDINARY_SOURCE_MATERIAL_ROOT=/absolute/new/source-material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_source_run_material
```

测试来源的公共行和预览回执明确显示来源类型。当前材料创建五个实际OPEN Run，包含B03/B01依赖、B08/B09及B10/B11，共六个结果；与原文直接计算的数值/期间一致，并拒绝五类伪造图、依赖缺漏、来源登记缺漏、自签信用升级及未登记追加。未经新适配的旧冻结来源包装器仍受原基线限制，不能声称全部39项已接受更新来源。

后续仍须接入新预算下的真实获取、完整路线、新申报触发、持久运行计数及正式发布。本次财务原文未变，不证明在线发现新财报；旧阶段额度不恢复，本测试接口不提供真实SEC执行信用或日常人工补文件流程。
