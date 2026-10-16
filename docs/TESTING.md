# 自动化测试与证据边界

用独立环境运行 `python scripts/bootstrap_assets.py` 和 `python scripts/run_tests.py --install --output test-results`。Mac 使用 `.venv/bin/python`。测试隔离数据/输出，不继承真实API Key。

| 层 | 内容 | 证据 |
|---|---|---|
| 单元 | 题池、数量/时间、选项证据、有效数字/单位、模型评分结构 | pytest/JUnit |
| 任务/文件 | 暂停/断点/三并发、确认/统计/ZIP、PDF落点和同页题目归属 | 状态断言、生成PDF/ZIP |
| HTTP | 上传、组卷、批改、确认、下载 | 真实本机服务 |
| 浏览器 | 预览、上传、复核、切页状态、下一份 | Chromium截图/DOM断言 |
| 模型协议 | 自然语言→模拟文字模型→组卷→匿名排版作答→模拟视觉模型→确认→导出 | model-http-trace.json，simulated:true |
| 部署 | 独立依赖、完整资源、许可、凭证检查、下载/ZIP路径防护 | 环境JSON、SHA-256、CI |

保留失败/跳过，不从准确率分母中删掉失败样本。覆盖率为进程内范围，HTTP子进程未插桩，不代表所有功能/分支全覆盖。历史迁移审计不依赖作者私人目录冒充移机回归。

人工组卷的内嵌PDF测试检查生成的Blob具有`%PDF`文件头、预览容器与导出按钮可用；无头Chromium的原生PDF查看器截屏可能为空白，不能据此声称查看器像素渲染已通过。生成PDF另有页面渲染证据，AI预览则检查实际图像加载；新Mac仍需人工打开预览与导出PDF核对。

真实AI评测另用教师金标准、合法匿名手写样本、冻结模型/题库/提示版本，分别统计识别、逐点评分、误给/漏给分和请求失败，记录真实耗时/服务商token。模拟和连接测试不替代准确率。

2026-10-16 新增针对异机反馈的 `tests/test_marking_question_alignment.py`：同页双题模型坐标串题、题旁勾叉/侧栏对齐、长点评防裁切、2/3位与1/4/5位数值、科学记数/单位指数、P456半边面积乘2、错误换算/缺过程不补分、旧草稿无模型迁移与浏览器缓存合并。可用 `python -m pytest tests/test_marking_question_alignment.py -q` 单独复跑；包含本机HTTP/无头浏览器检查。排版样本采用匿名排版答案，不声称是真人手写识别测试。已保存的已确认PDF需要在复核后重新导出，不会远程替换另一台电脑的文件。

持续补充超时、429、坏JSON、损坏/加密PDF、手机照片、磁盘失败、异常退出、线程竞争、长批次和不同字体。性能比较在同样环境/输入下进行。

CI在Ubuntu/macOS/Windows干净Python环境运行；不使用continue-on-error掩盖失败，也不替代第二台实体Mac验收。测试结果包含日志、JUnit、JSON、覆盖率和合法匿名生成证据。

## 公开演示输入检查

三份自写PDF位于`examples/marking-demo/`，人工预期与来源许可分别在`EXPECTED_RESULTS.md`和`SOURCES.md`。运行`.venv/bin/python scripts/verify_demo_samples.py`（Windows使用`.venv\Scripts\python.exe`）检查文件SHA-256、元数据、逐题来源及实际上传识别；输出3份匹配结果，不调用外部模型。完整pytest包含三份真实PDF识别、未声明PDF检查及文件改动拒绝，并检查便携包包含样例和START_HERE。

真实模型体验按`docs/BAILIAN_SETUP.md`与`docs/JUDGE_QUICKSTART.md`进行；`docs/MANUAL_ACCEPTANCE.csv`只提供操作和预期，实际结果由评测者填写，不预填通过。

## 完整自写试卷

本次指定的三份7页完整答卷位于`examples/full-papers/`。运行`.venv/bin/python scripts/verify_demo_samples.py --full-papers`（Windows使用`.venv\Scripts\python.exe`），检查三份SHA-256、来源与每份6个题号/12分满分匹配。pytest同时逐份走实际上传识别流程。文件与维护者提供的原件相同；整卷没有预先核定的人工得分，不套用单页小样的5/6。该检查不调用模型。
