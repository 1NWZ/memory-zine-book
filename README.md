# Memory Zine Book · 电子回忆书

将 1–9 张照片编排成明亮、统一的静态照片书：小窗封面、跨页布局、椭圆照片、细框与轻柔书本阴影。AI 辅助理解照片与策划，Python/Pillow 保留原片并精确排版。

A reusable AI skill for turning 1–9 photos into static memory-zine PNGs, with optional Doubao analysis and Seedream backgrounds.

## 功能

- 1 张照片 → 1 张封面；2–3 张 → 2 张成图；4–6 张 → 3 张；7–9 张 → 4 张。
- 支持明确要求的单张集合页；默认输出 1600 × 2133 PNG。
- 原照片裁剪、布局、书脊、页缝、阴影与文字均由代码合成。
- 可选火山方舟照片理解与背景生成；本地排版不需要 API 密钥。
- 输出静态图片，不包含翻页动画、视频或印刷拼版。

## 安装为 Skill

将整个仓库目录放入支持 `SKILL.md` 的代理技能目录。以 Codex 为例，可将仓库克隆到自己的 skills 目录下，并保留所有子目录：

```bash
git clone https://github.com/1NWZ/memory-zine-book.git
cd memory-zine-book
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

需要 Python 3.10+。Windows 可使用 `.venv\Scripts\activate` 激活环境。执行代理应使用此环境的 Python。中文排版需要系统可用的中文字体，也可在计划 `font` 字段指定字体路径。

调用示例：

> 用 memory-zine-book 将这 5 张照片做成一本静态回忆书，第一张作封面，浅米灰背景，不编造时间地点。

## 本地快速运行

在仓库根目录运行，替换为自己的照片绝对路径：

```bash
mkdir -p work
python scripts/render_book.py plan /absolute/photo1.jpg /absolute/photo2.jpg --out work/book-plan.json
python scripts/render_book.py validate work/book-plan.json
python scripts/render_book.py render work/book-plan.json --out work/book-v1
```

`plan` 只生成初始分组与配色建议，需检查主体、裁剪和叙事后再渲染。`--single` 可生成单张方案。计划路径必须未被占用，渲染目录必须为空。所有相对素材路径以计划文件所在目录为基准。

## 可选 AI 模型配置

```bash
cp config/models.example.json config/models.local.json
```

在本地 JSON 填写自己的图片理解和图片生成端点，分别对应豆包 2.0-lite 与 Seedream 5.0 Pro（以账号实际开通的模型为准），再通过环境变量 `ARK_TEXT_API_KEY` 和 `ARK_IMAGE_API_KEY` 提供密钥。不要将真实密钥写入仓库。

```bash
python scripts/ark_book.py check-keys
python scripts/ark_book.py analyze --input /absolute/photo1.jpg --brief '浅米灰背景' --output work/analysis.json
```

分析会将去除 EXIF、缩小后的照片发送至火山方舟；背景生成按需调用远程 API，可能产生费用。脚本不自动重试付费请求。`check-keys` 仅检查本地凭据可读，不验证远程模型是否可用。分析 JSON 是语义建议，需按 [schema](references/schema.md) 合并到渲染计划，不能直接作为渲染输入。

## 文件说明

| 文件 | 用途 |
|---|---|
| [SKILL.md](SKILL.md) | 代理执行规则与成品数量约定 |
| [references/layouts.json](references/layouts.json) | 封面与跨页布局参数 |
| [references/visual-analysis.md](references/visual-analysis.md) | 参考布局的文字分析 |
| [references/production.md](references/production.md) | AI 与静态排版工作流 |
| [references/schema.md](references/schema.md) | 计划字段、裁剪与运行示例 |
| [scripts/render_book.py](scripts/render_book.py) | 本地计划、验证、PNG 渲染 |
| [scripts/ark_book.py](scripts/ark_book.py) | 可选火山方舟客户端 |

## 开源版与原包差异

- 移除本机配置、个人端点 ID 与凭据文件路径，提供通用示例配置。
- 端点从使用者的本地配置读取，不再锁定原作者的端点。
- 不附带原压缩包中的 15 张第三方参考图片；保留布局参数、分析与来源文件名记录。没有原图也可执行本地渲染。

## 许可证与素材

代码及本仓库原创文档采用 [MIT License](LICENSE)。第三方图片、品牌、字体与用户输入照片的权利归各自权利人，MIT 许可证不授予这些素材的使用权。参考来源见 [sources.json](references/sources.json)。项目与参考素材中的品牌无隶属或背书关系。
