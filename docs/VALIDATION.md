# 自动化验收

[查看当前提交的GitHub Actions报告](https://github.com/Laura-LLU/OPBP-Bank/actions/workflows/ci.yml)

验收在Windows x64、macOS ARM64、Linux x64的Python3.12环境执行：安装依赖、校验题图、检查运行环境，测试接口、浏览器、任务和PDF/ZIP导出。

打开对应提交的工作流，查看三个系统任务的结果。附件`acceptance-Windows`、`acceptance-macOS`、`acceptance-Linux`包含：

- `test-result.json`：程序版本、提交、平台、Python版本、通过数及失败/错误/跳过数。
- `junit.xml`和日志：逐项结果。
- `evidence/`：浏览器截图、生成的PDF和ZIP。
- 覆盖率JSON和页面：进程内代码统计。

通过标准为`ok:true`，失败、错误、跳过均为0。自动化使用模拟模型；真实模型评分按[测试说明](TESTING.md)单独记录。

[本机复跑方法](TESTING.md) · [人工操作表](MANUAL_ACCEPTANCE.csv)
