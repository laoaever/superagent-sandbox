"""结构块 → 公众号可直接粘贴的 HTML。

设计约束（来自市面工具踩坑总结，见 docs/wechat-sop/00-research.md）：

1. 只输出 `<section>` 结构，不用 `<div>`；
2. 所有样式内联在 `style` 属性里，不用 `class` / `id` / `<style>` / CSS 变量 / 渐变；
3. 文本节点用 `<span leaf="">` 包裹（公众号编辑器对裸文本会重新套样式）；
4. 外部链接转脚注，正文只保留公众号内链；
5. 列表不用 `<ul>/<ol>`，逐项转成带符号的 `<p>`（规避粘贴时列表结构被打散），嵌套列表缩进在父项内部；
6. 图片宽高内联进 `style`，不依赖 `width`/`height` 属性；
7. 代码块做成固定宽度卡片，横向滚动，行号与代码用 float + 左外边距两栏排布（不用 flex，兼容性更稳）；
8. 表格包一层可横滑的容器，列多时手机不挤。
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

from . import markdown as md
from .theme import heading_number_style, merge_styles

WECHAT_HOSTS = ("mp.weixin.qq.com", "weixin.qq.com")


_SIMPLE_HIGHLIGHT = {
    "comment": re.compile(r"(#.*)$"),
    "string": re.compile(r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"),
    "number": re.compile(r"\b(\d+(?:\.\d+)?)\b"),
    "keyword": re.compile(
        r"\b(def|class|return|import|from|if|elif|else|for|while|try|except|finally|with|as|"
        r"function|const|let|var|new|export|default|async|await|yield|null|None|True|False|"
        r"true|false|undefined|this|self|lambda|pass|raise|in|is|not|and|or)\b"
    ),
}


def escape(text: str) -> str:
    return html.escape(text, quote=True)


@dataclass
class RenderResult:
    body: str
    footnotes: List[Tuple[str, str, str]] = field(default_factory=list)
    heading_count: int = 0
    image_count: int = 0


class WechatRenderer:
    """把 Markdown 文档渲染为公众号 HTML 片段。"""

    def __init__(self, theme: Dict[str, Any], *, numbered_headings: bool = True,
                 footnote_title: str = "参考链接", cover_caption: bool = True) -> None:
        self.theme = theme
        self.styles = theme.get("styles", {})
        self.x = theme["x"]
        self.numbered_headings = numbered_headings
        self.footnote_title = footnote_title
        self.footnotes: List[Tuple[str, str, str]] = []
        self._footnote_index: Dict[str, int] = {}
        self._h2_count = 0

    # ------------------------------------------------------------ 基础样式

    def base_inline(self) -> str:
        return merge_styles({}, {
            "font-size": self.theme["font_size"],
            "line-height": self.theme["line_height"],
            "color": self.theme["color"],
        })

    def styled(self, inline_style: str, inner: str, tag: str = "section") -> str:
        if inline_style:
            return '<%s style="%s">%s</%s>' % (tag, inline_style, inner, tag)
        return "<%s>%s</%s>" % (tag, inner, tag)

    def tag_style(self, tag: str, **extra: Any) -> str:
        return merge_styles({}, self.styles.get(tag, {}), extra)

    # ------------------------------------------------------------ 行内

    def inline(self, nodes: Sequence[md.Inline], ctx: Dict[str, bool]) -> str:
        out: List[str] = []
        for node in nodes:
            out.append(self.inline_node(node, ctx))
        return "".join(out)

    def inline_node(self, node: md.Inline, ctx: Dict[str, bool]) -> str:
        if isinstance(node, md.Text):
            return self.leaf("".join(node.value))
        if isinstance(node, md.Code):
            return '<code style="%s">%s</code>' % (self.code_style(), escape(node.value))
        if isinstance(node, md.Strong):
            return '<strong style="%s">%s</strong>' % (
                "color:%s;font-weight:700" % self.theme["primary_color"],
                self.inline(node.children, ctx),
            )
        if isinstance(node, md.Emph):
            return '<em style="font-style:italic">%s</em>' % self.inline(node.children, ctx)
        if isinstance(node, md.Strike):
            return '<span style="text-decoration:line-through;color:%s">%s</span>' % (
                self.x["text_secondary"], self.inline(node.children, ctx))
        if isinstance(node, md.Link):
            return self.link(node, ctx)
        if isinstance(node, md.Image):
            return self.image(node, block=True)
        return self.leaf(str(getattr(node, "value", "")))

    def leaf(self, text: str) -> str:
        return '<span leaf="">%s</span>' % escape(text)

    def code_style(self) -> str:
        return (
            "font-family:Menlo,Consolas,Monaco,'Courier New',monospace;font-size:90%%;"
            "padding:2px 5px;border-radius:3px;background:%s;color:%s"
            % (self.x["code_bg"], self.x["code_text"])
        )

    def link(self, node: md.Link, ctx: Dict[str, bool]) -> str:
        href = node.href.strip()
        text = self.leaf(node.text)
        if self._is_wechat_link(href):
            return '<a href="%s" style="color:%s;text-decoration:none">%s</a>' % (
                escape(href), self.x["link_color"], text)
        index = self._footnote_index.get(href)
        if index is None:
            index = len(self.footnotes) + 1
            self._footnote_index[href] = index
            self.footnotes.append((node.title or node.text, href, node.text))
        sup = '<sup style="font-size:75%%;color:%s;vertical-align:super">[%d]</sup>' % (
            self.theme["primary_color"], index)
        return '<span style="color:%s">%s</span>%s' % (self.x["link_color"], text, sup)

    @staticmethod
    def _is_wechat_link(href: str) -> bool:
        lowered = href.lower()
        if lowered.startswith("mailto:"):
            return True
        for host in WECHAT_HOSTS:
            if lowered.startswith("https://%s" % host) or lowered.startswith("http://%s" % host):
                return True
        return lowered.startswith("weixin://")

    def image(self, node: md.Image, block: bool = False) -> str:
        alt = escape(node.alt or "图片")
        if block:
            return (
                '<section style="text-align:center;margin:1.5em 0">'
                '<img src="%s" alt="%s" style="width:100%%;max-width:100%%;height:auto;'
                'border-radius:6px;display:block;margin:0 auto">'
                "</section>" % (escape(node.src), alt)
            )
        return '<img src="%s" alt="%s" style="max-width:100%%;height:auto;vertical-align:middle">' % (
            escape(node.src), alt)

    # ------------------------------------------------------------ 块

    def render_document(self, doc: md.Document) -> RenderResult:
        self.footnotes = []
        self._footnote_index = {}
        self._h2_count = 0
        image_count = 0
        has_h2 = any(isinstance(b, md.Heading) and b.level == 2 for b in doc.blocks)

        if not has_h2:
            chunks: List[str] = []
            for block in doc.blocks:
                chunks.append(self.render_block(block))
                if isinstance(block, md.ImageBlock):
                    image_count += 1
            if self.footnotes:
                chunks.append(self.render_footnotes())
            body = '<section style="%s">%s</section>' % (self.base_inline(), "".join(chunks))
            return RenderResult(
                body=body,
                footnotes=list(self.footnotes),
                heading_count=sum(1 for b in md.iter_blocks(doc.blocks) if isinstance(b, md.Heading)),
                image_count=image_count,
            )

        sections: List[List[str]] = [[]]
        for block in doc.blocks:
            if isinstance(block, md.Heading) and block.level == 2:
                sections.append([self.render_heading(block)])
                continue
            sections[-1].append(self.render_block(block))
            if isinstance(block, md.ImageBlock):
                image_count += 1
        parts = [
            '<section style="%s">%s</section>' % (merge_styles({}, {"margin": "0 0 1.5em"}), "".join(chunk))
            for chunk in sections
            if chunk
        ]
        if self.footnotes:
            parts.append(self.render_footnotes())
        body = '<section style="%s">%s</section>' % (self.base_inline(), "".join(parts))
        return RenderResult(
            body=body,
            footnotes=list(self.footnotes),
            heading_count=sum(1 for b in md.iter_blocks(doc.blocks) if isinstance(b, md.Heading)),
            image_count=image_count,
        )

    def render_blocks(self, blocks: Sequence[md.Block]) -> str:
        return "".join(self.render_block(b) for b in blocks)

    def render_block(self, block: md.Block) -> str:
        ctx: Dict[str, bool] = {}
        if isinstance(block, md.Heading):
            return self.render_heading(block)
        if isinstance(block, md.Paragraph):
            inner = self.inline(block.inlines, ctx)
            return "<p style=\"%s\">%s</p>" % (self.tag_style("p"), inner)
        if isinstance(block, md.ListBlock):
            return self.render_list(block, depth=0)
        if isinstance(block, md.Quote):
            return self.render_quote(block)
        if isinstance(block, md.CodeBlock):
            return self.render_code_block(block)
        if isinstance(block, md.Table):
            return self.render_table(block)
        if isinstance(block, md.ImageBlock):
            return self.image(block.image, block=True) + self.image_alt_caption(block.image)
        if isinstance(block, md.ThematicBreak):
            return '<hr style="border:none;border-top:1px solid %s;margin:2em 0">' % self.x["border_color"]
        return ""

    def image_alt_caption(self, node: md.Image) -> str:
        if not node.alt:
            return ""
        return ('<section style="text-align:center;margin:-0.8em 0 1.8em">'
                '<span style="font-size:13px;color:%s">%s</span></section>'
                % (self.x["text_secondary"], self.leaf(node.alt)))

    def render_heading(self, block: md.Heading) -> str:
        ctx: Dict[str, bool] = {}
        inner = self.inline(block.inlines, ctx)
        if block.level == 1:
            return '<h1 style="%s">%s</h1>' % (self.tag_style("h1"), inner)
        if block.level == 2:
            self._h2_count += 1
            prefix = ""
            if self.numbered_headings and self._h2_count < 10:
                prefix = '<span style="%s">%02d</span>' % (
                    heading_number_style(self.theme, self.styles.get("h2", {})),
                    self._h2_count,
                )
            bar = ('<span style="display:inline-block;width:4px;height:0.95em;'
                   'background:%s;margin-right:8px;vertical-align:-0.1em;border-radius:2px"></span>'
                   % self.theme["primary_color"])
            return '<h2 style="%s">%s%s%s</h2>' % (self.tag_style("h2"), bar, prefix, inner)
        bullet = ('<span style="color:%s;margin-right:6px">#</span>' % self.theme["primary_color"])
        return '<h3 style="%s">%s%s</h3>' % (self.tag_style("h3"), bullet, inner)

    def render_list(self, block: md.ListBlock, depth: int) -> str:
        ctx: Dict[str, bool] = {}
        items: List[str] = []
        for index, item in enumerate(block.items, start=block.start):
            marker = ("%d." % index) if block.ordered else ("•" if depth == 0 else "◦")
            marker_span = ('<span style="color:%s;font-weight:600;margin-right:6px">%s</span>'
                           % (self.theme["primary_color"], marker))
            content_parts: List[str] = []
            for sub in item.blocks:
                if isinstance(sub, md.Paragraph):
                    content_parts.append(self.inline(sub.inlines, ctx))
                elif isinstance(sub, md.ListBlock):
                    content_parts.append(
                        '<section style="margin-top:0.4em">%s</section>'
                        % self.render_list(sub, depth + 1))
                elif isinstance(sub, md.CodeBlock):
                    content_parts.append(self.render_code_block(sub))
                else:
                    content_parts.append(self.render_block(sub))
            items.append(
                '<p style="%s">%s%s</p>' % (
                    self.tag_style("p", margin="0 0 0.6em"),
                    marker_span,
                    "".join(content_parts),
                )
            )
        return '<section style="margin:0 0 1.5em">%s</section>' % "".join(items)

    def render_quote(self, block: md.Quote) -> str:
        ctx: Dict[str, bool] = {}
        inner_parts: List[str] = []
        for sub in block.blocks:
            if isinstance(sub, md.Paragraph):
                inner_parts.append(
                    '<p style="%s">%s</p>' % (
                        self.tag_style("p", margin="0 0 0.5em", color=self.x.get("text_secondary", "#666")),
                        self.inline(sub.inlines, ctx),
                    )
                )
            elif isinstance(sub, md.ListBlock):
                inner_parts.append(self.render_list(sub, 0))
            else:
                inner_parts.append(self.render_block(sub))
        inner = "".join(inner_parts)
        return (
            '<section style="margin:0 0 1.5em;padding:12px 16px;background:%s;'
            'border-left:4px solid %s;border-radius:4px">%s</section>'
            % (self.x["quote_bg"], self.theme["primary_color"], inner)
        )

    def render_code_block(self, block: md.CodeBlock) -> str:
        return render_code_block_html(block.lang, block.code, self.x)

    def render_table(self, block: md.Table) -> str:
        ctx: Dict[str, bool] = {}
        align_map = {"center": "center", "right": "right", "left": "left", "": "left"}
        head_cells = []
        for index, cell in enumerate(block.header):
            align = align_map.get(block.align[index] if index < len(block.align) else "", "left")
            head_cells.append(
                '<th style="padding:8px 10px;border:1px solid %s;background:%s;'
                'text-align:%s;font-weight:700;white-space:nowrap">%s</th>'
                % (self.x["border_color"], self.x["table_head_bg"], align, self.inline(cell, ctx))
            )
        rows_html = []
        for row_index, row in enumerate(block.rows):
            cells = []
            for index, cell in enumerate(row):
                align = align_map.get(block.align[index] if index < len(block.align) else "", "left")
                bg = self.x["table_stripe_bg"] if row_index % 2 == 1 else "#ffffff"
                cells.append(
                    '<td style="padding:8px 10px;border:1px solid %s;background:%s;'
                    'text-align:%s">%s</td>'
                    % (self.x["border_color"], bg, align, self.inline(cell, ctx))
                )
            rows_html.append("<tr>%s</tr>" % "".join(cells))
        table = (
            '<table style="border-collapse:collapse;width:100%%;font-size:14px">'
            "<thead><tr>%s</tr></thead><tbody>%s</tbody></table>"
            % ("".join(head_cells), "".join(rows_html))
        )
        return (
            '<section style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 1.5em">'
            "%s</section>" % table
        )

    def render_footnotes(self) -> str:
        items = []
        for index, (title, href, text) in enumerate(self.footnotes, start=1):
            items.append(
                '<p style="margin:0 0 0.5em;font-size:13px;line-height:1.6;color:%s;'
                'word-break:break-all">[%d] %s：%s</p>'
                % (self.x["footnote_color"], index, self.leaf(title or text), self.leaf(href))
            )
        return (
            '<section style="margin:2em 0 0;padding-top:1em;border-top:1px solid %s">'
            '<p style="margin:0 0 0.6em;font-size:13px;color:%s;font-weight:700">%s</p>'
            "%s</section>"
            % (self.x["border_color"], self.x["text_secondary"], self.leaf(self.footnote_title), "".join(items))
        )


def highlight_code(code: str, lang: str, x: Dict[str, str]) -> str:
    """极简高亮：先切分「注释 / 字符串」，再在其余部分标记关键字与数字。

    切分使用稳定占位符（不会与正文冲突），避免正则互相污染。
    """
    if lang in ("text", "plain", "plaintext", "markdown", "md", "output", ""):
        return escape(code)
    colors = {
        "string": x["code_block_string"],
        "comment": x["code_block_comment"],
        "number": x["code_block_number"],
        "keyword": x["code_block_keyword"],
    }
    literal = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")
    comment = re.compile(r"(?:#|//).*$") if lang not in ("html", "xml", "css", "yaml", "yml", "ini", "toml") else None
    keyword = _SIMPLE_HIGHLIGHT["keyword"]
    number = re.compile(r"\b\d+(?:\.\d+)?\b")

    def paint(fragment: str, color: str) -> str:
        return _PAINT_COLOR(color) + escape(fragment) + _PAINT_CLOSE

    segments: List[str] = []
    index = 0
    for match in literal.finditer(code):
        segments.append(_paint_rest(code[index:match.start()], colors, keyword, number))
        segments.append(paint(match.group(0), colors["string"]))
        index = match.end()
    tail = code[index:]
    if comment is not None:
        found = comment.search(tail)
        if found:
            segments.append(_paint_rest(tail[:found.start()], colors, keyword, number))
            segments.append(paint(found.group(0), colors["comment"]))
            tail = ""
    if tail:
        segments.append(_paint_rest(tail, colors, keyword, number))
    return _restore_paint("".join(segments))


def _paint_rest(text: str, colors: Dict[str, str], keyword: "re.Pattern[str]",
                number: "re.Pattern[str]") -> str:
    """处理非字符串片段：关键字与数字各自加色，其余转义。"""
    pattern = re.compile("(%s|%s)" % (keyword.pattern, number.pattern))
    out: List[str] = []
    position = 0
    for match in pattern.finditer(text):
        out.append(escape(text[position:match.start()]))
        token = match.group(0)
        color = colors["keyword"] if keyword.fullmatch(token) else colors["number"]
        out.append(_PAINT_COLOR(color) + escape(token) + _PAINT_CLOSE)
        position = match.end()
    out.append(escape(text[position:]))
    return "".join(out)


# 高亮占位符：\x00 表示「开一个色块」，\x01 表示「关掉色块」。
# 颜色值在占位符生成时就写进去，所以还原只是替换成真实标签。
_PAINT_OPEN = '\x00<span style="color:'
_PAINT_MID = '">'
_PAINT_CLOSE = '\x01'


def _PAINT_COLOR(color: str) -> str:
    return _PAINT_OPEN + color + _PAINT_MID


def _restore_paint(html: str) -> str:
    while "\x00" in html:
        start = html.index("\x00")
        mid = html.index(_PAINT_MID, start)
        end = html.index(_PAINT_CLOSE, mid)
        color = html[start + len(_PAINT_OPEN):mid]
        body = html[mid + len(_PAINT_MID):end]
        html = html[:start] + '<span style="color:%s">%s</span>' % (color, body) + html[end + 1:]
    return html


def render_code_block_html(lang: str, code: str, x: Dict[str, str]) -> str:
    code = code if code else " "
    lines = code.split("\n")
    number_html = "".join(
        '<span style="display:block;color:%s;text-align:right;user-select:none">%d</span>'
        % (x["code_block_comment"], i)
        for i in range(1, len(lines) + 1)
    )
    code_html = "".join(
        '<span style="display:block;min-height:1.5em;white-space:pre">%s</span>'
        % (highlight_code(line, lang, x) or "&#8203;")
        for line in lines
    )
    lang_label = ""
    if lang:
        lang_label = (
            '<section style="padding:6px 12px 0;font-size:11px;letter-spacing:1px;'
            'text-transform:uppercase;color:%s"><span leaf="">%s</span></section>'
            % (x["code_block_comment"], escape(lang))
        )
    return (
        '<section style="margin:0 0 1.5em;background:%(bg)s;border-radius:6px;overflow:hidden">'
        "%(label)s"
        '<section style="padding:10px 0 12px;overflow-x:auto;-webkit-overflow-scrolling:touch">'
        '<section style="float:left;width:2.4em;text-align:right;font-family:Menlo,Consolas,Monaco,monospace;'
        'font-size:12px;line-height:1.6;opacity:0.6">%(numbers)s</section>'
        '<section style="margin-left:3.4em;padding-right:14px;font-family:Menlo,Consolas,Monaco,monospace;'
        'font-size:12.5px;line-height:1.6;color:%(fg)s">%(code)s</section>'
        '<section style="clear:both"></section>'
        "</section></section>"
        % {
            "bg": x["code_block_bg"],
            "label": lang_label,
            "numbers": number_html,
            "fg": x["code_block_text"],
            "code": code_html,
        }
    )


def render_markdown(text: str, theme: Dict[str, Any], **options: Any) -> RenderResult:
    doc = md.parse_markdown(text)
    renderer = WechatRenderer(theme, **options)
    return renderer.render_document(doc)
