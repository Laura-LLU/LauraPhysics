# 测试说明

## 运行

macOS / Linux：

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

Windows：

```powershell
.venv\Scripts\python.exe scripts/run_tests.py --install --output test-results
```

测试使用独立数据、输出目录和模拟模型。首次安装测试依赖及Chromium需要联网。

## 范围

| 层次 | 检查内容 |
|---|---|
| 规则 | 题池、数量、时间分配、多选、有效数字、单位、评分结构 |
| HTTP | 服务启动、题库、组卷、上传识别、批改、确认与下载 |
| 浏览器 | 工作区切换、选题、预览、上传、复核、批量任务 |
| PDF与ZIP | 题图排版、题旁批注、评分栏、班级总结与批量导出 |
| 任务 | 三并发、暂停、继续、断点保存、逐份确认 |
| 模型协议 | 模拟文字/视觉响应、异常返回与流程衔接 |
| 部署 | 平台依赖、资源校验、源码包完整性和文件访问 |

## 报告

`test-results/`包含`test-result.json`、`junit.xml`、日志、覆盖率页面与`evidence/`。通过标准：`ok:true`，失败、错误、跳过均为0。版本和提交用于对应运行的源码，覆盖率统计进程内代码。

[GitHub Actions](https://github.com/Laura-LLU/OPBP-Bank/actions/workflows/ci.yml)在Windows、macOS、Linux的Python3.12环境运行同一套测试。

## 测试答卷

完整答卷位于[examples/full-papers](../examples/full-papers/README.md)，每份7页、6题、满分12分：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

单页规则小样位于[examples/marking-demo](../examples/marking-demo/README.md)：

```bash
.venv/bin/python scripts/verify_demo_samples.py
```

两项均检查SHA-256、来源、页数与实际上传识别。Windows使用`.venv\Scripts\python.exe`。

## 真实模型测试

配置[百炼](BAILIAN_SETUP.md)，上传自写答卷，记录原始模型得分、逐点差异、教师修正和用时。单页用例提供[人工预期](../examples/marking-demo/EXPECTED_RESULTS.md)；整卷由教师逐题核对。使用[人工操作表](MANUAL_ACCEPTANCE.csv)记录本轮结果。
