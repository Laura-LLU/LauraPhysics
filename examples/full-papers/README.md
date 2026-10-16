# 完整自写测试答卷

三份维护者本人填写的Dynamics答卷，每份7页、6题、满分12分，用于测试整卷上传、识别、批改、复核和导出。

| 文件 | 页数 | 题数 | 满分 |
|---|---:|---:|---:|
| [Student-Paper 2.pdf](Student-Paper%202.pdf) | 7 | 6 | 12 |
| [Student-Paper 3.pdf](Student-Paper%203.pdf) | 7 | 6 | 12 |
| [Student-Paper 4.pdf](Student-Paper%204.pdf) | 7 | 6 | 12 |

三份包含相同题目和不同作答。题号顺序为P402、P403-1、P478、P087、P352、P456，前两题在第3页，其余分别在第4至7页。

## 操作

1. 按[安装入口](../../START_HERE.md)启动网页。
2. 在“AI批改”选择PDF，识别并核对题号。
3. 按[百炼教程](../../docs/BAILIAN_SETUP.md)配置视觉模型，确认发送。
4. 逐题对照评分点与作答证据，记录原始模型得分，教师修正后确认并导出。

重点核对选择题差异、计算过程、力-时间图毫秒换算以及2或3位有效数字。12分为每份满分，实际得分按各自作答逐题记录。

无需Key的文件和题号识别检查：

```bash
.venv/bin/python scripts/verify_demo_samples.py --full-papers
```

Windows使用`.venv\Scripts\python.exe`。预期`ok:true`、`sampleCount:3`，每份7页、6个题号匹配。单页规则用例的人工预期见[marking-demo](../marking-demo/EXPECTED_RESULTS.md)。

## 来源与许可

自写笔迹由维护者Laura-LLU提供，六道原题及答卷按CC BY-NC-SA 4.0提供。文件SHA-256与逐题来源见[sample-manifest.json](sample-manifest.json)。

- P402: Falling Mass on Rope; author: Patrick Jilek-Rodriguez; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Momentum/Falling%20Mass%20on%20Rope/FallingMassOnRope.md)
- P403-1: Force Multipart True False Question; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/006.Force/Topic%20Outcome/forceMultipartTrueFalse/forceMultipartTrueFalse.md)
- P478: Position Vector and Momentum; author: Tarek Alkabbani; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Topic%20Outcome/What%20is%20r_mv/What%20is%20r_mv.md)
- P087: Bouncing Ball; author: Jake Bobowski; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Impulse/Bouncing_Ball/Bouncing_Ball.md)
- P352: Car in Ditch; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/006.Force/Free%20Body%20Diagrams/Car%20in%20Ditch/car_in_ditch.md)
- P456: Force on a Mosquito; author: John Hopkinson; license: CC BY-NC-SA 4.0. [原始来源](https://github.com/open-resources/physics_bank/blob/59de2e82f4fa6fc1ca24c15a088f07428fd4480e/content/public/007.Momentum%20and%20Impulse/Topic%20Outcome/Force%20on%20a%20Mosquito/force_on_mosquito.md)

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)：保留署名与许可，非商业使用，修改版按相同许可共享。
