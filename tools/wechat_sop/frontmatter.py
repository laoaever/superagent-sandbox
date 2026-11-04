"""Markdown YAML frontmatter 的读取与写回（不依赖 PyYAML）。

只支持公众号写作流程实际会用到的 YAML 子集：

    ---
    title: 标题
    summary: "一句话摘要"
    theme: default
    materials: [M001, M002]
    cover: cover.png
    publish_confirm: false
    ---

支持：`key: value`、`key: "quoted"`、`key:` + 缩进列表、`key: [a, b]`。
值类型：字符串 / 布尔 / 整数 / 浮点 / 字符串列表 / null。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


class FrontmatterError(ValueError):
    """frontmatter 格式错误。"""


def _strip_comment(value: str) -> str:
    """去掉行尾注释（引号内的 # 不算）。"""
    out = []
    quote = None
    for ch in value:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(raw: str) -> Any:
    raw = _strip_comment(raw).strip()
    if raw == "":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        body = raw[1:-1]
        if raw[0] == '"':
            body = body.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return body
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_flow(inner)]
    lowered = raw.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def _split_flow(inner: str) -> List[str]:
    parts, buf, quote = [], [], None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """返回 (frontmatter 字典, 正文)。没有 frontmatter 时返回 ({}, 原文)。"""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end():]
    return parse_yaml_block(raw), body


def parse_yaml_block(raw: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_key = None
    for line_no, line in enumerate(raw.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            # 缩进：作为上一个 key 的列表项
            if current_key is None:
                raise FrontmatterError("第 %d 行：缩进内容没有对应的 key" % line_no)
            item = line.strip()
            if item.startswith("- "):
                item = item[2:]
            elif item == "-":
                item = ""
            value = _parse_scalar(item)
            existing = data.get(current_key)
            if existing is None:
                data[current_key] = [value]
            elif isinstance(existing, list):
                existing.append(value)
            else:
                raise FrontmatterError("第 %d 行：%s 已经是标量，不能追加列表项" % (line_no, current_key))
            continue
        if ":" not in line:
            raise FrontmatterError("第 %d 行：缺少冒号：%r" % (line_no, line))
        key, _, rest = line.partition(":")
        key = key.strip()
        if not key:
            raise FrontmatterError("第 %d 行：key 为空" % line_no)
        data[key] = _parse_scalar(rest)
        current_key = key
    return data


def dump_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or re.search(r"^[\s\-?:,\[\]{}#&*!|>'\"%@`]|\s$", text) or ": " in text or " #" in text:
        return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')
    return text


REQUIRED_FIELDS = ("title", "summary", "theme", "author", "cover", "publish_confirm")

DEFAULTS: Dict[str, Any] = {
    "title": "",
    "summary": "",
    "theme": "default",
    "template": "",
    "author": "",
    "materials": [],
    "cover": "cover.png",
    "publish_confirm": False,
}


def read_article(path: str) -> Tuple[Dict[str, Any], str]:
    """读取文章文件，返回 (完整字段（含默认值）, 正文)。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta, body = split_frontmatter(text)
    merged = dict(DEFAULTS)
    merged.update(meta)
    return merged, body


def render_document(meta: Dict[str, Any], body: str) -> str:
    """把字段与正文拼回完整 Markdown 文档。"""
    lines = ["---"]
    ordered = ["title", "summary", "theme", "template", "author", "materials", "cover", "publish_confirm"]
    keys = ordered + [k for k in meta if k not in ordered]
    for key in keys:
        if key not in meta or meta[key] in (None, [], ""):
            if key in ("materials",) and key in meta:
                lines.append("%s: []" % key)
            continue
        value = meta[key]
        if isinstance(value, list):
            lines.append("%s: [%s]" % (key, ", ".join(dump_scalar(v) for v in value)))
        else:
            lines.append("%s: %s" % (key, dump_scalar(value)))
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.lstrip("\n")
