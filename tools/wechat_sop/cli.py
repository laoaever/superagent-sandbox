"""命令行入口。

在仓库根目录执行（需要 `PYTHONPATH=tools`）：

    python3 -m wechat_sop init
    python3 -m wechat_sop topics list
    python3 -m wechat_sop topics add --title "..." --angle "..." --audience "..."
    python3 -m wechat_sop topics use T2026110301 --slug my-article
    python3 -m wechat_sop topics done T2026110301 --url https://mp.weixin.qq.com/s/xxx
    python3 -m wechat_sop materials add --title "..." --tags 读者问题
    python3 -m wechat_sop templates
    python3 -m wechat_sop new --topic T2026110301 --template 教程 --slug my-article
    python3 -m wechat_sop outline articles/2026-11-03-my-article/article.md
    python3 -m wechat_sop format articles/2026-11-03-my-article/article.md --write
    python3 -m wechat_sop render articles/2026-11-03-my-article/article.md --open
    python3 -m wechat_sop check articles/2026-11-03-my-article/article.md
    python3 -m wechat_sop theme-lint [default]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import webbrowser
from typing import List, Optional

from . import check as checker
from . import frontmatter as fm
from . import render as render_mod
from . import library, markdown as md, preview, templates, theme as theme_mod
from . import textfmt

ROOT_MARKERS = ("topics", "articles", "tools", "docs")


def find_root(start: Optional[str] = None) -> str:
    """从当前目录向上找仓库根（含 topics/articles/tools/docs 的目录）。"""
    current = os.path.abspath(start or os.getcwd())
    while True:
        if all(os.path.isdir(os.path.join(current, marker)) for marker in ROOT_MARKERS):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start or os.getcwd())
        current = parent


# ---------------------------------------------------------------- init


def cmd_init(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    library.ensure_library(root)
    os.makedirs(os.path.join(root, "articles"), exist_ok=True)
    config_dir = os.path.join(root, "config")
    os.makedirs(config_dir, exist_ok=True)
    banned = os.path.join(config_dir, "checkwords.txt")
    if not os.path.exists(banned):
        with open(banned, "w", encoding="utf-8") as f:
            f.write("# 发布前检查的敏感/违禁词表，一行一个，# 开头为注释\n")
            f.write("# 默认包含广告法风险词与常见引流话术，可按自己的行业补充\n")
            for word in ["最好", "最高级", "第一品牌", "国家级", "点击领取", "加微信领"]:
                f.write(word + "\n")
    style = os.path.join(config_dir, "style.md")
    if not os.path.exists(style):
        with open(style, "w", encoding="utf-8") as f:
            f.write(
                "# 我的写作风格\n\n"
                "- 读者：（写给谁）\n"
                "- 语气：（像同事讲经验，还是像老师讲课）\n"
                "- 从不写：（例如「希望对你有帮助」）\n"
                "- 习惯：（先给结论，再给证据）\n"
            )
    print("✅ 已初始化：%s" % root)
    print("   topics/topics.md, topics/materials.md, config/checkwords.txt, config/style.md")
    return 0


# ---------------------------------------------------------------- topics


def cmd_topics(args: argparse.Namespace) -> int:
    root = find_root()
    library.ensure_library(root)
    if args.action == "list":
        entries = library.parse_entries(os.path.join(root, "topics", "topics.md"))
        if not entries:
            print("还没有选题。用 `topics add` 添加，或先在 topics/topics.md 里手写。")
            return 0
        print("%-16s %-10s %s" % ("编号", "状态", "标题"))
        for entry in entries:
            print("%-16s %-10s %s" % (entry["id"], entry["meta"].get("状态", "-"), entry["title"]))
        return 0
    if args.action == "add":
        materials = [m for m in re.split(r"[,，\s]+", args.material or "") if m]
        topic_id = library.add_topic(
            root, args.title, angle=args.angle or "", audience=args.audience or "",
            materials=materials, reason=args.reason or "", difference=args.difference or "",
            words=args.words or "",
        )
        print("✅ 已添加选题 %s：%s" % (topic_id, args.title))
        print("   下一步：python3 -m wechat_sop topics use %s --slug <英文短名>" % topic_id)
        return 0
    if args.action == "use":
        entry = library.get_entry(root, args.topic_id)
        if entry is None or not entry["id"].startswith("T"):
            print("❌ 找不到选题：%s" % args.topic_id, file=sys.stderr)
            return 2
        missing = [k for k in ("人群", "一句话结论", "独特证据") if not entry["meta"].get(k) or entry["meta"].get(k) in ("（待补）",)]
        if missing and not args.force:
            print("❌ 选题卡缺少必需字段：%s（补全后再立项，或加 --force）" % "、".join(missing), file=sys.stderr)
            return 1
        status = entry["meta"].get("状态", "draft")
        if status not in ("draft", "planned", "writing") and not args.force:
            print("❌ 选题状态是 %s，不能重复立项（加 --force 强制）" % status, file=sys.stderr)
            return 1
        slug = args.slug or entry["title"]
        article_dir = library.create_article_dir(root, slug)
        template = templates.get_template(args.template)
        meta = {
            "title": entry["title"],
            "summary": entry["meta"].get("一句话结论", ""),
            "theme": args.theme or template.theme,
            "template": template.name,
            "author": args.author or "",
            "materials": [m for m in re.split(r"[,，\s]+", entry["meta"].get("关联素材", "")) if m],
            "cover": "cover.png",
            "publish_confirm": False,
        }
        article_path = os.path.join(article_dir, "article.md")
        with open(article_path, "w", encoding="utf-8") as f:
            f.write(templates.render_article(template, entry["title"], summary=meta["summary"],
                                             author=meta["author"], materials=meta["materials"],
                                             theme=meta["theme"]))
        with open(os.path.join(article_dir, "outline.md"), "w", encoding="utf-8") as f:
            f.write(templates.render_outline(template, entry["title"]))
        library.mark_topic(root, args.topic_id, "planned", article_dir)
        print("✅ 已立项 %s → %s" % (args.topic_id, os.path.relpath(article_dir, root)))
        print("   下一步：编辑 %s 的 outline.md / article.md" % os.path.relpath(article_dir, root))
        return 0
    if args.action == "done":
        entry = library.get_entry(root, args.topic_id)
        if entry is None:
            print("❌ 找不到选题：%s" % args.topic_id, file=sys.stderr)
            return 2
        library.set_entry_meta(root, args.topic_id, "状态", "published")
        if args.url:
            library.set_entry_meta(root, args.topic_id, "文章链接", args.url)
        print("✅ 选题 %s 已标记为 published" % args.topic_id)
        return 0
    if args.action == "status":
        entry = library.get_entry(root, args.topic_id)
        if entry is None:
            print("❌ 找不到选题：%s" % args.topic_id, file=sys.stderr)
            return 2
        library.set_entry_meta(root, args.topic_id, "状态", args.value)
        print("✅ 选题 %s 状态改为 %s" % (args.topic_id, args.value))
        return 0
    print("未知子命令", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- materials


def cmd_materials(args: argparse.Namespace) -> int:
    root = find_root()
    library.ensure_library(root)
    if args.action == "list":
        entries = library.parse_entries(os.path.join(root, "topics", "materials.md"))
        if not entries:
            print("还没有素材。用 `materials add` 添加。")
            return 0
        for entry in entries:
            print("%-16s %-14s %s" % (entry["id"], entry["meta"].get("标签", "-"), entry["title"]))
        return 0
    if args.action == "add":
        material_id = library.add_material(root, args.title, tags=args.tags or "",
                                           source=args.source or "", points=args.points or "",
                                           quota=args.quota or "")
        print("✅ 已添加素材 %s：%s" % (material_id, args.title))
        return 0
    return 2


# ---------------------------------------------------------------- templates / new


def cmd_templates(args: argparse.Namespace) -> int:
    print("%-8s %-16s %-6s %s" % ("名称", "文章类型", "默认主题", "说明"))
    for template in templates.list_templates():
        print("%-8s %-16s %-8s %s" % (template.name, template.display_name, template.theme, template.description))
    print("\n用法：python3 -m wechat_sop new --template 教程 --slug my-article")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    root = find_root()
    template = templates.get_template(args.template)
    title = args.title or ""
    materials: List[str] = []
    if args.topic:
        entry = library.get_entry(root, args.topic)
        if entry is None:
            print("❌ 找不到选题：%s" % args.topic, file=sys.stderr)
            return 2
        title = title or entry["title"]
        materials = [m for m in re.split(r"[,，\s]+", entry["meta"].get("关联素材", "")) if m]
    if not title:
        print("❌ 需要 --title 或 --topic", file=sys.stderr)
        return 2
    article_dir = library.create_article_dir(root, args.slug or title)
    with open(os.path.join(article_dir, "article.md"), "w", encoding="utf-8") as f:
        f.write(templates.render_article(template, title, summary=args.summary or "",
                                         author=args.author or "", materials=materials,
                                         theme=args.theme))
    with open(os.path.join(article_dir, "outline.md"), "w", encoding="utf-8") as f:
        f.write(templates.render_outline(template, title))
    if args.topic:
        library.mark_topic(root, args.topic, "planned", article_dir)
    print("✅ 已创建文章目录：%s" % os.path.relpath(article_dir, root))
    print("   1) 先填 outline.md 的大纲")
    print("   2) 再改 article.md 正文（【待补】标记会被发布前检查拦截）")
    return 0


# ---------------------------------------------------------------- outline


def cmd_outline(args: argparse.Namespace) -> int:
    meta, body = fm.read_article(args.article)
    doc = md.parse_markdown(body)
    print("文章：%s" % meta.get("title") or "(无标题)")
    print("字数：%d  段落：%d  图片：%d" % (
        md.count_words(body),
        sum(1 for b in md.iter_blocks(doc.blocks) if isinstance(b, md.Paragraph)),
        checker.image_references(doc).__len__(),
    ))
    print()
    h2 = [b for b in doc.blocks if isinstance(b, md.Heading) and b.level == 2]
    for index, heading in enumerate(h2, start=1):
        # 统计本节段落数
        started = False
        count = 0
        for block in doc.blocks:
            if block is heading:
                started = True
                continue
            if started and isinstance(block, md.Heading) and block.level <= 2:
                break
            if started and isinstance(block, (md.Paragraph, md.ListBlock)):
                count += 1
        print("%02d %s  （%d 段）" % (index, heading.text, count))
    problems = _outline_problems(doc, h2)
    if problems:
        print("\n结构问题：")
        for problem in problems:
            print(" ⚠️ " + problem)
    else:
        print("\n✅ 结构无明显问题")
    return 0


def _outline_problems(doc: md.Document, h2: List[md.Heading]) -> List[str]:
    problems: List[str] = []
    if len(h2) < 3:
        problems.append("二级标题只有 %d 个（建议 3–8 个）" % len(h2))
    if len(h2) > 8:
        problems.append("二级标题有 %d 个，可能过长（建议 ≤8 个）" % len(h2))
    levels = [b.level for b in doc.blocks if isinstance(b, md.Heading)]
    previous = 0
    for level in levels:
        if previous and level > previous + 1:
            problems.append("标题层级跳跃：H%d 直接到 H%d" % (previous, level))
        previous = level
    for heading in h2:
        started = False
        content = 0
        for block in doc.blocks:
            if block is heading:
                started = True
                continue
            if started and isinstance(block, md.Heading) and block.level <= 2:
                break
            if started and isinstance(block, (md.Paragraph, md.ListBlock)):
                content += len(md.block_plain_text(block))
        if content < 40:
            problems.append("章节「%s」内容过少（%d 字），可能是空壳章节" % (heading.text, content))
    if h2 and not any(re.search(r"(试试|可以|建议|记得|点击|收藏|关注|评论|留言|转发)", md.block_plain_text(b))
                      for b in doc.blocks[-2:]):
        problems.append("结尾似乎没有具体行动建议")
    return problems


# ---------------------------------------------------------------- format


def cmd_format(args: argparse.Namespace) -> int:
    path = args.article
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta, body = fm.split_frontmatter(text)
    fixed = textfmt.format_text(body)
    changed = fixed != body
    if args.write:
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fm.render_document(meta, fixed) if meta else fixed)
            print("✅ 已写回（有改动）：%s" % path)
        else:
            print("✅ 无需修改：%s" % path)
        return 0
    if changed:
        import difflib
        diff = difflib.unified_diff(body.splitlines(), fixed.splitlines(),
                                    fromfile="原文", tofile="格式化后", lineterm="", n=0)
        print("\n".join(diff))
        print("\n提示：加 --write 写回原文件")
        return 0
    print("✅ 无需修改")
    return 0


# ---------------------------------------------------------------- render


def cmd_render(args: argparse.Namespace) -> int:
    path = args.article
    meta, body = fm.read_article(path)
    theme_value = args.theme or str(meta.get("theme") or "default")
    try:
        theme = theme_mod.load_theme(theme_value)
    except theme_mod.ThemeError as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 2
    result = render_mod.render_markdown(body, theme, numbered_headings=not args.no_numbering)
    base_dir = os.path.dirname(os.path.abspath(path))
    outline_path = os.path.join(base_dir, "outline.html")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(result.body)
    word_count = md.count_words(body)
    preview_html = preview.wrap_preview(result.body, meta, theme,
                                        footnotes=len(result.footnotes), word_count=word_count)
    preview_path = os.path.join(base_dir, "preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(preview_html)
    print("✅ 已生成：")
    print("   %s（正文片段 %d 字节）" % (outline_path, len(result.body.encode("utf-8"))))
    print("   %s（预览页）" % preview_path)
    print("   标题：%s   主题：%s   字数：%d   图片：%d   外链脚注：%d"
          % (meta.get("title", ""), theme.get("name"), word_count, result.image_count, len(result.footnotes)))
    if args.open:
        webbrowser.open("file://" + os.path.abspath(preview_path))
    return 0


# ---------------------------------------------------------------- check


def cmd_check(args: argparse.Namespace) -> int:
    result = checker.check_article(args.article, stage=args.stage, root_dir=find_root(),
                                   cover=args.cover, theme_name=args.theme)
    report_path = checker.write_report(result)
    print(checker.format_report(result))
    print("报告已写入：%s" % report_path)
    if args.strict and result.warns:
        return 1
    return result.exit_code()


# ---------------------------------------------------------------- theme-lint


def cmd_theme_lint(args: argparse.Namespace) -> int:
    targets = [args.name] if args.name else theme_mod.list_themes()
    failed = False
    for name in targets:
        theme = theme_mod.load_theme(name)
        errors, warnings = theme_mod.lint_theme(theme)
        state = "✅" if not errors else "❌"
        print("%s %s（%s）" % (state, theme.get("name", name), theme.get("display_name", "")))
        for error in errors:
            print("   ❌ " + error)
        for warning in warnings:
            print("   ⚠️ " + warning)
        failed = failed or bool(errors)
    return 1 if failed else 0


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat_sop", description="公众号写作流程 SOP 配套脚本")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="初始化选题库/素材库/配置目录")
    p_init.add_argument("--root", default=None)
    p_init.set_defaults(func=cmd_init)

    p_topics = sub.add_parser("topics", help="选题库")
    topics_sub = p_topics.add_subparsers(dest="action")
    p_list = topics_sub.add_parser("list", help="列出选题")
    p_list.set_defaults(func=cmd_topics)
    p_add = topics_sub.add_parser("add", help="新增选题卡")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--angle", default="")
    p_add.add_argument("--audience", default="")
    p_add.add_argument("--material", default="", help="关联素材编号，逗号分隔")
    p_add.add_argument("--reason", default="")
    p_add.add_argument("--difference", default="")
    p_add.add_argument("--words", default="")
    p_add.set_defaults(func=cmd_topics)
    p_use = topics_sub.add_parser("use", help="立项：检查字段并生成文章目录")
    p_use.add_argument("topic_id")
    p_use.add_argument("--slug", default="")
    p_use.add_argument("--template", default=None)
    p_use.add_argument("--theme", default=None)
    p_use.add_argument("--author", default="")
    p_use.add_argument("--force", action="store_true")
    p_use.set_defaults(func=cmd_topics)
    p_done = topics_sub.add_parser("done", help="标记选题已发布")
    p_done.add_argument("topic_id")
    p_done.add_argument("--url", default="")
    p_done.set_defaults(func=cmd_topics)
    p_status = topics_sub.add_parser("status", help="修改选题状态")
    p_status.add_argument("topic_id")
    p_status.add_argument("value", choices=["draft", "planned", "writing", "published", "dropped"])
    p_status.set_defaults(func=cmd_topics)
    p_topics.set_defaults(func=cmd_topics, action=None)

    p_materials = sub.add_parser("materials", help="素材库")
    materials_sub = p_materials.add_subparsers(dest="action")
    m_list = materials_sub.add_parser("list")
    m_list.set_defaults(func=cmd_materials)
    m_add = materials_sub.add_parser("add")
    m_add.add_argument("--title", required=True)
    m_add.add_argument("--tags", default="")
    m_add.add_argument("--source", default="")
    m_add.add_argument("--points", default="")
    m_add.add_argument("--quota", default="")
    m_add.set_defaults(func=cmd_materials)
    p_materials.set_defaults(func=cmd_materials, action=None)

    p_templates = sub.add_parser("templates", help="列出写作模板")
    p_templates.set_defaults(func=cmd_templates)

    p_new = sub.add_parser("new", help="用模板新建文章")
    p_new.add_argument("--topic", default="")
    p_new.add_argument("--title", default="")
    p_new.add_argument("--slug", default="")
    p_new.add_argument("--template", default=None)
    p_new.add_argument("--theme", default=None)
    p_new.add_argument("--summary", default="")
    p_new.add_argument("--author", default="")
    p_new.set_defaults(func=cmd_new)

    p_outline = sub.add_parser("outline", help="检查大纲结构")
    p_outline.add_argument("article")
    p_outline.set_defaults(func=cmd_outline)

    p_format = sub.add_parser("format", help="中文标点/空格自动修复")
    p_format.add_argument("article")
    p_format.add_argument("--write", action="store_true")
    p_format.set_defaults(func=cmd_format)

    p_render = sub.add_parser("render", help="Markdown → 公众号 HTML 片段 + 预览页")
    p_render.add_argument("article")
    p_render.add_argument("--theme", default=None)
    p_render.add_argument("--no-numbering", action="store_true")
    p_render.add_argument("--open", action="store_true")
    p_render.set_defaults(func=cmd_render)

    p_check = sub.add_parser("check", help="发布前检查")
    p_check.add_argument("article")
    p_check.add_argument("--stage", choices=["draft", "publish"], default="publish")
    p_check.add_argument("--cover", default=None)
    p_check.add_argument("--theme", default=None)
    p_check.add_argument("--strict", action="store_true", help="风险项也视为失败")
    p_check.set_defaults(func=cmd_check)

    p_lint = sub.add_parser("theme-lint", help="检查主题是否符合排版规范")
    p_lint.add_argument("name", nargs="?", default=None)
    p_lint.set_defaults(func=cmd_theme_lint)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    if getattr(args, "func", None) is None:
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except (library.LibraryError, templates.TemplateError, md.MarkdownError,
            fm.FrontmatterError, theme_mod.ThemeError) as exc:
        print("❌ %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
