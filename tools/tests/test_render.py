"""渲染层测试：公众号兼容性约束是硬要求。"""

import re

import pytest

from wechat_sop import markdown as md
from wechat_sop import render, theme

FORBIDDEN_IN_OUTPUT = {
    "style-tag": r"<style[\s>]",
    "script-tag": r"<script[\s>]",
    "div-tag": r"<div[\s>]",
    "class-attr": r"\sclass\s*=",
    "id-attr": r"\sid\s*=",
    "css-var": r"var\s*\(\s*--",
    "gradient": r"(linear|radial|conic)-gradient",
    "media-query": r"@media",
    "position": r"position\s*:\s*(fixed|absolute|sticky)",
    "ul-tag": r"<ul[\s>]",
}


@pytest.fixture(params=theme.list_themes())
def any_theme(request):
    return theme.load_theme(request.param)


def test_output_has_no_forbidden_constructs(sample_body, any_theme):
    result = render.render_markdown(sample_body, any_theme)
    for name, pattern in FORBIDDEN_IN_OUTPUT.items():
        assert not re.search(pattern, result.body, re.I), "输出中出现了 %s" % name


def test_output_contains_no_doctype_or_full_page(sample_body, any_theme):
    result = render.render_markdown(sample_body, any_theme)
    for token in ("<!DOCTYPE", "<html", "<head", "<body"):
        assert token.lower() not in result.body.lower()


def test_text_nodes_wrapped_in_leaf_span(sample_body):
    result = render.render_markdown(sample_body, theme.load_theme("default"))
    assert '<span leaf="">' in result.body
    # 每个中文文本节点都应位于 span leaf 内：所有裸的中文字符出现在标签外即视为漏包
    # 去掉所有 span leaf 内的文本后，剩余标签外的文本不应含汉字
    # （代码块与高亮片段属于代码区，公众号会保留其节点样式，不要求再包 leaf）
    outside_leaf = re.sub(r'<span leaf="">[^<]*</span>', "", result.body)
    outside_leaf = re.sub(r'<section style="margin:0 0 1.5em;background:[^"]*">.*?</section></section>', "", outside_leaf, flags=re.S)
    outside_text = re.sub(r"<[^>]+>", "", outside_leaf)
    assert not re.search("[\u4e00-\u9fff]", outside_text)


def test_external_links_become_footnotes():
    result = render.render_markdown(
        "参考 [外部](https://example.com/a)，再看 [外部](https://example.com/a)。", theme.load_theme("default"))
    assert len(result.footnotes) == 1  # 同一地址只登记一次
    assert "[1]" in result.body
    assert 'href="https://example.com/a"' not in result.body
    assert "参考链接" in result.body


def test_wechat_links_stay_clickable():
    result = render.render_markdown("[内链](https://mp.weixin.qq.com/s/x)", theme.load_theme("default"))
    assert 'href="https://mp.weixin.qq.com/s/x"' in result.body
    assert not result.footnotes


def test_images_have_inline_width_and_alt():
    result = render.render_markdown("![示意](images/a.png)", theme.load_theme("default"))
    assert 'src="images/a.png"' in result.body
    assert 'alt="示意"' in result.body
    assert "width:100%" in result.body.replace(" ", "")
    assert "width=" not in result.body.replace("width:", "")  # 不使用 width 属性


def test_nested_list_is_flattened_into_paragraphs():
    source = "- 一\n  - 子项\n- 二\n"
    result = render.render_markdown(source, theme.load_theme("default"))
    assert "<ul" not in result.body and "<ol" not in result.body
    assert "•" in result.body
    assert "子项" in result.body


def test_code_block_is_card_with_lang_label():
    result = render.render_markdown("```python\nprint(1)\n```", theme.load_theme("default"))
    assert "PYTHON" in result.body.upper()
    assert "print" in result.body
    assert theme.load_theme("default")["x"]["code_block_bg"] in result.body


def test_headings_numbered():
    result = render.render_markdown("## 一\n\n正文\n\n## 二\n\n正文", theme.load_theme("default"))
    assert ">01<" in result.body.replace("\n", "")
    assert ">02<" in result.body.replace("\n", "")


def test_numbering_can_be_disabled():
    result = render.render_markdown("## 一\n\n正文", theme.load_theme("default"), numbered_headings=False)
    assert ">01<" not in result.body.replace("\n", "")


def test_table_wrapped_in_scroll_container():
    result = render.render_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n", theme.load_theme("default"))
    assert "overflow-x:auto" in result.body
    assert "<table" in result.body


def test_html_escaped_in_text():
    result = render.render_markdown("文本 <script>alert(1)</script> 结束", theme.load_theme("default"))
    assert "<script>" not in result.body
    assert "&lt;script&gt;" in result.body


def test_numeric_footnote_is_published_text():
    result = render.render_markdown("参考 [报告](https://example.com/report)。", theme.load_theme("default"))
    # 上标脚注编号可以没有 leaf（渲染样式已足够），但脚注标题/链接文本必须有 leaf
    assert '<span leaf="">参考链接</span>' in result.body
    assert '<span leaf="">https://example.com/report</span>' in result.body


def test_markdown_inside_code_not_rendered():
    result = render.render_markdown("```\n**不该加粗**\n```", theme.load_theme("default"))
    assert "<strong" not in result.body


def test_highlight_code_keeps_entities():
    x = theme.load_theme("tech")["x"]
    html = render.highlight_code('const a = "<b>"; // 注释', "js", x)
    assert "&lt;b&gt;" in html
    assert "<b>" not in html


def test_render_is_deterministic():
    body = "## 标题\n\n正文 **加粗**\n"
    first = render.render_markdown(body, theme.load_theme("serif")).body
    second = render.render_markdown(body, theme.load_theme("serif")).body
    assert first == second
