"""frontmatter 与 Markdown 解析测试。"""

import pytest

from wechat_sop import frontmatter as fm
from wechat_sop import markdown as md


def test_frontmatter_roundtrip():
    text = """---
title: "带: 冒号的标题"
summary: 一句话摘要
theme: default
materials: [M001, M002]
publish_confirm: false
---
正文第一段。
"""
    meta, body = fm.split_frontmatter(text)
    assert meta["title"] == "带: 冒号的标题"
    assert meta["materials"] == ["M001", "M002"]
    assert meta["publish_confirm"] is False
    assert body.startswith("正文第一段。")


def test_frontmatter_block_list_and_comments():
    text = """---
title: 标题 # 行尾注释
materials:
  - M001
  - M002
---
正文
"""
    meta, _ = fm.split_frontmatter(text)
    assert meta["title"] == "标题"
    assert meta["materials"] == ["M001", "M002"]


def test_frontmatter_missing_returns_empty():
    meta, body = fm.split_frontmatter("# 没有 frontmatter\n正文")
    assert meta == {}
    assert body.startswith("# 没有 frontmatter")


def test_frontmatter_bad_format_raises():
    with pytest.raises(fm.FrontmatterError):
        fm.split_frontmatter("---\n这一行没有冒号\n---\n正文")


def test_render_document_roundtrip():
    meta = {"title": "标题", "summary": "摘要", "materials": ["M001"], "publish_confirm": True}
    doc = fm.render_document(meta, "正文")
    parsed, body = fm.split_frontmatter(doc)
    assert parsed["title"] == "标题"
    assert parsed["materials"] == ["M001"]
    assert parsed["publish_confirm"] is True
    assert body.strip() == "正文"


def test_parse_heading_levels_and_text():
    doc = md.parse_markdown("# 一级\n\n## 二级 ##\n\n### 三级\n")
    headings = doc.headings()
    assert [h.level for h in headings] == [1, 2, 3]
    assert headings[1].text == "二级"


def test_parse_inline_basic():
    nodes = md.parse_inline("普通 **粗** 与 *斜* 和 `code`")
    kinds = [type(n).__name__ for n in nodes]
    assert "Strong" in kinds and "Emph" in kinds and "Code" in kinds


def test_parse_link_and_image():
    nodes = md.parse_inline("[文字](https://a.com \"标题\") ![图](images/x.png)")
    link = next(n for n in nodes if isinstance(n, md.Link))
    image = next(n for n in nodes if isinstance(n, md.Image))
    assert link.href == "https://a.com" and link.title == "标题"
    assert image.src == "images/x.png" and image.alt == "图"


def test_parse_list_nested():
    doc = md.parse_markdown("- a\n  - b\n- c\n")
    listblock = doc.blocks[0]
    assert isinstance(listblock, md.ListBlock)
    assert len(listblock.items) == 2
    nested = [b for b in listblock.items[0].blocks if isinstance(b, md.ListBlock)]
    assert nested and len(nested[0].items) == 1


def test_parse_ordered_list_start():
    doc = md.parse_markdown("3. 三\n4. 四\n")
    block = doc.blocks[0]
    assert block.ordered and block.start == 3


def test_parse_quote_and_code():
    doc = md.parse_markdown("> 引用\n> 第二行\n\n```py\nprint(1)\n```\n")
    assert isinstance(doc.blocks[0], md.Quote)
    code = next(b for b in doc.blocks if isinstance(b, md.CodeBlock))
    assert code.lang == "py" and code.code == "print(1)"


def test_parse_table_align():
    doc = md.parse_markdown("| a | b |\n|:--|--:|\n| 1 | 2 |\n")
    table = doc.blocks[0]
    assert isinstance(table, md.Table)
    assert table.align[:2] == ["left", "right"]
    assert md.inline_plain_text(table.rows[0][0]) == "1"


def test_parse_unclosed_fence_raises():
    with pytest.raises(md.MarkdownError):
        md.parse_markdown("```\n没有闭合\n")


def test_count_words_mixed():
    assert md.count_words("中文三个字") == 5
    assert md.count_words("hello world") == 2
    assert md.count_words("用 Markdown 写") == 3


def test_image_only_paragraph_is_image_block():
    doc = md.parse_markdown("![说明](images/a.png)\n")
    assert isinstance(doc.blocks[0], md.ImageBlock)
