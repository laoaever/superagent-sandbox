"""CLI 端到端测试：在临时副本里跑一遍完整流程。"""

import os
import shutil

import pytest

from conftest import REPO_ROOT, TOOLS_DIR, _make_png

from wechat_sop import cli


def _full_body():
    filler = "这一段用于填充正文，保证字数超过下限，同时覆盖中文标点与英文 Markdown 术语。" * 30
    return (
        "# 公众号 HTML 渲染元素覆盖样例\n\n"
        "这一段包含 **加粗**、*斜体*、~~删除线~~、`inline code`，以及一个 [外部链接](https://example.com/a)。\n\n"
        + filler + "\n\n"
        "## 列表\n\n- 无序项一\n- 无序项二\n  - 嵌套项 A\n- 无序项三\n\n"
        "1. 有序项一\n2. 有序项二\n\n"
        "## 引用与代码\n\n> 这是一段引用，说明一句话观点。\n\n"
        "```python\ndef greet(name):\n    print(\"Hello, \" + name)\n```\n\n"
        "## 图片与表格\n\n![耗时对比示意图](images/chart.png)\n\n"
        "| 方式 | 耗时 |\n|:---|---:|\n| 手动排版 | 32 分钟 |\n\n"
        + filler + "\n\n"
        "最后一段，建议你先按文档准备一篇样例跑通流程，然后收藏这份清单。\n"
    )


def _copy_skeleton(tmp_path):
    root = tmp_path / "repo"
    for name in ("tools", "docs", "config", "topics", "articles"):
        shutil.copytree(os.path.join(REPO_ROOT, name), root / name)
    shutil.rmtree(root / "articles")
    (root / "articles").mkdir()
    for name in ("topics.md", "materials.md"):
        (root / "topics" / name).unlink(missing_ok=True)
    for junk in ("__pycache__",):
        for dirpath, dirnames, _ in os.walk(root / "tools"):
            if junk in dirnames:
                shutil.rmtree(os.path.join(dirpath, junk))
    return root


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = _copy_skeleton(tmp_path)
    monkeypatch.chdir(root)
    return root


def _run(argv):
    return cli.main(argv)


def test_full_workflow(sandbox, capsys):
    assert _run(["init"]) == 0
    assert _run(["materials", "add", "--title", "读者问题",
                 "--tags", "读者问题", "--points", "排版慢"]) == 0
    material_id = [line.split()[1]
                   for line in (sandbox / "topics" / "materials.md").read_text(encoding="utf-8").splitlines()
                   if line.startswith("## M")][-1]
    assert _run(["topics", "add", "--title", "怎么写公众号",
                 "--angle", "固定流程", "--audience", "运营",
                 "--material", material_id]) == 0

    topics_path = sandbox / "topics" / "topics.md"
    text = topics_path.read_text(encoding="utf-8")
    topic_id = [line.split()[1] for line in text.splitlines() if line.startswith("## T")][0]

    assert _run(["topics", "use", topic_id, "--slug", "demo"]) == 0
    article_dirs = list((sandbox / "articles").iterdir())
    assert len(article_dirs) == 1
    article_dir = article_dirs[0]
    article_path = article_dir / "article.md"
    assert article_path.exists()
    assert (article_dir / "outline.md").exists()

    # 用完整正文替换模板占位内容
    body = _full_body()
    _make_png(str(article_dir / "images" / "chart.png"), 800, 450)
    _make_png(str(article_dir / "cover.png"), 900, 383)
    text = article_path.read_text(encoding="utf-8")
    head = text.split("---", 2)
    frontmatter = "---" + head[1].replace("publish_confirm: false", "publish_confirm: true") + "---\n\n"
    article_path.write_text(frontmatter + body, encoding="utf-8")

    # 大纲结构
    assert _run(["outline", str(article_path)]) == 0

    # 排版
    assert _run(["render", str(article_path)]) == 0
    assert (article_dir / "outline.html").exists()
    assert (article_dir / "preview.html").exists()
    preview = (article_dir / "preview.html").read_text(encoding="utf-8")
    assert "复制到公众号" in preview

    # 发布前检查：干净文章应通过
    code = _run(["check", str(article_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert (article_dir / "check-report.md").exists()


def test_topics_use_requires_fields(sandbox, capsys):
    assert _run(["init"]) == 0
    assert _run(["topics", "add", "--title", "缺字段的选题"]) == 0
    text = (sandbox / "topics" / "topics.md").read_text(encoding="utf-8")
    topic_id = [line.split()[1] for line in text.splitlines() if line.startswith("## T")][-1]
    assert _run(["topics", "use", topic_id, "--slug", "x"]) == 1
    assert "缺少必需字段" in capsys.readouterr().err


def test_format_write(sandbox, capsys):
    article = sandbox / "articles" / "a.md"
    article.write_text("中文,后面还有word粘连。\n", encoding="utf-8")
    assert _run(["format", str(article)]) == 0
    assert "中文" in capsys.readouterr().out
    assert _run(["format", str(article), "--write"]) == 0
    assert "word" in article.read_text(encoding="utf-8")


def test_theme_lint_cli(sandbox):
    assert _run(["theme-lint"]) == 0
    assert _run(["theme-lint", "default"]) == 0


def test_check_missing_article_returns_error(sandbox, capsys):
    assert _run(["check", str(sandbox / "articles" / "nope.md")]) == 1
