# 指定模型与现有API配置

- 图片理解：豆包2.0-lite，`在本地配置 analysis.endpoint`，`/chat/completions`。
- 按需背景生图：Seedream5.0 Pro，`在本地配置 image_generation.endpoint`，`/images/generations`。
- 将 `config/models.example.json` 复制为 `config/models.local.json`，填写自己在火山方舟开通的对应模型端点。通过 `ARK_TEXT_API_KEY` 与 `ARK_IMAGE_API_KEY` 环境变量提供凭据。脚本也支持显式配置本地凭据文件；本地配置被 Git 忽略。不要将密钥输出或写入计划、日志、压缩包。
- 使用Python3及Pillow。脚本不自动重试付费请求，不默认切换模型；网络超时先检查已有输出，避免重复扣费。缺少凭据或接口不可用时如实报告。

```bash
python scripts/ark_book.py check-keys
python scripts/ark_book.py analyze --input /absolute/01.jpg --input /absolute/02.jpg --brief '浅米灰底，丰富内页配色' --output /absolute/work/analysis.json
python scripts/ark_book.py background --prompt-file /absolute/work/background-prompt.txt --output /absolute/work/background.png
```

先用render_book.py的plan生成数量与布局骨架。豆包返回的analysis.json是语义建议，不直接交给渲染器；核对所有U编号、裁剪、分组和事实，再合并到符合schema.md的计划。模型对裁剪的建议必须实际预览检验。

纯色展示底、线框、小方块和椭圆由代码绘制，不为调用模型而生成无用资产。背景提示词写明所需颜色与材质，不上传用户照片做背景重绘；用户原图只在豆包理解阶段发送，最终用静态代码合成。生成背景尺寸1728×2304，按需适配最终1600×2133画布。保留输出数量、封面规则、裁剪规则和无动态代码限制。

本地check-keys只检查凭据可读取，不代表联网或模型可用。真实调用需运行对应子命令，不能以配置成功冒称生图成功。
