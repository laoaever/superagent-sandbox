"""主题：加载、内联样式生成、排版规范校验。

主题是一个 JSON 文件（`themes/*.json`），结构：

    {
      "name": "default",
      "display_name": "默认",
      "primary_color": "#07c160",
      "font_family": "-apple-system, ...",
      "font_size": "16px",
      "line_height": "1.75",
      "color": "#3f3f3f",
      "styles": {
        "p": {"margin": "0 0 1.5em", "letter_spacing": "0.5px"},
        "h2": {"font_size": "20px", ...}
      },
      "x": {            # 扩展：脚本内部使用的颜色与数值
        "text_secondary": "#888888",
        "border_color": "#e5e5e5",
        "code_bg": "#f7f7f7",
        "code_block_bg": "#282c34",
        "code_block_text": "#abb2bf",
        "quote_bg": "rgba(7,193,96,0.06)",
        "table_head_bg": "rgba(7,193,96,0.08)",
        "table_stripe_bg": "#fafafa",
        "footnote_color": "#888888",
        "heading_number_color": "#07c160",
        "link_color": "#576b95"
      }
    }

所有样式都是**字面量**（禁止 CSS 变量、禁止渐变），因为公众号粘贴会丢弃变量。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

THEMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")

_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGBA_RE = re.compile(r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*(0|1|0?\.\d+)\s*)?\)$")
_PX_RE = re.compile(r"^(-?\d+(?:\.\d+)?)px$")
_EM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(em|rem|%)?$")

DEFAULT_X: Dict[str, str] = {
    "font_family": "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "text_secondary": "#888888",
    "border_color": "#e5e5e5",
    "code_bg": "rgba(0,0,0,0.05)",
    "code_text": "#c7254e",
    "code_block_bg": "#282c34",
    "code_block_text": "#abb2bf",
    "code_block_comment": "#5c6370",
    "code_block_keyword": "#c678dd",
    "code_block_string": "#98c379",
    "code_block_number": "#d19a66",
    "quote_bg": "rgba(0,0,0,0.03)",
    "table_head_bg": "rgba(0,0,0,0.05)",
    "table_stripe_bg": "#fafafa",
    "footnote_color": "#888888",
    "heading_number_color": "#999999",
    "link_color": "#576b95",
}


class ThemeError(ValueError):
    pass


def list_themes() -> List[str]:
    names = []
    for filename in sorted(os.listdir(THEMES_DIR)):
        if filename.endswith(".json"):
            names.append(filename[:-5])
    return names


def load_theme(name_or_path: str) -> Dict[str, Any]:
    if name_or_path is None or not str(name_or_path).strip():
        name_or_path = "default"
    if os.path.sep in name_or_path or name_or_path.endswith(".json"):
        path = name_or_path
    else:
        path = os.path.join(THEMES_DIR, name_or_path + ".json")
    if not os.path.exists(path):
        raise ThemeError(
            "主题不存在：%s（可用主题：%s）" % (name_or_path, ", ".join(list_themes()))
        )
    with open(path, encoding="utf-8") as f:
        try:
            theme = json.load(f)
        except json.JSONDecodeError as exc:
            raise ThemeError("主题文件不是合法 JSON：%s：%s" % (path, exc))
    theme.setdefault("styles", {})
    theme.setdefault("font_size", "16px")
    theme.setdefault("line_height", "1.75")
    theme.setdefault("color", "#3f3f3f")
    theme.setdefault("primary_color", "#07c160")
    theme.setdefault("font_family", DEFAULT_X["font_family"])
    x = dict(DEFAULT_X)
    x.update(theme.get("x", {}) or {})
    theme["x"] = x
    theme["path"] = path
    return theme


def style_string(props: Dict[str, Any]) -> str:
    """把 {font_size, line_height, ...} 转成 `font-size:16px;line-height:1.75` 形式。"""
    parts: List[str] = []
    for key, value in props.items():
        if value is None or value == "":
            continue
        css_key = key.replace("_", "-")
        parts.append("%s:%s" % (css_key, value))
    return ";".join(parts)


def merge_styles(base: Dict[str, Any], scheme: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> str:
    merged = dict(base)
    merged.update(scheme or {})
    merged.update(extra or {})
    return style_string(merged)


def heading_number_style(theme: Dict[str, Any], scheme: Dict[str, Any]) -> str:
    props = {
        "font-size": "0.72em",
        "color": theme["x"]["heading_number_color"],
        "font-weight": "400",
        "margin-right": scheme.get("number_margin", "0.5em"),
        "letter-spacing": "0.05em",
    }
    return style_string(props)


# ---------------------------------------------------------------- lint

MIN_FONT_PX = 14
RECOMMENDED_FONT_PX = (15, 17)
MAX_FONT_PX = 18
MIN_LINE_HEIGHT = 1.6
MAX_H1_PX = 28
MAX_H2_PX = 22


def _px(value: Any) -> Optional[float]:
    if value is None:
        return None
    m = _PX_RE.match(str(value).strip())
    return float(m.group(1)) if m else None


def _gradient_props(theme: Dict[str, Any]) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for tag, props in theme.get("styles", {}).items():
        for key, value in props.items():
            if isinstance(value, str) and re.search(r"(linear|radial|conic)-gradient", value, re.I):
                found.append((tag, key))
    return found


def lint_theme(theme: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """返回 (blocking_errors, warnings)。"""
    errors: List[str] = []
    warnings: List[str] = []

    def name() -> str:
        return theme.get("name") or theme.get("path", "?")

    font_px = _px(theme.get("font_size"))
    if font_px is None:
        errors.append("[%s] font_size 必须是 px 值，当前：%r" % (name(), theme.get("font_size")))
    elif not (RECOMMENDED_FONT_PX[0] <= font_px <= RECOMMENDED_FONT_PX[1]):
        if MIN_FONT_PX <= font_px <= MAX_FONT_PX:
            warnings.append("[%s] 正文字号 %gpx 不在推荐区间 15–17px" % (name(), font_px))
        else:
            errors.append("[%s] 正文字号 %gpx 越界（允许 14–18px）" % (name(), font_px))

    try:
        line_height = float(theme.get("line_height"))
    except (TypeError, ValueError):
        errors.append("[%s] line_height 必须是数字，当前：%r" % (name(), theme.get("line_height")))
        line_height = None
    if line_height is not None and line_height < MIN_LINE_HEIGHT:
        errors.append("[%s] 行高 %g 过紧（应 ≥%.1f）" % (name(), line_height, MIN_LINE_HEIGHT))

    styles = theme.get("styles", {})
    sizes = {tag: _px(styles.get(tag, {}).get("font_size")) for tag in ("h1", "h2", "h3")}
    if sizes["h1"] is not None and sizes["h1"] > MAX_H1_PX:
        errors.append("[%s] H1 字号 %gpx 过大（应 ≤%dpx）" % (name(), sizes["h1"], MAX_H1_PX))
    if sizes["h2"] is not None and sizes["h2"] > MAX_H2_PX:
        errors.append("[%s] H2 字号 %gpx 过大（应 ≤%dpx）" % (name(), sizes["h2"], MAX_H2_PX))
    if font_px is not None:
        for tag in ("h1", "h2", "h3"):
            if sizes[tag] is not None and sizes[tag] < font_px:
                errors.append("[%s] %s 字号 %gpx 小于正文 %gpx（字号梯度倒置）"
                              % (name(), tag.upper(), sizes[tag], font_px))
    sequence = [(tag, sizes[tag]) for tag in ("h1", "h2", "h3") if sizes[tag] is not None]
    for (tag_a, size_a), (tag_b, size_b) in zip(sequence, sequence[1:]):
        if size_b > size_a:
            errors.append("[%s] 字号梯度倒置：%s(%gpx) < %s(%gpx)"
                          % (name(), tag_a.upper(), size_a, tag_b.upper(), size_b))

    for tag, key in _gradient_props(theme):
        errors.append("[%s] styles.%s.%s 使用了渐变背景（公众号深色模式会报错，请改用纯色）"
                      % (name(), tag, key))

    for key in ("primary_color", "color"):
        value = theme.get(key)
        if value and not (_COLOR_RE.match(str(value)) or _RGBA_RE.match(str(value))):
            errors.append("[%s] %s 不是合法颜色：%r" % (name(), key, value))

    font_family = str(theme.get("font_family", ""))
    if any(ord(ch) > 127 for ch in font_family.split(",")[0]) and "'" not in font_family and '"' not in font_family:
        warnings.append("[%s] font_family 首项含中文字体名，建议加引号" % name())

    return errors, warnings


def lint_all() -> Dict[str, Tuple[List[str], List[str]]]:
    result: Dict[str, Tuple[List[str], List[str]]] = {}
    for name in list_themes():
        theme = load_theme(name)
        result[name] = lint_theme(theme)
    return result
