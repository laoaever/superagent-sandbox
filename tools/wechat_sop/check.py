"""发布前检查。

两个阶段：
- draft：写稿阶段，只看内容（标题/摘要/字数/占位符/标点/间距/敏感词）
- publish：发布前，额外检查主题、封面、图片、排版产物与发布确认

检查项分「阻断项」（必须清零才允许发布）与「风险项」（人工确认）。

实现说明：链接使用「链接地址」判定外链（`[文字](https://…)`）；图片宽度用标准库
`struct` 读取 PNG/GIF/JPEG 文件头，无法识别时只提示不阻断。
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import frontmatter as fm
from . import markdown as md
from . import textfmt
from .theme import ThemeError, list_themes, load_theme

TITLE_HARD_MAX = 64
TITLE_SOFT_MAX = 30
SUMMARY_MAX = 120
WORD_MIN = 300
WORD_MAX = 6000
PARAGRAPH_MAX = 400
IMAGE_MIN_WIDTH = 300

PLACEHOLDER_RE = re.compile(r"(\bTODO\b|\bFIXME\b|\bXXX\b|【待补[^】]*】|待补充|待完善|\{\{[^}]{1,40}\}\}|\[待[^\]]{0,10}\])")
EXTREME_WORDS = ["最好", "最佳", "最强", "最高级", "最大", "第一品牌", "全网第一", "唯一", "顶级",
                 "国家级", "绝对", "百分百", "永久有效", "100%"]

DEFAULT_BANNED_WORDS = [
    "加微信领取", "点击领取", "包治", "百分百有效",
    # 广告法明确禁止的绝对化用语（风险项见 EXTREME_WORDS，这里是更硬的越界表述）
    "最强", "最先进", "最权威", "销量第一", "行业第一", "绝对第一",
]


@dataclass
class Issue:
    code: str
    level: str  # "block" | "warn"
    message: str
    hint: str = ""

    def as_line(self) -> str:
        marker = "❌" if self.level == "block" else "⚠️"
        text = "%s [%s] %s" % (marker, self.code, self.message)
        if self.hint:
            text += "\n     → " + self.hint
        return text


@dataclass
class CheckResult:
    article: str
    stage: str
    issues: List[Issue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def blocks(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "block"]

    @property
    def warns(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "warn"]

    @property
    def ok(self) -> bool:
        return not self.blocks

    def exit_code(self) -> int:
        return 0 if self.ok else 1


def _add(result: CheckResult, level: str, code: str, message: str, hint: str = "") -> None:
    result.issues.append(Issue(code=code, level=level, message=message, hint=hint))


def _resolve(base_dir: str, path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def image_size(path: str) -> Optional[Tuple[int, int]]:
    """读取 PNG / GIF / JPEG 宽高；不支持的格式返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if head[:6] in (b"GIF87a", b"GIF89a"):
                width, height = struct.unpack("<HH", head[6:10])
                return int(width), int(height)
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if len(marker) < 2 or marker[0:1] != b"\xff":
                        return None
                    code = marker[1]
                    if code in (0xD8, 0xD9):
                        continue
                    length_bytes = f.read(2)
                    if len(length_bytes) < 2:
                        return None
                    length = struct.unpack(">H", length_bytes)[0]
                    if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        data = f.read(5)
                        height, width = struct.unpack(">HH", data[1:5])
                        return int(width), int(height)
                    f.seek(length - 2, os.SEEK_CUR)
    except (OSError, struct.error):
        return None
    return None


def image_references(doc: md.Document) -> List[Tuple[str, str]]:
    """返回 [(src, alt)]。"""
    refs: List[Tuple[str, str]] = []
    for block in md.iter_blocks(doc.blocks):
        if isinstance(block, md.ImageBlock):
            refs.append((block.image.src, block.image.alt))
    for block in md.iter_blocks(doc.blocks):
        nodes: List[Any] = []
        if isinstance(block, (md.Paragraph, md.Heading)):
            nodes = block.inlines
        elif isinstance(block, md.Table):
            for cell in block.header:
                nodes.extend(cell)
            for row in block.rows:
                for cell in row:
                    nodes.extend(cell)
        for node in md.iter_inlines(nodes):
            if isinstance(node, md.Image):
                refs.append((node.src, node.alt))
    return refs


def _load_banned_words(root_dir: str) -> List[str]:
    path = os.path.join(root_dir, "config", "checkwords.txt")
    words = list(DEFAULT_BANNED_WORDS)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                words.append(line)
    return words


def check_article(article_path: str, *, stage: str = "publish",
                  root_dir: Optional[str] = None, cover: Optional[str] = None,
                  theme_name: Optional[str] = None) -> CheckResult:
    article_path = os.path.abspath(article_path)
    base_dir = os.path.dirname(article_path)
    root_dir = root_dir or base_dir
    result = CheckResult(article=article_path, stage=stage)

    if not os.path.exists(article_path):
        _add(result, "block", "file-missing", "文章文件不存在：%s" % article_path)
        return result

    try:
        meta, body = fm.read_article(article_path)
    except fm.FrontmatterError as exc:
        _add(result, "block", "frontmatter", "frontmatter 解析失败：%s" % exc,
             "检查 --- 之间的 key: value 格式")
        return result

    # ---- 标题与摘要
    title = str(meta.get("title") or "").strip()
    summary = str(meta.get("summary") or "").strip()
    if not title:
        _add(result, "block", "title-missing", "标题缺失", "填写 frontmatter 的 title")
    elif len(title) > TITLE_HARD_MAX:
        _add(result, "block", "title-too-long", "标题 %d 字，超过公众号上限 %d 字"
             % (len(title), TITLE_HARD_MAX), "精简标题")
    elif len(title) > TITLE_SOFT_MAX:
        _add(result, "warn", "title-long", "标题 %d 字，超过建议值 %d 字，信息流可能截断"
             % (len(title), TITLE_SOFT_MAX), "考虑精简到 30 字以内")

    if not summary:
        _add(result, "block", "summary-missing", "摘要缺失", "填写 frontmatter 的 summary（≤120 字）")
    elif len(summary) > SUMMARY_MAX:
        _add(result, "block", "summary-too-long", "摘要 %d 字，超过 %d 字"
             % (len(summary), SUMMARY_MAX), "精简摘要")

    author = str(meta.get("author") or "").strip()
    if not author:
        _add(result, "warn", "author-missing", "作者字段为空", "填写 frontmatter 的 author")

    # ---- 正文
    doc = md.parse_markdown(body)
    word_count = md.count_words(body)
    result.stats["words"] = word_count
    result.stats["paragraphs"] = sum(1 for b in md.iter_blocks(doc.blocks) if isinstance(b, md.Paragraph))
    result.stats["images"] = len(image_references(doc))
    result.stats["headings"] = sum(1 for b in md.iter_blocks(doc.blocks) if isinstance(b, md.Heading))

    if word_count < WORD_MIN:
        _add(result, "block", "too-short", "正文仅 %d 字（下限 %d 字）" % (word_count, WORD_MIN),
             "补充内容，或确认是否误传了草稿")
    elif word_count > WORD_MAX:
        _add(result, "block", "too-long", "正文 %d 字（上限 %d 字）" % (word_count, WORD_MAX),
             "考虑拆成系列文章")

    for block in md.iter_blocks(doc.blocks):
        if isinstance(block, md.Paragraph) and len(block.text) > PARAGRAPH_MAX:
            snippet = block.text[:18].replace("\n", " ")
            _add(result, "warn", "paragraph-long",
                 "单段 %d 字（建议 ≤%d 字）：%s…" % (len(block.text), PARAGRAPH_MAX, snippet),
                 "拆成多段，手机阅读更友好")

    placeholders = PLACEHOLDER_RE.findall(body)
    if placeholders:
        unique = sorted({p if isinstance(p, str) else p[0] for p in placeholders})
        _add(result, "block", "placeholder", "仍有未完成标记：%s" % "、".join(unique[:8]),
             "补全内容并删除标记")

    # ---- 标点 / 间距
    half = textfmt.find_half_width_punctuation(body)
    if half:
        _add(result, "warn", "half-width-punct", "中文上下文使用了半角标点（%d 处），例：%s"
             % (len(half), "；".join(half[:3])), "运行 `python3 -m wechat_sop format <文章> --write`")
    spacing = textfmt.find_missing_spacing(body)
    if spacing:
        _add(result, "warn", "cjk-spacing", "中文与英文/数字之间缺少空格（%d 处），例：%s"
             % (len(spacing), "；".join(spacing[:3])), "运行 `format --write` 自动修复")

    # ---- 敏感词
    banned = _load_banned_words(root_dir)
    article_text = "\n".join([body, str(meta.get("title") or ""), str(meta.get("summary") or "")])
    hits = [w for w in banned if w and w in article_text]
    if hits:
        _add(result, "block", "banned-word", "命中敏感/违禁词：%s" % "、".join(hits[:8]),
             "改写表述；若确认为误报，可从 config/checkwords.txt 移除")
    extreme = [w for w in EXTREME_WORDS if w in body]
    if extreme:
        _add(result, "warn", "extreme-word", "出现绝对化用语：%s" % "、".join(extreme[:6]),
             "广告法对「最/第一/唯一」等词有约束，确认属实或改写")

    # ---- 结尾行动
    if doc.blocks:
        last_texts = [md.block_plain_text(b) for b in doc.blocks[-2:]]
        if not any(re.search(r"(试试|可以|建议|记得|点击|收藏|关注|评论|留言|转发)", t) for t in last_texts):
            _add(result, "warn", "no-cta", "结尾似乎没有具体行动建议", "给读者一个明确动作（试一下/收藏/讨论）")

    if stage == "draft":
        result.stats["stage"] = "draft"
        return result

    # ---- 主题
    theme_value = theme_name or str(meta.get("theme") or "default")
    try:
        load_theme(theme_value)
    except ThemeError as exc:
        _add(result, "block", "theme-missing", "主题不可用：%s" % exc,
             "可用主题：%s" % ", ".join(list_themes()))
    result.stats["theme"] = theme_value

    # ---- 封面
    cover_value = cover or str(meta.get("cover") or "")
    if not cover_value:
        _add(result, "block", "cover-missing", "未指定封面（frontmatter cover 为空）",
             "制作封面并写入 cover 字段")
    else:
        cover_path = _resolve(base_dir, cover_value)
        if not os.path.exists(cover_path):
            _add(result, "block", "cover-missing", "封面文件不存在：%s" % cover_value,
                 "把封面放到文章目录，或修正 cover 字段")
        else:
            size = image_size(cover_path)
            size_kb = os.path.getsize(cover_path) // 1024
            if size is None and not cover_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                _add(result, "warn", "cover-format", "封面格式无法识别：%s" % cover_value,
                     "使用 JPG / PNG / GIF")
            elif size is not None:
                result.stats["cover_size"] = "%dx%d" % size
                if size[0] < 900:
                    _add(result, "warn", "cover-small", "封面宽度 %dpx，低于建议 900px" % size[0],
                         "公众号首图建议 ≥900×383")
                if size[0] / max(size[1], 1) < 1.5:
                    _add(result, "warn", "cover-ratio", "封面宽高比 %.2f，建议 2.35:1 或 16:9"
                         % (size[0] / max(size[1], 1)), "重新裁切封面")
            if size_kb > 2048:
                _add(result, "warn", "cover-large", "封面 %dKB，建议 <2048KB" % size_kb, "压缩封面")

    # ---- 正文图片
    refs = image_references(doc)
    if not refs:
        _add(result, "warn", "no-image", "正文没有任何配图", "建议 2–5 张承担信息的图（见 05-配图.md）")
    for src, alt in refs:
        if re.match(r"^https?://", src):
            _add(result, "warn", "image-external", "使用外链图片：%s" % src[:60],
                 "公众号不接受外链图片，改为本地相对路径")
            continue
        path = _resolve(base_dir, src)
        if not os.path.exists(path):
            _add(result, "block", "image-missing", "正文引用的图片不存在：%s" % src, "放入 images/ 或修正路径")
            continue
        if not alt.strip():
            _add(result, "warn", "image-no-alt", "图片缺少说明：%s" % src, "补充 alt 说明这张图在说什么")
        size = image_size(path)
        if size is not None and size[0] < IMAGE_MIN_WIDTH:
            _add(result, "block", "image-small", "图片宽度 %dpx 小于 %dpx：%s"
                 % (size[0], IMAGE_MIN_WIDTH, src), "换一张更清晰的图")

    # ---- 排版产物
    outline_html = os.path.join(base_dir, "outline.html")
    if not os.path.exists(outline_html):
        _add(result, "block", "render-missing", "尚未生成排版产物 outline.html",
             "运行 `python3 -m wechat_sop render <文章>`")
    else:
        with open(outline_html, encoding="utf-8") as f:
            rendered = f.read()
        for code, pattern, message, hint in RENDER_FORBIDDEN:
            if re.search(pattern, rendered, re.I):
                _add(result, "block", code, "排版产物含公众号不支持的内容：%s" % message, hint)
        source_mtime = os.path.getmtime(article_path)
        if os.path.getmtime(outline_html) < source_mtime:
            _add(result, "warn", "render-stale", "排版产物比文章旧，可能未重新生成",
                 "重新运行 `render`")

    # ---- 发布确认
    confirmed = meta.get("publish_confirm")
    if confirmed is not True:
        _add(result, "block", "publish-confirm", "publish_confirm 尚未设为 true（发布确认未完成）",
             "人工复核 07-发布清单.md 后，把 frontmatter 的 publish_confirm 改为 true")

    return result


RENDER_FORBIDDEN = [
    ("html-style", r"<style[\s>]", "<style> 标签", "样式必须内联"),
    ("html-script", r"<script[\s>]", "<script> 标签", "公众号会过滤脚本"),
    ("html-div", r"<div[\s>]", "<div> 标签", "使用 <section>"),
    ("html-class", r"\sclass\s*=", "class 属性", "class 会被剥离，请用内联 style"),
    ("html-id", r"\sid\s*=", "id 属性", "id 会被剥离"),
    ("css-var", r"var\s*\(\s*--", "CSS 变量", "变量不支持，请写死值"),
    ("css-gradient", r"(?:linear|radial|conic)-gradient", "渐变背景", "深色模式会报错，请用纯色"),
    ("css-media", r"@media|@keyframes|@import", "媒体查询/动画", "公众号不支持"),
    ("css-position", r"position\s*:\s*(?:fixed|absolute|sticky)", "绝对定位", "公众号不支持"),
    ("css-link-ext", r"<link[\s>]", "外部 <link>", "会被过滤"),
]


def format_report(result: CheckResult) -> str:
    lines: List[str] = []
    lines.append("# 发布前检查报告")
    lines.append("")
    lines.append("- 文章：%s" % result.article)
    lines.append("- 阶段：%s" % result.stage)
    stats = result.stats
    if stats:
        detail = "，".join("%s %s" % (k, v) for k, v in stats.items())
        lines.append("- 统计：%s" % detail)
    if result.ok:
        lines.append("- 结论：✅ 无阻断项（%d 项风险项待人工确认）" % len(result.warns))
    else:
        lines.append("- 结论：❌ 存在 %d 项阻断问题、%d 项风险提示" % (len(result.blocks), len(result.warns)))
    lines.append("")
    if result.blocks:
        lines.append("## 阻断项（%d）" % len(result.blocks))
        lines.append("")
        for issue in result.blocks:
            lines.append("- [%s] %s" % (issue.code, issue.message))
            if issue.hint:
                lines.append("  - 修复：%s" % issue.hint)
        lines.append("")
    if result.warns:
        lines.append("## 风险项（%d）" % len(result.warns))
        lines.append("")
        for issue in result.warns:
            lines.append("- [%s] %s" % (issue.code, issue.message))
            if issue.hint:
                lines.append("  - 建议：%s" % issue.hint)
        lines.append("")
    lines.append("## 人工复核")
    lines.append("")
    lines.append("脚本查不了事实与观感，请按 `docs/wechat-sop/06-发布检查.md` 第 4 节逐条确认。")
    lines.append("")
    return "\n".join(lines)


def write_report(result: CheckResult, path: Optional[str] = None) -> str:
    if path is None:
        path = os.path.join(os.path.dirname(result.article), "check-report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_report(result))
    return path
