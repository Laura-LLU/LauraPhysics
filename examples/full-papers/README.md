# 三份完整自写测试答卷

维护者于2026-10-16指定以下三份本人填写的答卷用于公开测试。文件与提供的原文件逐字节相同；保留封面、公式页、题目、笔迹和原有页脚。姓名、班级与考号栏为空，非真实学生答卷。原文件未修改。

| 文件 | 页数 | 题数 | 满分 |
|---|---:|---:|---:|
| [Student-Paper 2.pdf](Student-Paper%202.pdf) | 7 | 6 | 12 |
| [Student-Paper 3.pdf](Student-Paper%203.pdf) | 7 | 6 | 12 |
| [Student-Paper 4.pdf](Student-Paper%204.pdf) | 7 | 6 | 12 |

三份是同一套 Dynamics 试卷的不同作答，不能将三份当成三套不同题目。识别顺序均应为：P402、P403-1、P478、P087、P352、P456。前两题在第3页，之后四题分别在第4至7页。每份12分是试卷满分，不是学生得分。

## 评委怎么测试

1. 按根目录 [START_HERE.md](../../START_HERE.md) 安装并启动。
2. 无需Key先检查文件和实际上传识别：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

Windows将`.venv/bin/python`替换为`.venv\Scripts\python.exe`。应输出`ok: true`、`sampleCount: 3`，每份7页、6个题号匹配；检查不调用模型、不消耗模型额度。

3. 按[百炼教程](../../docs/BAILIAN_SETUP.md)配置自己的视觉模型。打开“AI批改”，选择这三份PDF，核对题号，再确认发送给模型。可以先上传一份跑通，再检查三份并发流程。
4. 逐题核对评分证据、批注位置和原卷对应关系；保留模型原始得分，教师修正后再确认、导出PDF及汇总。重点检查选择题作答差异、计算过程、力-时间图的毫秒换算及2或3位有效数字。不要将三份设为同一个预期分数。

三份整卷尚未建立独立逐题人工评分基准，也没有在本次发布中调用真实模型测准确率。完整性/识别检查通过不代表AI批改正确；已有单页[规则小样及人工预期](../marking-demo/EXPECTED_RESULTS.md)仍保留，5/6仅针对那三份单页小样，不适用于本目录整卷。

## 来源与许可

六题均来自项目已收录的OPBP题库，原题与自写笔迹按CC BY-NC-SA 4.0提供，代码AGPL不覆盖试卷内容。逐题作者、来源链接、许可及文件SHA-256见[sample-manifest.json](sample-manifest.json)；原有页脚中的历史名称不代表当前项目名称。

- P402: Falling Mass on Rope; author: Patrick Jilek-Rodriguez; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Momentum/Falling%20Mass%20on%20Rope/FallingMassOnRope.md)
- P403-1: Force Multipart True False Question; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/006.Force/Topic%20Outcome/forceMultipartTrueFalse/forceMultipartTrueFalse.md)
- P478: Position Vector and Momentum; author: Tarek Alkabbani; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Topic%20Outcome/What%20is%20r_mv/What%20is%20r_mv.md)
- P087: Bouncing Ball; author: Jake Bobowski; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Impulse/Bouncing_Ball/Bouncing_Ball.md)
- P352: Car in Ditch; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/006.Force/Free%20Body%20Diagrams/Car%20in%20Ditch/car_in_ditch.md)
- P456: Force on a Mosquito; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Topic%20Outcome/Force%20on%20a%20Mosquito/force_on_mosquito.md)

[CC BY-NC-SA 4.0许可](https://creativecommons.org/licenses/by-nc-sa/4.0/)：使用时保留署名与许可，不用于商业用途，修改版遵循相同许可。
