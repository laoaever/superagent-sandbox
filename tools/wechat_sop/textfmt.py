"""中文排版格式修复：半角标点、中英文空格、加粗标点位置。

规则来源（见 docs/wechat-sop/00-research.md §3.5）：先「保护」代码块、行内代码、
URL、链接地址等不应被修改的片段，再做替换，最后还原。
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

CJK_CHARS = "[\u4e00-\u9fff\u3400-\u4dbf]"
CJK = "\u4e00-\u9fff\u3400-\u4dbf"
CJK_CLASS = CJK_CHARS
# 全角标点用 codepoint 表示，避免源码里被输入法切成半角而肉眼难查
CJK_PUNCT_CODES = (0xFF0C, 0x3002, 0xFF01, 0xFF1F, 0xFF1B, 0xFF1A,
                   0x201C, 0x201D, 0x2018, 0x2019, 0xFF08, 0xFF09, 0x3010, 0x3011,
                   0x300A, 0x300B, 0x2026, 0x2014, 0x3001)
FW_COMMA = chr(0xFF0C)
FW_COLON = chr(0xFF1A)
FW_SEMI = chr(0xFF1B)
FW_QMARK = chr(0xFF1F)
FW_EXCL = chr(0xFF01)
FW_PERIOD = chr(0x3002)
FW_LPAREN = chr(0xFF08)
FW_RPAREN = chr(0xFF09)
CJK_PUNCT = "".join(chr(c) for c in CJK_PUNCT_CODES)

_PROTECT_PATTERNS = [
    re.compile(r"```.*?```", re.DOTALL),          # 围栏代码块
    re.compile(r"`[^`\n]+?`"),                      # 行内代码
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),            # 图片
    re.compile(r"\[[^\]]*\]\([^)]*\)"),             # 链接
    re.compile(r"<[^>\n]+>"),                       # 自动链接 / HTML
    re.compile(r"https?://\S+"),                    # 裸 URL
]


def protect(text: str) -> Tuple[str, List[str]]:
    bag: List[str] = []

    def stash(match: "re.Match[str]") -> str:
        bag.append(match.group(0))
        return "\x00P%d\x00" % (len(bag) - 1)

    for pattern in _PROTECT_PATTERNS:
        text = pattern.sub(stash, text)
    return text, bag


def restore(text: str, bag: List[str]) -> str:
    for index, fragment in enumerate(bag):
        text = text.replace("\x00P%d\x00" % index, fragment)
    return text


def _apply_outside_code_blocks(text: str, fn: Callable[[str], str]) -> str:
    """按围栏代码块切分，只对非代码部分应用 fn。"""
    lines = text.split("\n")
    out: List[str] = []
    buffer: List[str] = []
    in_fence = False

    def flush() -> None:
        if buffer:
            out.append(fn("\n".join(buffer)))
            buffer.clear()

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            out.append(line)
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
        else:
            buffer.append(line)
    flush()
    return "\n".join(out)


def fix_punctuation(text: str) -> str:
    """中文上下文的半角标点 → 全角。"""
    text = _apply_outside_code_blocks(text, _fix_punctuation_line)
    return text


def _fix_punctuation_line(text: str) -> str:
    text, bag = protect(text)
    text = re.sub("(%s)[ \\t]*," % CJK_CLASS, lambda m: m.group(1) + FW_COMMA, text)
    text = re.sub("(%s)[ \\t]*:" % CJK_CLASS, lambda m: m.group(1) + FW_COLON, text)
    text = re.sub("(%s)[ \\t]*;" % CJK_CLASS, lambda m: m.group(1) + FW_SEMI, text)
    text = re.sub("(%s)[ \\t]*\\?" % CJK_CLASS, lambda m: m.group(1) + FW_QMARK, text)
    text = re.sub("(%s)[ \\t]*!" % CJK_CLASS, lambda m: m.group(1) + FW_EXCL, text)
    text = re.sub(
        "(%s)[ \\t]*\\.(?=[\\s%s]|$)" % (CJK_CLASS, CJK),
        lambda m: m.group(1) + FW_PERIOD,
        text,
        flags=re.MULTILINE,
    )
    text = re.sub("(%s)[ \\t]*\\(" % CJK_CLASS, lambda m: m.group(1) + FW_LPAREN, text)
    right_lookahead = "%s%s\\s" % (CJK, re.escape(FW_COMMA + chr(0x3001) + FW_PERIOD + FW_SEMI + FW_COLON + FW_EXCL + FW_QMARK))
    text = re.sub(
        "\\)(?=[%s]|$)" % right_lookahead,
        lambda m: FW_RPAREN,
        text,
        flags=re.MULTILINE,
    )
    return restore(text, bag)


def find_half_width_punctuation(text: str) -> List[str]:
    """返回仍存在半角标点问题的片段（用于检查）。"""
    issues: List[str] = []

    def collect(line: str) -> str:
        masked, bag = protect(line)
        for pattern in _HALF_PUNCT_PATTERNS:
            for match in re.finditer(pattern, masked):
                start = max(0, match.start() - 6)
                end = min(len(masked), match.end() + 6)
                issues.append(restore(masked[start:end], bag).replace("\n", " "))
        return line

    _apply_outside_code_blocks(text, collect)
    return issues


_HALF_PUNCT_PATTERNS = [
    "%s[ \\t]*," % CJK_CLASS,
    "%s[ \\t]*;" % CJK_CLASS,
    "%s[ \\t]*\\?" % CJK_CLASS,
    "%s[ \\t]*!" % CJK_CLASS,
    "%s[ \\t]*\\(" % CJK_CLASS,
]


def fix_cjk_spacing(text: str) -> str:
    """中文与英文/数字之间补空格。"""
    return _apply_outside_code_blocks(text, _fix_spacing_line)


def _fix_spacing_line(line: str) -> str:
    masked, bag = protect(line)
    masked = re.sub("(%s)([A-Za-z0-9])" % CJK_CLASS, r"\1 \2", masked)
    masked = re.sub("([A-Za-z0-9])(%s)" % CJK_CLASS, r"\1 \2", masked)
    # 全角标点两侧不补空格
    masked = re.sub("(%s) +" % re.escape(CJK_PUNCT), r"\1", masked)
    masked = re.sub(" +(%s)" % re.escape(CJK_PUNCT), r"\1", masked)
    return restore(masked, bag)


def find_missing_spacing(text: str) -> List[str]:
    """返回中文与英文/数字粘连的位置（每行每类最多 2 处）。"""
    issues: List[str] = []

    def scan(line: str) -> str:
        masked, bag = protect(line)
        for pattern in ("%s[A-Za-z0-9]" % CJK_CLASS, "[A-Za-z0-9]%s" % CJK_CLASS):
            for match in list(re.finditer(pattern, masked))[:2]:
                start = max(0, match.start() - 5)
                end = min(len(masked), match.end() + 5)
                issues.append(restore(masked[start:end], bag))
        return line

    _apply_outside_code_blocks(text, scan)
    return issues


_BOLD_PUNCT_RE = re.compile(r"\*\*([^*\n]+?)([%s]+)\*\*" % re.escape(CJK_PUNCT))
_EM_PUNCT_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)([%s]+)\*(?!\*)" % re.escape(CJK_PUNCT))


def fix_bold_punctuation(text: str) -> str:
    """`**文字，**` → `**文字**，`；`*文字。*` → `*文字*。`"""
    text = _apply_outside_code_blocks(text, lambda block: _BOLD_PUNCT_RE.sub(r"**\1**\2", block))
    text = _apply_outside_code_blocks(text, lambda block: _EM_PUNCT_RE.sub(r"*\1*\2", block))
    return text


def format_text(text: str) -> str:
    """完整格式化：标点 → 加粗位置 → 空格。"""
    text = fix_punctuation(text)
    text = fix_bold_punctuation(text)
    text = fix_cjk_spacing(text)
    return text
