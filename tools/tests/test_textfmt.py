"""格式修复：标点、空格、加粗位置，以及保护区域不被修改。"""

from wechat_sop import textfmt as tf

FW = {name: chr(code) for name, code in {
    "comma": 0xFF0C, "colon": 0xFF1A, "semi": 0xFF1B, "qmark": 0xFF1F,
    "excl": 0xFF01, "period": 0x3002, "lparen": 0xFF08, "rparen": 0xFF09,
}.items()}


def test_half_width_comma_after_cjk():
    assert tf.fix_punctuation("这是中文,后面还有") == "这是中文%s后面还有" % FW["comma"]


def test_half_width_parens_around_cjk():
    assert tf.fix_punctuation("中文(注释)结束") == "中文%s注释%s结束" % (FW["lparen"], FW["rparen"])


def test_ascii_period_after_cjk_becomes_ideographic():
    assert tf.fix_punctuation("中文句号.") == "中文句号%s" % FW["period"]


def test_code_is_protected():
    source = "文本`a,b(c)`和```py\nx=1,y=2\n```\n"
    assert tf.fix_punctuation(source) == source


def test_links_and_urls_protected():
    source = "参考[说明,含逗号](https://example.com/a,b?x=1,2)与 https://a.b/c,d 结束"
    assert tf.fix_punctuation(source) == source


def test_cjk_spacing_between_latin():
    assert tf.fix_cjk_spacing("用word排版") == "用 word 排版"
    assert tf.fix_cjk_spacing("支持2026年") == "支持 2026 年"


def test_cjk_spacing_not_inside_code_or_links():
    source = "看`foo中文`和[bar中文](https://x.y/z)"
    assert tf.fix_cjk_spacing(source) == source


def test_bold_punctuation_moved_out():
    assert tf.fix_bold_punctuation("**重点，**后面") == "**重点**，后面"
    assert tf.fix_bold_punctuation("*强调。*结束") == "*强调*。结束"


def test_bold_punctuation_not_in_fenced_code():
    source = "```\n**a，**\n```\n"
    assert tf.fix_bold_punctuation(source) == source


def test_find_half_width_reports_issues():
    issues = tf.find_half_width_punctuation("中文,后面")
    assert issues


def test_find_half_width_ignores_code():
    assert tf.find_half_width_punctuation("```\n中文,后面\n```\n") == []


def test_find_missing_spacing_reports_issues():
    assert tf.find_missing_spacing("用word排版")
    assert tf.find_missing_spacing("已经 加了 空格") == []


def test_format_text_is_idempotent():
    source = "**重点，**后面还有中文(括号)和word粘连,再试一次。\n"
    once = tf.format_text(source)
    assert tf.format_text(once) == once
