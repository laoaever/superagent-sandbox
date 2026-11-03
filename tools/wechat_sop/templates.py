"""写作模板：按文章类型给出骨架、每节提示与 frontmatter 默认值。

模板是**骨架**，允许增删章节；`new` 命令会把模板渲染成文章初稿。
每个模板的 `sections` 里写的是「这一节要论证什么、用什么证据」，
正文占位文本会明确提示删除，`check` 会把它当作未完成标记。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Section:
    title: str
    hint: str


@dataclass
class Template:
    name: str
    display_name: str
    description: str
    sections: List[Section]
    hook: str = ""
    cta: str = ""
    theme: str = "default"
    words: str = "2000"


TEMPLATES: Dict[str, Template] = {
    "观点": Template(
        name="观点",
        display_name="观点 / 深度分析",
        description="钩子 → 现象 → 根源 → 主张 → 证据 → 反方回应 → 行动",
        hook="用一个具体场景或数据开场，让读者觉得「这跟我有关」。不要用「在这个时代」这类空开头。",
        cta="给读者一个今天就能做的动作。",
        theme="serif",
        sections=[
            Section("现象：我看到的 X", "描述一个具体、可验证的现象或数据。写清时间、对象、数字。"),
            Section("根源：为什么会这样", "给出 1–2 个根本原因，拒绝「大家都这样」式的解释。"),
            Section("主张：我认为应该 Y", "用一句话说清你的主张，后面所有内容都在服务它。"),
            Section("证据：我凭什么这么讲", "列出证据：自测数据、案例、文献。每条都要能追溯。"),
            Section("反方：有人会说……", "主动回应最有力的反方观点，展示你考虑过。"),
        ],
        words="2500",
    ),
    "教程": Template(
        name="教程",
        display_name="教程 / 操作指南",
        description="钩子 → 你将得到什么 → 前提 → 步骤 1..N → 常见坑 → 行动",
        hook="描述读者现在的处境，以及读完这篇之后会变成什么样。",
        cta="建议读者立刻按第一步试一次。",
        theme="tech",
        sections=[
            Section("读完你能做到什么", "写清产出：读者按步骤做完会得到什么可验证的结果。"),
            Section("开始前需要准备什么", "列出工具、账号、环境、前置知识；缺一项就会卡住。"),
            Section("第 1 步：……", "每步只做一件事，给出可复制粘贴的命令或操作。"),
            Section("第 2 步：……", "同上。步骤标题里直接写「做什么」，不要写「第一步」。"),
            Section("常见坑", "列出新手最容易错的 3 个地方，以及错误现象与原因。"),
        ],
        words="2000",
    ),
    "盘点": Template(
        name="盘点",
        display_name="盘点 / 工具对比",
        description="钩子 → 评选标准 → 条目 1..N（是什么 / 适合谁 / 不足）→ 怎么选 → 行动",
        hook="先说清「为什么值得盘」以及「这篇不收录什么」。",
        cta="给出你的推荐组合，以及不推荐的情况。",
        theme="default",
        sections=[
            Section("评选标准", "先说标准再看条目：用哪些维度打分，为什么是这些维度。"),
            Section("条目一：……", "三个字段固定：它解决什么 / 适合谁 / 明显不足。不足必须写。"),
            Section("条目二：……", "同上。条目之间保持同一结构，读者才能横向比较。"),
            Section("条目三：……", "同上。"),
            Section("怎么选：一张决策表", "给出「如果你是 A 类人 → 选 X」的决策路径。"),
        ],
        words="2500",
    ),
    "复盘": Template(
        name="复盘",
        display_name="复盘 / 数据总结",
        description="钩子 → 背景 → 做了什么 → 结果数据 → 关键判断 → 可复用方法 → 行动",
        hook="用一个最出乎意料的结果数字开场。",
        cta="告诉读者哪条经验可以直接搬走。",
        theme="default",
        sections=[
            Section("背景：当时的情况", "交代时间、目标、约束，让读者理解当时的限制。"),
            Section("我们做了什么", "按时间顺序列关键动作，不要写成流水账，只写影响结果的。"),
            Section("结果：数据说话", "给出前后对比数据，标明口径与时间。"),
            Section("关键判断：对了什么、错了什么", "至少写一条「事后看是错的」的判断，复盘才有可信度。"),
            Section("可复用的方法", "提炼 2–3 条能迁移到其他场景的经验。"),
        ],
        words="2000",
    ),
    "随笔": Template(
        name="随笔",
        display_name="随笔 / 经验分享",
        description="钩子 → 场景 → 转折 → 思考 → 落点",
        hook="从一个具体的瞬间写起，不要从概括写起。",
        cta="把落点留给读者，不要强行升华。",
        theme="serif",
        sections=[
            Section("场景", "一个具体的时刻：时间、地点、发生的事。"),
            Section("转折", "是什么改变了我原来的想法或做法。"),
            Section("思考", "这个转折让我意识到什么，尽量具体，少讲大道理。"),
            Section("落点", "回到开头的场景，或者给一个可操作的改变。"),
        ],
        words="1500",
    ),
    "通告": Template(
        name="通告",
        display_name="通告 / 活动通知",
        description="一句话说清 → 是什么 → 关键信息 → 怎么参与",
        hook="第一句就把「发生了什么、跟我有什么关系」说清楚。",
        cta="给读者明确的参与入口与截止时间。",
        theme="default",
        sections=[
            Section("这件事是什么", "一句话说清，不要铺垫。"),
            Section("关键信息", "时间、地点、对象、费用、名额：用列表写清。"),
            Section("怎么参与", "一步步列出参与流程，不要让人猜。"),
        ],
        words="800",
    ),
}


class TemplateError(ValueError):
    pass


def list_templates() -> List[Template]:
    return list(TEMPLATES.values())


def get_template(name: Optional[str]) -> Template:
    if not name:
        return TEMPLATES["观点"]
    if name in TEMPLATES:
        return TEMPLATES[name]
    # 允许用英文别名：tutorial / listicle / retro / essay / notice
    aliases = {"tutorial": "教程", "listicle": "盘点", "retro": "复盘",
               "essay": "随笔", "notice": "通告", "opinion": "观点"}
    if name in aliases:
        return TEMPLATES[aliases[name]]
    raise TemplateError("未知模板：%s（可用：%s）" % (name, "、".join(TEMPLATES)))


def render_article(template: Template, title: str, summary: str = "", author: str = "",
                   materials: Optional[List[str]] = None, theme: Optional[str] = None) -> str:
    from . import frontmatter as fm

    meta = {
        "title": title or "（在这里写标题）",
        "summary": summary or "（一句话摘要，≤120 字）",
        "theme": theme or template.theme,
        "template": template.name,
        "author": author,
        "materials": materials or [],
        "cover": "cover.png",
        "publish_confirm": False,
    }
    body_lines = ["# %s" % meta["title"], ""]
    body_lines.append("> %s" % template.hook)
    body_lines.append("")
    for index, section in enumerate(template.sections, start=1):
        body_lines.append("## %s" % section.title)
        body_lines.append("")
        body_lines.append("<!-- 提示：%s -->" % section.hint)
        body_lines.append("")
        body_lines.append("【待补】在这里写正文：%s" % section.hint)
        body_lines.append("")
    body_lines.append("## 结尾")
    body_lines.append("")
    body_lines.append("【待补】%s" % template.cta)
    body_lines.append("")
    return fm.render_document(meta, "\n".join(body_lines))


OUTLINE_SKELETON = """# 大纲：{title}

## 一句话结论
（读者读完能带走的那句话）

## 开头钩子
（具体场景 / 数据 / 反常识，不要空开头）

## 章节
{chapters}

## 结尾行动
（给读者一个具体动作）
"""


def render_outline(template: Template, title: str) -> str:
    chapters = []
    for index, section in enumerate(template.sections, start=1):
        chapters.append("### {}. {}\n- 论证：\n- 证据（素材库编号）：\n- 配图：\n".format(index, section.title))
    return OUTLINE_SKELETON.format(title=title, chapters="\n".join(chapters))
