# 计划文件与脚本

从Skill根目录运行（`python3`替换为环境实际可用、已含Pillow的Python）：

```bash
python3 scripts/render_book.py plan /绝对路径/照片1.jpg /绝对路径/照片2.jpg --cover R01 --out /工作目录/book-plan.json
python3 scripts/render_book.py validate /工作目录/book-plan.json
python3 scripts/render_book.py render /工作目录/book-plan.json --out /成品目录/book-v1
```

`plan --single`开启明确要求的单张模式。计划文件已有时不覆写；渲染输出目录必须为空。报告写在成品目录旁的 `book-v1-report.json`，目录内仅最终PNG。所有相对路径以计划文件所在目录解析。改计划后渲染到新目录，检查完成再交付。

## 顶层字段

| 字段 | 类型/含义 |
|---|---|
| version | 1 |
| mode | book默认；single仅明确单张需求 |
| size | [1600,2133]；直出A系页可[1600,2263] |
| photos | 对象数组：id、path、focus、note；size/palette供视觉模型决策 |
| cover_reference | R01–R05 |
| cover_photo | 默认U01，用户指定才改 |
| cover_color | 可选，覆盖参考封面色的#RRGGBB |
| cover_title | 默认“日常收藏”，建议中文2–8字 |
| background | kind取dots/paper/fiber/dark/navy/gingham/black，或path提供AI背景；path优先 |
| palette | paper/yellow/green/plum/lavender/sage/blue/teal/accent/ink的色值映射 |
| font / font_italic | 可用字体文件绝对路径；不填则探测系统字体；中文要检查字形 |
| story | 语义串联记录，不自动印在图片上 |
| pages | 最终图片数组，长度必须满足数量规则 |

## 单张跨页

```json
{
  "kind": "spread",
  "layout": "diagonal",
  "photos": ["U02", "U03"],
  "colors": ["yellow", "plum"],
  "decor": [],
  "dotted_rings": true,
  "captions": [
    {"page": 0, "at": [0.06, 0.93], "text": "片刻", "size": 0.04},
    {"page": 1, "at": [0.06, 0.07], "text": "余韵", "size": 0.04, "color": "yellow"}
  ]
}
```

`photos`按模板槽位顺序逐一配对，数量必须恰好相同；需要复用时显式写重复ID。`captions`的坐标、字号均相对单页；anchor遵循Pillow（mm居中、la左侧、ra右侧）。标题/旁白没有自动换行，需控制短句并显式插入换行；渲染后检查不会压图或出界。`numbers: true`为非满版照片加编号，必须检查编号是否落到页外，不合适则通过captions定位。

若要自定槽位，用 `slots` 替代 `photos`，仍填最接近的 `layout` 获取页面色与装饰默认值：

```json
{
  "kind": "spread",
  "layout": "full_oval",
  "decor": ["orbit:1"],
  "slots": [
    {"page": 0, "box": [0, 0, 1, 1], "photo": "U02", "style": "none", "focus": [0.45, 0.5]},
    {"page": 1, "box": [0.13, 0.14, 0.75, 0.69], "photo": "U03", "shape": "ellipse", "style": "accent", "crop": [0.1, 0.05, 0.9, 0.95]}
  ]
}
```

`box`为[x,y,w,h]；`crop`为原片归一化[x0,y0,x1,y1]，先裁后适配；`focus`为适配中心。style支持none/line/accent/polaroid/split。split将同一图整体切成顺序连续的两个片段，有间隔，不能填两个不同ID。shape为rect/ellipse。外部素材贴纸未内置，不得写无效字段假装支持。

裁剪用于主动调整构图：当原片景别相近时，用一个槽位的`crop`突出明确主体，其他槽位保留环境或中景，形成疏密与景别变化。通过照片`note`记录裁剪理由。保持`box`的模板几何，避免把主体放大误做成照片框放大。封面如需精确局部裁剪，可在工作目录从U01生成静态裁剪副本，将U01的`path`指向该副本，并在备注保留原路径；不覆盖原片，不增加输入计数。

`decor`支持squares/orbit/ab/dots/stars，各项后缀`:0`或`:1`指定页。可以用空数组去掉装饰以保护主体。默认模板的装饰不可无差别全部启用。

## 两组跨页陈列

```json
{
  "kind": "stack",
  "spreads": [
    {"layout": "full_split", "photos": ["U02", "U03"]},
    {"layout": "diagonal", "photos": ["U04", "U05"]}
  ]
}
```

对应R06等的外层截图，一个stack只算一张输出。照片总覆盖仍须满足计划约束。

## 局部跨页特写

在spread增加 `view_crop: [0.35,0,1,1]`（跨页归一化裁切）。可使用 `mount: [x,y,w,h]` 指定整张成图中的书框；w/h必须与裁后书图的像素宽高比一致，程序会拒绝明显拉伸。默认自动等比居中。特写隐藏的照片不能作为“已清晰出现”计数，需在其他成图展示；程序不自动判断可见覆盖。

## 集合页

`{"kind":"collection","photos":["U01","U02","U03"],"title":"小小收藏","footer":"把日常留在这一页。","color":"yellow"}`

每行最多3张，保持R13的横图比例、细边、图下序号和留白。不为补齐最后一行复制照片。
