# 单页规则小样

三份维护者自写作答用于检查多选、有效数字和正确/错误选项判定。

| 文件 | 题号 | 人工预期 |
|---|---|---|
| Demo-01-Multiple-Choice-AB.pdf | P650-1 | 1/1（AB多选） |
| Demo-02-Three-Significant-Figures.pdf | P160 | 3/3（1.86 m，3位有效数字） |
| Demo-03-Correct-and-Incorrect-Choices.pdf | P402、P403-1 | 1/2（C正确、B错误） |

人工预期合计5/6，逐题说明见[EXPECTED_RESULTS.md](EXPECTED_RESULTS.md)。

## 使用

在“AI批改”上传PDF，检查题号，确认发送配置的视觉模型，逐题复核后确认并导出。模型原始结果与教师修正结果分别记录。

无需Key的输入检查：

```bash
.venv/bin/python scripts/verify_demo_samples.py
```

Windows使用`.venv\Scripts\python.exe`。检查文件摘要、页数、来源和实际上传识别。

题目、演示笔迹及处理方式按[SOURCES.md](SOURCES.md)和[sample-manifest.json](sample-manifest.json)中的署名与CC许可使用。[完整试卷测试](../full-papers/README.md)
