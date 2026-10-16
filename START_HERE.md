# 安装与运行

[OPBP物理题库-AI组卷和批改工具](README.md) · v0.7.47

## 1. 安装

准备Python 3.12、联网环境和至少4 GB本地空间。下载[发布包](https://github.com/Laura-LLU/OPBP-Bank/releases/tag/v0.7.47)并解压，在 `OPBP-Bank` 目录运行。

macOS / Linux：

```bash
python3 scripts/setup_environment.py --venv .venv
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/run_web.py --open
```

Windows PowerShell：

```powershell
py -3.12 scripts/setup_environment.py --venv .venv
.venv\Scripts\python.exe scripts/run_web.py --check
.venv\Scripts\python.exe scripts/run_web.py --open
```

检查结果应为 `ok:true`、`questionCount:900`、`missingAssets:[]`。浏览器访问 http://127.0.0.1:8895/ ，终端保持运行，按 `Control+C` 停止。

## 2. 组卷

切到“OPBP组卷”，搜索P402，加入作业，预览并导出学生卷和答案卷。使用[百炼教程](docs/BAILIAN_SETUP.md)配置模型后，可在“AI组卷”输入要求生成试卷。

## 3. 测试答卷

在“AI批改”上传 [Student-Paper 2、3、4](examples/full-papers/README.md)，核对题号，确认发送模型，再逐题复核、确认并导出。

无需Key的整卷输入检查：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

Windows使用`.venv\Scripts\python.exe`。预期为3份通过，每份7页、6个题号、满分12分。

[单页规则小样](examples/marking-demo/README.md)另有逐题人工预期，可单独核对多选和有效数字规则。

## 4. 自动化验收

```bash
.venv/bin/python scripts/run_tests.py --install --output test-results
```

Windows使用`.venv\Scripts\python.exe`。成功时 `test-results/test-result.json` 中 `ok` 为 `true`，失败、错误和跳过均为0。

[完整部署指南](docs/JUDGE_QUICKSTART.md) · [故障排查](docs/安装与故障排查.md) · [功能图解](docs/FEATURE_TOUR.md) · [测试说明](docs/TESTING.md)
