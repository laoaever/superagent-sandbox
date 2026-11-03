# 主题说明

主题决定渲染出的公众号 HTML 长什么样。一个主题 = 一个 JSON 文件，**所有值都是字面量**，
因为公众号粘贴会丢弃 CSS 变量、`class`、`<style>`。

## 内置主题

| 文件 | 风格 | 适合 |
|---|---|---|
| `default.json` | 中性、留白、绿色强调 | 大多数文章 |
| `serif.json` | 衬线、砖红、行距更松 | 随笔、观点、深度 |
| `tech.json` | 蓝色、紧凑、代码块突出 | 教程、工具、技术 |

## 结构

```json
{
  "name": "default",
  "display_name": "默认（中性留白）",
  "description": "……",
  "primary_color": "#07c160",
  "color": "#3f3f3f",
  "font_family": "-apple-system, ...",
  "font_size": "16px",
  "line_height": "1.75",
  "styles": {
    "h1": {"font_size": "22px", "font_weight": "700", "margin": "0 0 1.2em", "line_height": "1.4"},
    "h2": {"font_size": "20px", "font_weight": "700", "margin": "2em 0 1em", "line_height": "1.4"},
    "h3": {"font_size": "17px", "font_weight": "700", "margin": "1.6em 0 0.8em", "line_height": "1.5"},
    "p":  {"margin": "0 0 1.5em", "letter_spacing": "0.5px"}
  },
  "x": {
    "code_bg": "rgba(0,0,0,0.05)",
    "quote_bg": "rgba(7,193,96,0.06)",
    "table_head_bg": "rgba(7,193,96,0.08)",
    "heading_number_color": "#07c160",
    "link_color": "#576b95"
  }
}
```

- `styles` 的 key 是标签名，值写成「下划线形式」的 CSS 属性（`font_size` → `font-size`）。
- `x` 是脚本内部使用的补充颜色，未写的项使用内置默认值（见 `theme.py` 的 `DEFAULT_X`）。
- 主题里**不要写**：`class`、`id`、CSS 变量、渐变、`@media`、`position`、`url()` 外部资源。

## 新增主题

1. 复制 `default.json` 改名为新主题（英文小写文件名）。
2. 修改配色与字号，保持规范区间。
3. 运行校验：

```bash
PYTHONPATH=tools python3 -m wechat_sop theme-lint 新主题名
```

4. 在文章 frontmatter 里写 `theme: 新主题名`，或 `render --theme 新主题名` 临时使用。

## 规范（`theme-lint` 强制）

| 项目 | 规则 |
|---|---|
| 正文字号 | 14–18px（15–17px 推荐，越界告警） |
| 行高 | ≥1.6 |
| H1 / H2 字号 | ≤28px / ≤22px |
| 字号梯度 | H1 ≥ H2 ≥ H3 ≥ 正文 |
| 背景 | 不得出现 `linear-gradient` / `radial-gradient` / `conic-gradient` |
| 颜色 | `primary_color` / `color` 必须是 `#rgb`、`#rrggbb`、`#rrggbbaa` 或 `rgb()/rgba()` |
