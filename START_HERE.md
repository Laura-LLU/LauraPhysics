# 评委请从这里开始：OPBP Bank v0.7.45

源码包内已包含部署说明、百炼配置教程、三份自写演示答卷及人工预期。首次安装需要网络下载校验题图和依赖；不含维护者运行环境或密钥，不是完全离线包。

1. [安装并启动网页](docs/JUDGE_QUICKSTART.md#2-先安装并验证无模型模式)：推荐Python 3.12，在新本地目录安装，成功后打开http://127.0.0.1:8895/。
2. 无模型先到“OPBP组卷”检查选题、预览及学生/教师卷导出。
3. [检查三份样例](examples/marking-demo/README.md)：运行下方指令，3份PDF应通过文件和题号匹配检查。
4. [配置自己的百炼接口与Key](docs/BAILIAN_SETUP.md)，再上传样例进行真实AI批改与教师复核。
5. [人工预期结果](examples/marking-demo/EXPECTED_RESULTS.md)为5/6，不是模型实测值；[10项人工验收表](docs/MANUAL_ACCEPTANCE.csv)的实际结果列由评测者填写。

Mac/Linux安装后：

```bash
.venv/bin/python scripts/run_web.py --check
.venv/bin/python scripts/verify_demo_samples.py
.venv/bin/python scripts/run_web.py --open
```

Windows：

```powershell
.venv\Scripts\python.exe scripts/run_web.py --check
.venv\Scripts\python.exe scripts/verify_demo_samples.py
.venv\Scripts\python.exe scripts/run_web.py --open
```

完整自动化验收用`scripts/run_tests.py --install --output test-results`，用上方相应Python执行。它隔离真实配置、不调用付费模型。运行和停止、其他端口、依赖/证书错误、模型错误均见[完整评委指南](docs/JUDGE_QUICKSTART.md)。

[图解功能说明](docs/FEATURE_TOUR.md) · [Mac详细部署](docs/MAC_DEPLOYMENT.md) · [测试范围](docs/TESTING.md) · [内容许可](CONTENT_LICENSES.md) · [已知限制](docs/KNOWN_LIMITATIONS.md)

Release源码ZIP不含Git历史，自动化报告的gitCommit可能为空；可用随包release-manifest.json和Release提供的SHA256SUMS.txt核对内容。Git克隆部署则核对版本标签与提交。
