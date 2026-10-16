# 三份自写批改演示输入

用于评委检查上传、题号匹配、真实模型评分、教师复核和导出。维护者于2026-10-16明确授权随项目公开；非真实学生答卷。

| 文件 | 题号 | 人工预期 |
|---|---|---|
| Demo-01-Multiple-Choice-AB.pdf | P650-1 | 1/1（AB多选） |
| Demo-02-Three-Significant-Figures.pdf | P160 | 3/3（1.86 m，3位有效数字） |
| Demo-03-Correct-and-Incorrect-Choices.pdf | P402、P403-1 | 1/2（C正确、B错误） |

共3份、4题、人工预期5/6。详细逐题说明见[EXPECTED_RESULTS.md](EXPECTED_RESULTS.md)。这不是模型实测输出；原始AI结果与教师纠正后的结果应分开记录。

直接把这些PDF上传到“AI批改”，本机识别后检查题号，再决定是否发送给自己配置的模型。无需模型账户的输入检查：

```bash
.venv/bin/python scripts/verify_demo_samples.py
```

Windows用`.venv\Scripts\python.exe`替代`.venv/bin/python`。它只核对样例SHA-256、元数据、题号和上传识别流程，不调用外部模型，不消耗模型额度；通过不代表真实AI评分准确率。

本目录是公开样例白名单；不要把其他学生试卷或私人批改文件复制进来。按文件对应CC许可使用，署名、许可和修改说明见[SOURCES.md](SOURCES.md)和[sample-manifest.json](sample-manifest.json)。代码的AGPL不覆盖这些题目内容。
