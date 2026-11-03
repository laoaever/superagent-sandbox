"""Markdown → 结构块。

只支持公众号写作会用到的语法子集，目标是**结构稳定、可预测**：

- 标题 `#` ~ `######`（可带 `{#id}` 忽略 id）
- 段落（段内换行保留）
- 列表（有序/无序，可嵌套；任务列表 `- [ ]` 视为普通项）
- 引用（可嵌套一层，含 `> **标题**` 形式的引用标题）
- 围栏代码块 ```lang
- 表格（GFM，含 `:---:` 对齐）
- 图片 `![alt](src "title")`
- 分割线 `---` / `***` / `___`
- 行内：`**粗**`、`*斜*`、`~~删~~`、`` `码` ``、`[文字](链接)`、`<https://x>`、转义字符

块用以下 dataclass 表示，渲染层只依赖这些结构，方便测试与扩展。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


# ---------------------------------------------------------------- 行内


@dataclass
class Text:
    value: str


@dataclass
class Code:
    value: str


@dataclass
class Strong:
    children: List["Inline"]


@dataclass
class Emph:
    children: List["Inline"]


@dataclass
class Strike:
    children: List["Inline"]


@dataclass
class Link:
    text: str
    href: str
    title: str = ""


@dataclass
class Image:
    alt: str
    src: str
    title: str = ""


Inline = object


# ---------------------------------------------------------------- 块


@dataclass
class Heading:
    level: int
    text: str
    inlines: List[Inline]


@dataclass
class Paragraph:
    inlines: List[Inline]
    text: str


@dataclass
class ListItem:
    blocks: List["Block"]
    checked: Optional[bool] = None


@dataclass
class ListBlock:
    ordered: bool
    start: int
    items: List[ListItem]


@dataclass
class Quote:
    blocks: List["Block"]


@dataclass
class CodeBlock:
    lang: str
    code: str


@dataclass
class Table:
    header: List[List[Inline]]
    align: List[str]
    rows: List[List[List[Inline]]]


@dataclass
class ImageBlock:
    image: Image


@dataclass
class ThematicBreak:
    pass


Block = object


@dataclass
class Document:
    blocks: List[Block] = field(default_factory=list)

    def headings(self) -> List[Heading]:
        return [b for b in self.blocks if isinstance(b, Heading)]

    def plain_text(self) -> str:
        return "\n".join(block_plain_text(b) for b in self.blocks)


def block_plain_text(block: Block) -> str:
    if isinstance(block, Heading):
        return block.text
    if isinstance(block, Paragraph):
        return block.text
    if isinstance(block, CodeBlock):
        return block.code
    if isinstance(block, (ListBlock,)):
        return "\n".join(block_plain_text(sub) for item in block.items for sub in item.blocks)
    if isinstance(block, Quote):
        return "\n".join(block_plain_text(sub) for sub in block.blocks)
    if isinstance(block, Table):
        cells = [inline_plain_text(c) for c in block.header]
        for row in block.rows:
            cells.extend(inline_plain_text(c) for c in row)
        return " ".join(cells)
    if isinstance(block, ImageBlock):
        return block.image.alt
    return ""


def inline_plain_text(nodes: Sequence[Inline]) -> str:
    parts: List[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.value)
        elif isinstance(node, Code):
            parts.append(node.value)
        elif isinstance(node, (Strong, Emph, Strike)):
            parts.append(inline_plain_text(node.children))
        elif isinstance(node, Link):
            parts.append(node.text)
        elif isinstance(node, Image):
            parts.append(node.alt)
    return "".join(parts)


def iter_inlines(nodes: Sequence[Inline]):
    """深度遍历行内节点。"""
    for node in nodes:
        yield node
        if isinstance(node, (Strong, Emph, Strike)):
            yield from iter_inlines(node.children)


def iter_blocks(blocks: Sequence[Block]):
    """深度遍历块（含列表项、引用内部）。"""
    for block in blocks:
        yield block
        if isinstance(block, ListBlock):
            for item in block.items:
                yield from iter_blocks(item.blocks)
        elif isinstance(block, Quote):
            yield from iter_blocks(block.blocks)


# ---------------------------------------------------------------- 行内解析

_ESCAPABLE = set("\\`*_{}[]()#+-.!|<>~")
_ESCAPE_RE = None


def parse_inline(text: str) -> List[Inline]:
    return _parse_inline(text)


def _parse_inline(text: str) -> List[Inline]:
    nodes: List[Inline] = []
    buf: List[str] = []
    i = 0
    n = len(text)

    def flush() -> None:
        if buf:
            nodes.append(Text("".join(buf)))
            buf.clear()

    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] in _ESCAPABLE:
            buf.append(text[i + 1])
            i += 2
            continue
        if ch == "`":
            j = i
            while j < n and text[j] == "`":
                j += 1
            ticks = j - i
            closing = text.find("`" * ticks, j)
            if closing != -1:
                flush()
                nodes.append(Code(text[j:closing].strip()))
                i = closing + ticks
                continue
            buf.append(text[i:j])
            i = j
            continue
        if ch == "!" and i + 1 < n and text[i + 1] == "[":
            parsed = _try_parse_link(text, i + 1)
            if parsed:
                label, href, title, end = parsed
                flush()
                nodes.append(Image(alt=label, src=href, title=title))
                i = end
                continue
        if ch == "[":
            parsed = _try_parse_link(text, i)
            if parsed:
                label, href, title, end = parsed
                flush()
                nodes.append(Link(text=label, href=href, title=title))
                i = end
                continue
        if ch == "<":
            end = text.find(">", i)
            if end != -1:
                inner = text[i + 1:end]
                if inner.startswith("http://") or inner.startswith("https://") or inner.startswith("mailto:"):
                    flush()
                    nodes.append(Link(text=inner, href=inner))
                    i = end + 1
                    continue
        if text.startswith("**", i) or text.startswith("__", i):
            marker = text[i:i + 2]
            closing = text.find(marker, i + 2)
            if closing > i + 2:
                inner = text[i + 2:closing]
                if not inner.strip():
                    buf.append(marker)
                    i += 2
                    continue
                flush()
                nodes.append(Strong(_parse_inline(inner)))
                i = closing + 2
                continue
        if text.startswith("~~", i):
            closing = text.find("~~", i + 2)
            if closing > i + 2:
                flush()
                nodes.append(Strike(_parse_inline(text[i + 2:closing])))
                i = closing + 2
                continue
        if ch in "*_" and not text.startswith("**", i):
            closing = text.find(ch, i + 1)
            if closing > i + 1:
                inner = text[i + 1:closing]
                if inner.strip():
                    flush()
                    nodes.append(Emph(_parse_inline(inner)))
                    i = closing + 1
                    continue
        buf.append(ch)
        i += 1
    flush()
    return nodes


def _try_parse_link(text: str, start: int) -> Optional[Tuple[str, str, str, int]]:
    """text[start] == '['，尝试解析 `[label](href "title")`。"""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if i >= n or depth != 0:
        return None
    label = text[start + 1:i]
    if i + 1 >= n or text[i + 1] != "(":
        return None
    j = i + 2
    depth = 1
    while j < n:
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    if j >= n:
        return None
    inner = text[i + 2:j].strip()
    href, title = inner, ""
    parts = _split_link_target(inner)
    if parts:
        href, title = parts
    return label, href, title, j + 1


def _split_link_target(inner: str) -> Optional[Tuple[str, str]]:
    if not inner:
        return None
    if inner.startswith("<"):
        end = inner.find(">")
        if end != -1:
            href = inner[1:end]
            rest = inner[end + 1:].strip()
            return href, rest.strip('"').strip("'")
    if " " in inner:
        href, _, rest = inner.partition(" ")
        return href, rest.strip().strip('"').strip("'")
    return inner, ""


# ---------------------------------------------------------------- 块解析

_HEADING_RE = __import__("re").compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = __import__("re").compile(r"^(\s{0,3})(`{3,}|~{3,})\s*([^\s`]*)[^`]*$")
_HR_RE = __import__("re").compile(r"^\s{0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})$")
_LIST_RE = __import__("re").compile(r"^(\s*)([-+*]|\d{1,9}[.)])\s+(.*)$")
_TABLE_SEP_RE = __import__("re").compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_QUOTE_RE = __import__("re").compile(r"^\s{0,3}>\s?(.*)$")
_IMG_ONLY_RE = __import__("re").compile(r"^\s*!\[([^\]]*)\]\((\S+?)(?:\s+[\"']([^\"']*)[\"'])?\)\s*$")


class MarkdownError(ValueError):
    pass


def parse_markdown(text: str) -> Document:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, _ = _parse_blocks(lines, 0)
    return Document(blocks)


def _parse_blocks(lines: List[str], start: int, stop_on_blank_quote: bool = False):
    blocks: List[Block] = []
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            indent, marker, lang = fence.group(1), fence.group(2), fence.group(3)
            code_lines: List[str] = []
            i += 1
            while i < n:
                close = _FENCE_RE.match(lines[i])
                if close and close.group(2)[0] == marker[0] and len(close.group(2)) >= len(marker) and not close.group(3):
                    i += 1
                    break
                raw = lines[i]
                if indent and raw.startswith(indent):
                    raw = raw[len(indent):]
                code_lines.append(raw)
                i += 1
            else:
                raise MarkdownError("代码块没有闭合（从 `%s` 开始）" % marker)
            blocks.append(CodeBlock(lang=lang.lower(), code="\n".join(code_lines)))
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            text_ = heading.group(2).strip()
            blocks.append(Heading(level=level, text=text_, inlines=parse_inline(text_)))
            i += 1
            continue

        if _HR_RE.match(line):
            blocks.append(ThematicBreak())
            i += 1
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            inner: List[str] = []
            while i < n:
                q = _QUOTE_RE.match(lines[i])
                if not q:
                    break
                inner.append(q.group(1))
                i += 1
            sub = parse_markdown("\n".join(inner))
            blocks.append(Quote(sub.blocks))
            continue

        if _LIST_RE.match(line):
            block, i = _parse_list(lines, i)
            blocks.append(block)
            continue

        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            table, i = _parse_table(lines, i)
            blocks.append(table)
            continue

        img_only = _IMG_ONLY_RE.match(line)
        if img_only:
            blocks.append(ImageBlock(Image(alt=img_only.group(1).strip(),
                                            src=img_only.group(2),
                                            title=(img_only.group(3) or "").strip())))
            i += 1
            continue

        # 段落：连续非空行，遇到其他块起始则停止
        para: List[str] = []
        while i < n:
            cur = lines[i]
            if not cur.strip():
                break
            if para and (_HEADING_RE.match(cur) or _FENCE_RE.match(cur) or _QUOTE_RE.match(cur)
                         or _HR_RE.match(cur) or _LIST_RE.match(cur)):
                break
            para.append(cur.strip() if not para else cur.rstrip())
            i += 1
        text_ = "\n".join(para).strip()
        blocks.append(Paragraph(inlines=parse_inline(text_), text=text_))
    return blocks, i


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _parse_list(lines: List[str], start: int):
    first = _LIST_RE.match(lines[start])
    base_indent = len(first.group(1))
    ordered = first.group(2)[0].isdigit()
    start_num = int(first.group(2).rstrip(".)")) if ordered else 1
    items: List[ListItem] = []
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _LIST_RE.match(line)
        if not m or len(m.group(1)) != base_indent:
            if not line.strip():
                # 允许列表项之间隔一个空行
                nxt = i + 1
                while nxt < n and not lines[nxt].strip():
                    nxt += 1
                if nxt < n:
                    nm = _LIST_RE.match(lines[nxt])
                    if nm and len(nm.group(1)) == base_indent and nm.group(2)[0].isdigit() == ordered:
                        i = nxt
                        continue
                break
            break
        item_is_ordered = m.group(2)[0].isdigit()
        if item_is_ordered != ordered:
            break
        content = m.group(3)
        content_indent = len(m.group(1)) + len(m.group(2)) + 1
        item_lines = [content]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                # 空行后若仍是缩进内容，则属于本项
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and _indent_of(lines[j]) > base_indent:
                    item_lines.append("")
                    i = j
                    continue
                break
            if _indent_of(nxt) > base_indent:
                item_lines.append(nxt[content_indent:] if len(nxt) > content_indent else nxt.lstrip())
                i += 1
                continue
            nm = _LIST_RE.match(nxt)
            if nm and len(nm.group(1)) == base_indent and nm.group(2)[0].isdigit() == ordered:
                break
            break
        checked = None
        if item_lines and item_lines[0][:4] in ("[ ] ", "[x] ", "[X] "):
            checked = not item_lines[0].startswith("[ ]")
            item_lines[0] = item_lines[0][4:]
        sub_blocks, _ = _parse_blocks(item_lines, 0)
        items.append(ListItem(blocks=sub_blocks, checked=checked))
    return ListBlock(ordered=ordered, start=start_num, items=items), i


def _split_row(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: List[str] = []
    buf: List[str] = []
    escaped = False
    in_code = False
    for ch in line:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            continue
        if ch == "`":
            in_code = not in_code
            buf.append(ch)
            continue
        if ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def _parse_table(lines: List[str], start: int):
    header = _split_row(lines[start])
    sep = _split_row(lines[start + 1])
    align: List[str] = []
    for cell in sep:
        cell = cell.strip()
        left = cell.startswith(":")
        right = cell.endswith(":")
        if left and right:
            align.append("center")
        elif right:
            align.append("right")
        elif left:
            align.append("left")
        else:
            align.append("")
    while len(align) < len(header):
        align.append("")
    rows: List[List[List[Inline]]] = []
    i = start + 2
    n = len(lines)
    while i < n and lines[i].strip() and "|" in lines[i]:
        cells = _split_row(lines[i])
        cells = (cells + [""] * len(header))[:len(header)]
        rows.append([parse_inline(c) for c in cells])
        i += 1
    return Table(header=[parse_inline(c) for c in header], align=align, rows=rows), i


def count_words(text: str) -> int:
    """中文按字计，英文/数字按词计；忽略 Markdown 标记。"""
    import re
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[#>*_~`|\-]+", " ", cleaned)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", cleaned))
    latin = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", cleaned))
    return cjk + latin
