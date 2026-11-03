# 公众号写作 SOP · 使用说明

> 本目录是「公众号写作流程 SOP」的落地入口：完整规范在 [`../../docs/wechat-sop/`](../../docs/wechat-sop/)，
> 脚本在本目录，零三方依赖（Python 3.8+ 标准库）。

## 1. 五分钟跑通

```bash
# 0) 在仓库根目录，把 tools 加到模块搜索路径（下面所有命令都依赖它）
export PYTHONPATH=tools

# 1) 初始化（首次）
python3 -m wechat_sop init

# 2) 记一条素材、一张选题卡
python3 -m wechat_sop materials add --title "读者反复问排版太花时间" --tags "读者问题" \
    --source "读者群 3 次提问" --points "卡点：样式每篇不一样"
python3 -m wechat_sop topics add --title "公众号排版，别再手调样式了" \
    --angle "排版应该一次配置、长期复用" --audience "每周发 2 篇以上的运营" \
    --material M2026110301

# 3) 立项，按模板生成文章骨架（.md）和大纲（outline.md）
python3 -m wechat_sop topics use T2026110301 --slug my-first-article

# 4) 写大纲（outline.md）→ 写正文（article.md），再检查结构
python3 -m wechat_sop outline articles/2026-11-03-my-first-article/article.md

# 5) 自动修复中文标点与空格（先用 git diff 看改动）
python3 -m wechat_sop format articles/2026-11-03-my-first-article/article.md --write

# 6) 排版：生成公众号 HTML 片段与带「复制到公众号」按钮的预览页
python3 -m wechat_sop render articles/2026-11-03-my-first-article/article.md --open

# 7) 发布前检查（生成 check-report.md，退出码 0 才算通过）
python3 -m wechat_sop check articles/2026-11-03-my-first-article/article.md
```

然后：打开预览页 → 点「复制到公众号」→ 在公众号后台新建图文、粘贴、填标题/摘要/封面 → **人工确认后发布**。

仓库里已经有一篇跑通的示例：[`../../articles/2026-11-03-wechat-typography-workflow/`](../../articles/2026-11-03-wechat-typography-workflow/)。

## 2. 命令一览

| 命令 | 作用 | 主要参数 |
|---|---|---|
| `init` | 初始化 `topics/`、`config/checkwords.txt`、`config/style.md` | `--root` |
| `topics list` | 列出选题与状态 | — |
| `topics add` | 新增选题卡 | `--title --angle --audience --material --reason --difference --words` |
| `topics use` | 立项：校验必需字段并生成文章目录 | `<选题编号> --slug --template --theme --author --force` |
| `topics done` | 标记已发布并记录链接 | `<选题编号> --url` |
| `topics status` | 修改状态 | `<选题编号> draft/planned/writing/published/dropped` |
| `materials list/add` | 素材库 | `--title --tags --source --points --quota` |
| `templates` | 列出写作模板 | — |
| `new` | 直接用模板新建文章（不经过选题库） | `--title/--topic --template --slug --theme --summary --author` |
| `outline` | 输出文章结构树并提示结构问题 | `<文章.md>` |
| `format` | 半角→全角、中英文加空格、加粗标点外移 | `<文章.md> --write` |
| `render` | Markdown → 公众号 HTML 片段 + 预览页 | `<文章.md> --theme --no-numbering --open` |
| `check` | 发布前检查，写 `check-report.md` | `<文章.md> --stage draft/publish --cover --theme --strict` |
| `theme-lint` | 检查主题是否符合排版规范 | `[主题名]` |

退出码：`0` 成功/无阻断项；`1` 有阻断项（`check`）或字段不合规；`2` 参数/文件错误。

## 3. 目录与文件

```
tools/wechat_sop/
├── cli.py           命令行入口
├── frontmatter.py   YAML frontmatter（极简 parser，不依赖 PyYAML）
├── markdown.py      Markdown → 结构块（标题/段落/列表/引用/代码/表格/图片）
├── render.py        结构块 → 公众号 HTML（section + 内联 style + span leaf + 脚注）
├── preview.py       带「复制到公众号」按钮的预览页外壳
├── theme.py         主题加载、样式生成、排版规范校验
├── check.py         发布前检查（阻断项 / 风险项）
├── textfmt.py       中文标点与空格修复
├── library.py       选题库/素材库
├── templates.py     写作模板
└── themes/          default.json / serif.json / tech.json
tools/tests/         pytest 用例（81 个）
topics/              选题库与素材库（仓库数据）
articles/            每篇文章一个目录
config/              checkwords.txt（敏感词）、style.md（写作风格）
```

## 4. 主题

主题是 `themes/*.json`，每个标签一组内联样式参数。修改后运行 `theme-lint` 确认没有越界：

```bash
python3 -m wechat_sop theme-lint
```

| 项目 | 规范 |
|---|---|
| 正文字号 | 14–18px（推荐 15–17px） |
| 行高 | ≥1.6（推荐 1.7–1.9） |
| H1 / H2 | ≤28px / ≤22px |
| 字号梯度 | H1 ≥ H2 ≥ H3 ≥ 正文 |
| 背景 | 禁止渐变（公众号深色模式会报错） |
| 颜色 | 必须写在主题里，只允许一个强调色 |

## 5. 渲染产物的硬约束

`render` 输出的 HTML 满足以下约束（由 `check` 在发布前复检，也有单测保护）：

- 只使用 `<section>`，不使用 `<div>`、`<style>`、`<script>`、`class`、`id`；
- 所有样式内联，不使用 CSS 变量、`@media`、`@keyframes`、`position`、渐变；
- 文本节点用 `<span leaf="">` 包裹，避免粘贴后掉样式；
- 列表不用 `<ul>/<ol>`，逐项渲染为带符号段落并保留嵌套（防止粘贴时结构被打散）；
- 图片宽度内联为 `style="width:100%"`，不依赖 `width` 属性；
- 外部链接自动转文末脚注，公众号内链保持可点；
- 代码块为深色卡片、带语言标签与行号，行内横向滚动；
- 表格包在可横滑的容器里。

## 6. 边界：脚本不发布

`wechat_sop` **没有**任何发布相关命令：不存草稿、不上传图片、不群发、不写公众号后台。
`check` 里的 `publish_confirm` 阻断项只能由人在 frontmatter 中改为 `true` —— 脚本只读不写。

## 7. 测试

```bash
cd tools && python3 -m pytest tests -q
```

覆盖：frontmatter/YAML 子集、Markdown 结构解析、渲染的公众号兼容性约束、主题 lint、
格式修复、发布前检查各检查项、CLI 全流程（在临时目录副本里跑）。
