# 公众号写作工具调研：市面做法与可吸收经验

> 调研时间：2026-11
> 调研方式：GitHub 公开仓库源码阅读（README、核心转换逻辑、校验脚本、发布脚本），未使用任何付费/私有服务。
> 目的：在设计本仓库的「公众号写作流程 SOP + 配套脚本」之前，先把市面上同类工具/插件的做法摸清，能用经验直接吸收，没必要自己重新发明。

## 1. 结论先行

1. **市面工具解决的核心问题只有一个**：`Markdown → 内联样式 HTML（section 结构）`，因为微信编辑器会剥离 `<style>`、`class`、`id`、`<div>`。
2. **写作侧的主流做法已经是「Agent Skill」形态**：把写作规范、配图规范、排版规则、校验脚本打包成一份带 `SKILL.md` 的目录，交给 AI Agent 按流程执行，而不是做一个复杂的 SaaS。
3. **质量靠「确定性脚本兜底」**：几乎每个成熟项目都有排版的 `validate` 脚本（禁用标签、半角标点、`<span leaf>` 包裹），以及发布前的 `inspect`（标题/摘要/封面/草稿就绪度检查）。
4. **发布环节的共识是「脚本只准备，人确认发布」**：要么生成可粘贴 HTML，要么调草稿箱 API 停在草稿，没有人把「群发」自动化。这与本需求「发布写成人工确认步骤」完全一致。
5. **可吸收进本仓库的能力（已在脚本中落地）**：
   - 公众号兼容 HTML 的硬约束（`section` / 内联 style / 不依赖 class 与 `<style>`）。
   - 外链转脚注（正文只保留公众号内链可点）。
   - 图片 `width` 属性/`<style>` 宽度在粘贴后丢失，必须内联到 `style`。
   - 代码块宽度溢出、行内代码等宽字体处理。
   - 浅色主题 + 纯色背景（渐变背景在公众号深色模式下会出问题）。
   - 半角标点 → 全角，中英文之间加空格，加粗标记与中文标点位置修正。
   - 标题 ≤64 字硬限（API）、30 字展示截断。
   - 图片必须走 `mmbiz.qpic.cn`，外链图片需落地。
   - 发布前清单可脚本化：标题、摘要、字数、封面、图片缺失、敏感词。

## 2. 调研对象总览

| 项目 | Stars | 形态 | 技术栈 | 许可证 | 最近更新 | 核心能力 |
|---|---|---|---|---|---|---|
| [doocs/md](https://github.com/doocs/md) | 13.5k | Web 编辑器 / Chrome 扩展 / CLI / Docker | Vue3 + TS | WTFPL | 2026-11 | 主题化 Markdown 渲染、一键复制到公众号、图床、MCP Server |
| [lyricat/wechat-format](https://github.com/lyricat/wechat-format) | 4.6k | 单页 Web 工具 | Vue2 + marked | 未声明 | 2025-09 | 微信特制 HTML 渲染器：外链转脚注、列表改造、代码块改造 |
| [isjiamu/gzh-design-skill](https://github.com/isjiamu/gzh-design-skill) | 4.2k | AI Agent Skill | Python 脚本 + Markdown 组件库 | AGPL-3.0 | 2026-10 | 主题组件库、双关卡校验（组件 lint + 产物校验）、预览页一键复制 |
| [geekjourneyx/md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill) | 3.8k | AI Agent CLI | Go | Source Available | 2026-10 | `inspect` 发布前检查、`convert`、草稿箱、标题建议、品牌档案 |
| [xiaohuailabs/xiaohu-wechat-format](https://github.com/xiaohuailabs/xiaohu-wechat-format) | 0.7k | Claude Code Skill | Python | 未声明 | 2026-06 | 排版 + 封面 + 草稿箱发布，主题 JSON + 主题 lint、中文标点修复器 |
| [joeseesun/qiaomu-publish](https://github.com/joeseesun/qiaomu-publish) | 45 | Obsidian 插件 | TS | MIT | 2026-11 | 在笔记软件内直接预览排版并推送草稿 |
| [tianyaxiang/neurapress](https://github.com/tianyaxiang/neurapress) | 1.8k | Web 编辑器 | Next.js | — | — | 实时预览、模板系统、一键复制 |

> 许可证提醒：`gzh-design-skill` 为 AGPL-3.0、`md2wechat` 为 Source Available，**这两者只适合借鉴思路，不适合复制代码**。本仓库的脚本为独立实现，未拷贝上述仓库源码。

## 3. 逐个拆解：它们各自解决什么、怎么解决

### 3.1 doocs/md —— 「样式注入 + 复制时再内联」的代表

- **渲染**：`marked` + 自定义扩展（alert/callout、KaTeX、Mermaid、Ruby 注音、emoji、slider），产出带 class 的 HTML。
- **主题**：主题是一个 CSS 文件（`base.css` + `default.css` 等），用 `wrapCSSWithScope()` 给所有选择器加 `#output` 前缀，再 `processCSS()` 把 `var(--x)`、`calc()` 全部求值成字面量。**这正是「不能依赖 CSS 变量」的工程解法**：在写入剪贴板前把变量全部展开。
- **复制到微信**：克隆预览节点 → `sanitizeHtmlCssForJuice()` 清洗 juice 解析不了的 CSS → `juice({ inlinePseudoElements: true, preserveImportant: true })` 把样式内联到每个元素 → 保留 `<style>` 兜底。
- **粘贴后的兼容修补（很多是踩坑总结）**：
  - `<li><ul>` 嵌套列表被微信打散 → `modifyHtmlStructure()` 把子列表提到 `li` 后面。
  - `img` 的 `width`/`height` 属性会被丢弃 → `solveWeChatImage()` 改成内联 `style`。
  - Mermaid 的 `foreignObject` 内 `div` 被丢弃 → `promoteSvgHtmlLabels()` 换成 `section`。
  - 字体名含空格/中文时 juice 解析失败 → 统一加引号。
- **SVG 约束**：仓库内 `.agents/skills/wechat-svg/SKILL.md` 记录了微信 SVG 的 AttributeName 白名单，以及「不使用 id/class/defs/`url(#id)`、箭头 marker 展开成 path、显式像素宽高」等硬约束。
- **可吸收**：`section` 优先、`li` 嵌套修补、`img` 尺寸内联、变量在输出前求值、SVG 不使用 id/class 与 defs。

### 3.2 lyricat/wechat-format —— 「直接用内联 style 渲染」的代表

- 不用 CSS + 后处理，而是让渲染器对每个 token 直接输出 `style="..."`：`S('h2')`、`S('p')`、`S('listitem')`……
- **外链转脚注**：正文里的非 `https://mp.weixin.qq.com` 链接被替换为「文字 + 上标序号」，文末生成 References 列表。原因：公众号正文里外部链接不可点击（会被提示「网页链接」），放在脚注里才可读。
- **列表不用 `<ul>`/`<ol>`**：`renderer.list()` 直接把列表渲染成 `<p>` 里的 `•`/`1.` 文本，并在 `listitem` 上做 `text-indent: -20px` 悬挂缩进 —— 规避微信对列表的内部改写的做法。
- **代码块**：用 `<section><ul>` 行号 + `<pre><code>` 逐行 `<span>` 的「代码卡片」结构。
- **可吸收**：外链脚注；列表退化；`<section>` 卡片式代码块。

### 3.3 isjiamu/gzh-design-skill —— 「Agent 流程 + 确定性校验」的代表

- **流程化**：`SKILL.md` 把「输入归一化 → 选主题 → 读组件库 → 解析结构 → 按配方装配 → 校验 → 输出」写成六步，每步都有明确输入输出。
- **格式归一化**：Word/PDF/纯文本/网页先转 Markdown，并且**结构确认后才继续**（「识别出 N 个章节……结构对吗？」），避免整篇返工。
- **校验脚本 `validate_gzh_html.py`** 是本调研中最完整的「公众号 HTML 合规检查」实现：
  - ERROR：`<style>`、`<script>`、`<div>`、`<link>`、`class`、`id`、`position:fixed/absolute/sticky`、`float`、`@media`、`@keyframes`、`@import`、`display:grid`、`var(--x)`、外部字体。
  - WARNING：`<span leaf>` 缺失（粘贴后掉样式的关键）、中文后半角标点、渐变背景（触发微信 `darkmode-no-gradient` 弹窗）。
- **产物规范**：输出纯 `<section>…</section>` 片段，不带 `<!DOCTYPE>/<html>/<head>`；另有 `wrap_preview.py` 生成带「复制」按钮的预览页。
- **可吸收**：禁用清单原样可用；`<span leaf>` 是很有用的粘贴保真技巧（微信编辑器对纯文本节点会重新套样式，包裹后更稳）；输出片段而非整页。

### 3.4 geekjourneyx/md2wechat —— 「发布前检查」的代表

- `inspect article.md --json` 输出「标题、摘要、图片、cover、draft readiness」——把发布前清单做成机器可读的检查项。
- 标题建议不调模型，只生成 prompt 交给人/Agent；**最终标题要人确认**。
- Brand Profile（`brand.md`）：用自然语言写给 Agent 的「我是谁、怎么说话」，比结构化配置更适合风格。
- **可吸收**：发布前检查的字段设计（标题长度、摘要、封面、图片可达性、草稿就绪度）；写作风格档案用 Markdown 自然语言描述。

### 3.5 xiaohuailabs/xiaohu-wechat-format —— 「主题即数据 + 草稿箱发布」的代表

- **主题是 JSON**：`styles` 里按标签给 `font_size` / `line_height` / `margin` 等，`build_style_string()` 直接把字典转成内联 style。
- **`theme_lint.py`**：主题设计规则的自动化检查——正文字号 15–17px、行高 ≥1.7、字号梯度不倒置、H1 ≤28px、H2 ≤22px（手机正文宽约 345px）。这是非常实用的「排版规范可执行化」样本。
- **`zh_punctuation_fix.py`**：半角 → 全角标点修复，且**先保护**代码块、行内码、URL、链接地址。
- `fix_cjk_spacing()`：中英文/中数字之间加空格，同样先保护代码与链接。
- `fix_cjk_bold_punctuation()`：`**文字，**` → `**文字**，`，修掉加粗标记吞掉中文标点的问题。
- **草稿箱 API 细节**（`publish.py`）：
  - `cgi-bin/token` 取 token；`cgi-bin/material/add_material?type=image` 上传封面得 `media_id`；`cgi-bin/media/uploadimg` 上传正文图得 `mmbiz.qpic.cn` URL；`cgi-bin/draft/add` 建草稿。
  - 常见错误码处理：`40164` IP 不在白名单、`40001/40125` AppSecret 错误。
  - **正文图片必须是微信 CDN 地址**，本地图/外链图都要先上传替换。
  - `json.dumps(ensure_ascii=False)`，否则中文转义导致长度计算异常。
  - 标题 64 字符是 API 硬限，>30 字会展示截断。
- **可吸收**：主题 lint 阈值、标点/空格修复规则、草稿箱 API 必知点（写进 SOP 的发布章节，但脚本不做自动发布）。

### 3.6 joeseesun/qiaomu-publish / neurapress

- 共同点：**把预览放在写作现场**（Obsidian / 编辑器内实时预览），减少「写完再搬去另一个编辑器」的损耗。
- 排版按篇记忆、一键复制、模板切换是标配。
- **可吸收**：SOP 应把「预览」内嵌进写作环节，而不是最后一次性排版；模板/主题按文章类型固定，避免每篇重新调样式。

## 4. 共性坑位清单（沉淀为脚本规则）

| 坑 | 现象 | 处理 | 来源 |
|---|---|---|---|
| `<style>` / `class` / `id` | 粘贴后样式全丢 | 全部内联；不输出这两个属性 | doocs/md, gzh-design |
| `<div>` | 被改写 | 一律用 `<section>` | gzh-design |
| CSS 变量 `var()` | 不支持 | 输出前展开为字面量 | doocs/md |
| 嵌套列表 `<li><ul>` | 结构被打散 | 子列表提到 `li` 之后 | doocs/md |
| `img width` 属性 | 被丢弃 | 内联 `style` 宽高 | doocs/md |
| 外部链接 | 不可点击 | 转脚注 | wechat-format |
| 代码块 | 溢出/宽度异常 | 固定宽度卡片、`overflow-x:auto`、等宽字体 | wechat-format, doocs/md |
| 渐变背景 | 深色模式报错 | 用纯色/rgba 纯色 | gzh-design |
| 半角标点 | 观感差 | 中文上下文转全角，保护代码/URL | xiaohu |
| 中英文粘连 | 观感差 | 加空格，保护代码/URL | xiaohu |
| 标题过长 | 截断/API 报错 | 软限 30 字、硬限 64 字 | xiaohu, md2wechat |
| 外链图片 | 公众号不显示 | 必须先落地到 `mmbiz.qpic.cn` | xiaohu |
| 纯文本节点 | 粘贴掉样式 | `<span leaf>` 包裹 | gzh-design |
| SVG `id/class/defs` | 箭头消失、样式失效 | 展开为内联 path/属性 | doocs/md |

## 5. 本仓库方案定位

| 维度 | 市面工具 | 本仓库 SOP + 脚本 |
|---|---|---|
| 覆盖范围 | 多数只管「排版」 | 选题 → 大纲 → 成文 → 排版 → 配图 → 发布前检查，全流程 |
| 交互形态 | Web 编辑器 / Agent Skill | 仓库内目录 + 命令行脚本（零三方依赖），人对每个环节确认 |
| 发布 | 部分工具直接推草稿箱 | **只准备到「粘贴即可」，发布人工确认** |
| 素材管理 | 工具内私有数据 | 仓库内文件（选题库/素材库/文章目录），可版本化、可 review |
| 校验 | 排版合规 | 排版合规 + 发布前清单（标题/字数/摘要/封面/图片/敏感词/风格） |

## 6. 参考链接

- doocs/md：<https://github.com/doocs/md>
- lyricat/wechat-format：<https://github.com/lyricat/wechat-format>
- isjiamu/gzh-design-skill：<https://github.com/isjiamu/gzh-design-skill>
- geekjourneyx/md2wechat-skill：<https://github.com/geekjourneyx/md2wechat-skill>
- xiaohuailabs/xiaohu-wechat-format：<https://github.com/xiaohuailabs/xiaohu-wechat-format>
- joeseesun/qiaomu-publish：<https://github.com/joeseesun/qiaomu-publish>
- tianyaxiang/neurapress：<https://github.com/tianyaxiang/neurapress>
