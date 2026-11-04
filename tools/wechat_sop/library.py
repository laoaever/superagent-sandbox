"""文章目录与素材/选题库的管理。

仓库约定（见 docs/wechat-sop/README.md 第 8 节）：

    topics/topics.md       选题库
    topics/materials.md    素材库
    articles/<日期>-<slug>/ 每篇文章一个目录
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
from typing import Dict, List, Optional

TOPICS_HEADER = """# 选题库

> 每条选题一段，`## T<编号> <标题>` 开头，下一行写元信息。
> 状态：`draft`（候选）→ `planned`（已立项）→ `writing`（写作中）→ `published`（已发布）→ `dropped`（放弃）

"""

MATERIALS_HEADER = """# 素材库

> 每条素材一段，`## M<编号> <一句话描述>` 开头。
> 标签建议：读者问题 / 经验 / 调研 / 回炉 / 数据 / 案例

"""

_ENTRY_RE = re.compile(r"^## ([TM])(\d{8}|[\dA-Za-z]+)\s+(.*)$")


class LibraryError(ValueError):
    pass


def ensure_library(root_dir: str) -> None:
    topics_dir = os.path.join(root_dir, "topics")
    os.makedirs(topics_dir, exist_ok=True)
    for filename, header in (("topics.md", TOPICS_HEADER), ("materials.md", MATERIALS_HEADER)):
        path = os.path.join(topics_dir, filename)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(header)


def _today() -> str:
    return datetime.date.today().strftime("%Y%m%d")


def _new_id(prefix: str, path: str) -> str:
    existing = {m.group(1) + m.group(2) for m in (_ENTRY_RE.match(line) for line in _read_lines(path)) if m}
    base = prefix + _today()
    index = 1
    while "%s%02d" % (base, index) in existing:
        index += 1
    return "%s%02d" % (base, index)


def _read_lines(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


def _write_lines(path: str, lines: List[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")


def parse_entries(path: str) -> List[Dict[str, str]]:
    """解析 `## ID 标题` 形式的条目。"""
    entries: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    for line in _read_lines(path):
        match = re.match(r"^## ([A-Z]\d{2,}[A-Za-z0-9]*)\s+(.*)$", line)
        if match:
            if current:
                entries.append(current)
            current = {"id": match.group(1), "title": match.group(2).strip(), "lines": ""}
            continue
        if current is not None and line.startswith("## "):
            entries.append(current)
            current = None
            continue
        if current is not None:
            current["lines"] += line + "\n"
    if current:
        entries.append(current)
    for entry in entries:
        meta: Dict[str, str] = {}
        for line in entry["lines"].splitlines():
            m = re.match(r"^\s*[-*]\s*([^：:]+)[：:]\s*(.*)$", line)
            if m:
                meta[m.group(1).strip()] = m.group(2).strip()
        entry["meta"] = meta
    return entries


def add_topic(root_dir: str, title: str, *, angle: str = "", audience: str = "",
              materials: Optional[List[str]] = None, reason: str = "",
              difference: str = "", words: str = "") -> str:
    ensure_library(root_dir)
    path = os.path.join(root_dir, "topics", "topics.md")
    topic_id = _new_id("T", path)
    block = [
        "",
        "## %s %s" % (topic_id, title.strip()),
        "- 状态：draft",
        "- 人群：%s" % audience,
        "- 一句话结论：%s" % angle,
        "- 独特证据：%s" % (", ".join(materials or []) or "（待补）"),
        "- 为什么现在：%s" % reason,
        "- 差异化：%s" % difference,
        "- 预估字数：%s" % words,
        "- 关联素材：%s" % (", ".join(materials or [])),
        "- 文章目录：",
        "",
    ]
    lines = _read_lines(path)
    while lines and not lines[-1].strip():
        lines.pop()
    lines.extend(block)
    _write_lines(path, lines)
    return topic_id


def add_material(root_dir: str, title: str, *, tags: str = "", source: str = "",
                 points: str = "", quota: str = "") -> str:
    ensure_library(root_dir)
    path = os.path.join(root_dir, "topics", "materials.md")
    material_id = _new_id("M", path)
    block = [
        "",
        "## %s %s" % (material_id, title.strip()),
        "- 标签：%s" % tags,
        "- 来源：%s" % source,
        "- 要点：%s" % points,
        "- 可引用：%s" % quota,
        "",
    ]
    lines = _read_lines(path)
    while lines and not lines[-1].strip():
        lines.pop()
    lines.extend(block)
    _write_lines(path, lines)
    return material_id


def get_entry(root_dir: str, entry_id: str) -> Optional[Dict[str, str]]:
    for filename in ("topics.md", "materials.md"):
        path = os.path.join(root_dir, "topics", filename)
        if not os.path.exists(path):
            continue
        for entry in parse_entries(path):
            if entry["id"].upper() == entry_id.upper():
                return entry
    return None


def set_entry_meta(root_dir: str, entry_id: str, key: str, value: str) -> bool:
    path = os.path.join(root_dir, "topics", "topics.md")
    lines = _read_lines(path)
    in_entry = False
    changed = False
    for index, line in enumerate(lines):
        match = re.match(r"^## (\S+)\s+", line)
        if match:
            in_entry = match.group(1).upper() == entry_id.upper()
            continue
        if in_entry and re.match(r"^\s*[-*]\s*%s\s*[：:]" % re.escape(key), line):
            lines[index] = "- %s：%s" % (key, value)
            changed = True
            break
    if changed:
        _write_lines(path, lines)
    return changed


def slugify(text: str, fallback: str = "article") -> str:
    text = text.strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\-]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or fallback


def create_article_dir(root_dir: str, slug: str, date: Optional[str] = None) -> str:
    date = date or datetime.date.today().strftime("%Y-%m-%d")
    slug = slugify(slug)
    path = os.path.join(root_dir, "articles", "%s-%s" % (date, slug))
    os.makedirs(os.path.join(path, "images"), exist_ok=True)
    return path


def mark_topic(root_dir: str, topic_id: str, status: str, article_dir: str = "") -> None:
    set_entry_meta(root_dir, topic_id, "状态", status)
    if article_dir:
        rel = os.path.relpath(article_dir, root_dir).replace(os.sep, "/")
        set_entry_meta(root_dir, topic_id, "文章目录", rel + "/")


def copy_tree(src: str, dst: str) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)
