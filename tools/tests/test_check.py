"""发布前检查测试。"""

import os

from wechat_sop import check as checker

LONG_BODY = (
    "## 第一部分\n\n"
    + "这是一段用于填充正文的中文内容，确保字数超过下限。" * 40 +
    "\n\n## 第二部分\n\n"
    + "再来一段内容，说明建议你先跑一遍流程，然后收藏这份清单。" * 30 +
    "\n\n![示意图](images/chart.png)\n"
)


def _codes(result):
    return {issue.code for issue in result.issues}


def _render(article_path):
    from wechat_sop import frontmatter as fm, render, theme
    meta, body = fm.read_article(article_path)
    result = render.render_markdown(body, theme.load_theme(meta.get("theme", "default")))
    path = os.path.join(os.path.dirname(article_path), "outline.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(result.body)
    return path


def test_missing_file():
    result = checker.check_article("/nonexistent/article.md")
    assert not result.ok
    assert "file-missing" in _codes(result)


def test_title_and_summary_missing(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)},
                           meta={"title": "", "summary": ""})
    result = checker.check_article(path, stage="draft")
    assert {"title-missing", "summary-missing"} <= _codes(result)


def test_title_too_long(make_article):
    path, _ = make_article(body=LONG_BODY, meta={"title": "标" * 70})
    result = checker.check_article(path, stage="draft")
    assert "title-too-long" in _codes(result)


def test_title_long_warns(make_article):
    path, _ = make_article(body=LONG_BODY, meta={"title": "标" * 40})
    result = checker.check_article(path, stage="draft")
    assert "title-long" in _codes(result)
    assert "title-too-long" not in _codes(result)


def test_too_short(make_article):
    path, _ = make_article(body="很短的一点内容。")
    result = checker.check_article(path, stage="draft")
    assert "too-short" in _codes(result)


def test_placeholder_blocked(make_article):
    path, _ = make_article(body=LONG_BODY + "\n【待补】这里还没写。\n")
    result = checker.check_article(path, stage="draft")
    assert "placeholder" in _codes(result)


def test_banned_word(make_article):
    path, _ = make_article(body=LONG_BODY + "\n这里有最强性能的方案。\n")
    result = checker.check_article(path, stage="draft")
    assert "banned-word" in _codes(result)


def test_draft_stage_skips_publish_checks(make_article):
    path, _ = make_article(body=LONG_BODY, cover=False)
    result = checker.check_article(path, stage="draft")
    assert "cover-missing" not in _codes(result)
    assert "publish-confirm" not in _codes(result)


def test_cover_missing(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)}, cover=False)
    result = checker.check_article(path, stage="publish")
    assert "cover-missing" in _codes(result)


def test_image_missing(make_article):
    path, _ = make_article(body=LONG_BODY)  # 引用 images/chart.png 但没有创建
    result = checker.check_article(path, stage="publish")
    assert "image-missing" in _codes(result)


def test_image_too_small(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (100, 100)})
    result = checker.check_article(path, stage="publish")
    assert "image-small" in _codes(result)


def test_image_without_alt_warns(make_article):
    body = LONG_BODY.replace("![示意图]", "![]")
    path, _ = make_article(body=body, images={"chart.png": (800, 450)})
    result = checker.check_article(path, stage="publish")
    assert "image-no-alt" in _codes(result)
    assert result.stats["images"] == 1


def test_external_image_warns(make_article):
    body = LONG_BODY.replace("images/chart.png", "https://example.com/a.png")
    path, _ = make_article(body=body)
    result = checker.check_article(path, stage="publish")
    assert "image-external" in _codes(result)


def test_theme_missing(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)}, meta={"theme": "nope"})
    result = checker.check_article(path, stage="publish")
    assert "theme-missing" in _codes(result)


def test_render_missing_and_forbidden(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)})
    result = checker.check_article(path, stage="publish")
    assert "render-missing" in _codes(result)

    outline_html = os.path.join(os.path.dirname(path), "outline.html")
    with open(outline_html, "w", encoding="utf-8") as f:
        f.write("<div class='x'>测试</div><style>p{}</style>")
    result = checker.check_article(path, stage="publish")
    codes = _codes(result)
    assert {"html-div", "html-class", "html-style"} <= codes


def test_publish_confirm_gate(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)},
                           meta={"publish_confirm": False})
    _render(path)
    result = checker.check_article(path, stage="publish")
    assert "publish-confirm" in _codes(result)

    path2, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)},
                            meta={"publish_confirm": True}, dir_name="2026-11-03-ok")
    _render(path2)
    result2 = checker.check_article(path2, stage="publish")
    assert "publish-confirm" not in _codes(result2)


def test_half_width_punct_and_spacing_warns(make_article):
    body = LONG_BODY + "\n这段有半角逗号,和中英文粘连word。\n"
    path, _ = make_article(body=body, images={"chart.png": (800, 450)})
    result = checker.check_article(path, stage="draft")
    assert "half-width-punct" in _codes(result)
    assert "cjk-spacing" in _codes(result)


def test_clean_article_passes(make_article):
    path, _ = make_article(body=LONG_BODY, images={"chart.png": (800, 450)},
                           meta={"publish_confirm": True})
    _render(path)
    result = checker.check_article(path, stage="publish")
    assert result.ok, [i.message for i in result.blocks]
    assert result.exit_code() == 0


def test_report_written(make_article):
    path, article_dir = make_article(body=LONG_BODY, images={"chart.png": (800, 450)},
                                     meta={"publish_confirm": True})
    _render(path)
    result = checker.check_article(path, stage="publish")
    report_path = checker.write_report(result)
    assert os.path.exists(report_path)
    content = open(report_path, encoding="utf-8").read()
    assert "发布前检查报告" in content
    assert "人工复核" in content


def test_image_size_png_gif_jpeg(tmp_path, make_png):
    png = make_png(str(tmp_path / "a.png"), 640, 480)
    assert checker.image_size(png) == (640, 480)
    gif = tmp_path / "b.gif"
    gif.write_bytes(b"GIF89a" + bytes([0x20, 0x02, 0x58, 0x02]) + b"\x00" * 16)
    assert checker.image_size(str(gif)) == (544, 600)
    # 最小 JPEG：SOI + SOF0(高 480, 宽 640) + EOI
    jpeg = tmp_path / "c.jpg"
    sof = b"\xff\xc0\x00\x11\x08\x01\xe0\x02\x80\x03" + b"\x00" * 9
    jpeg.write_bytes(b"\xff\xd8" + sof + b"\xff\xd9")
    assert checker.image_size(str(jpeg)) == (640, 480)
    assert checker.image_size(str(tmp_path / "nope.png")) is None
