"""主题：加载、样式生成、排版规范校验。"""

import json
import os

import pytest

from wechat_sop import theme


def test_builtin_themes_load_and_lint_clean():
    for name in theme.list_themes():
        loaded = theme.load_theme(name)
        errors, _ = theme.lint_theme(loaded)
        assert errors == [], "%s 主题不合规：%s" % (name, errors)
        assert loaded["x"]["font_family"]


def test_load_unknown_theme_raises():
    with pytest.raises(theme.ThemeError):
        theme.load_theme("不存在的主题")


def _write_theme(tmp_path, data):
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _base_theme(**overrides):
    data = {
        "name": "custom",
        "primary_color": "#333333",
        "font_size": "16px",
        "line_height": "1.75",
        "styles": {"h1": {"font_size": "22px"}, "h2": {"font_size": "20px"}, "h3": {"font_size": "17px"}},
    }
    data.update(overrides)
    return data


def test_lint_rejects_small_font(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(font_size="12px")))
    errors, _ = theme.lint_theme(loaded)
    assert any("正文字号" in e for e in errors)


def test_lint_warns_on_unrecommended_font(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(font_size="14px")))
    errors, warnings = theme.lint_theme(loaded)
    assert not errors
    assert any("推荐区间" in w for w in warnings)


def test_lint_rejects_tight_line_height(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(line_height="1.3")))
    errors, _ = theme.lint_theme(loaded)
    assert any("行高" in e for e in errors)


def test_lint_rejects_reversed_heading_scale(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(
        styles={"h1": {"font_size": "18px"}, "h2": {"font_size": "20px"}, "h3": {"font_size": "17px"}})))
    errors, _ = theme.lint_theme(loaded)
    assert any("梯度倒置" in e for e in errors)


def test_lint_rejects_gradient(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(
        styles={"h1": {"font_size": "22px", "background": "linear-gradient(#fff, #000)"}})))
    errors, _ = theme.lint_theme(loaded)
    assert any("渐变" in e for e in errors)


def test_lint_rejects_bad_color(tmp_path):
    loaded = theme.load_theme(_write_theme(tmp_path, _base_theme(primary_color="green")))
    errors, _ = theme.lint_theme(loaded)
    assert any("颜色" in e for e in errors)


def test_merge_styles_order():
    css = theme.merge_styles({"a": "1"}, {"a": "2"}, {"b": "3"})
    assert css == "a:2;b:3"
