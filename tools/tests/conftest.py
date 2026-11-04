"""pytest fixture：最小 PNG 生成、临时文章目录、渲染 helper。"""

import os
import struct
import sys
import zlib

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(TESTS_DIR)
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
REPO_ROOT = os.path.dirname(TOOLS_DIR)

if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def _make_png(path, width=800, height=450, color=(7, 193, 96)):
    """不依赖 Pillow，生成一张纯色 PNG。"""
    raw = b""
    row = bytes(color) * width
    for _ in range(height):
        raw += b"\x00" + row

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return path


@pytest.fixture
def make_png():
    return _make_png


@pytest.fixture
def make_article(tmp_path):
    """构造一个文章目录，返回 (article_path, dir)。

    参数通过 keyword 传入：frontmatter 字段、body、图片尺寸等。
    """

    def _make(body="", images=None, cover=True, meta=None, dir_name="2026-11-03-demo"):
        article_dir = tmp_path / dir_name
        (article_dir / "images").mkdir(parents=True, exist_ok=True)
        base_meta = {
            "title": "测试文章标题",
            "summary": "这是一句话摘要，用来测试发布前检查。",
            "theme": "default",
            "template": "观点",
            "author": "测试作者",
            "materials": ["M2026110301"],
            "cover": "cover.png",
            "publish_confirm": False,
        }
        base_meta.update(meta or {})
        for name, size in (images or {}).items():
            _make_png(str(article_dir / "images" / name), *size)
        if cover:
            _make_png(str(article_dir / "cover.png"), 900, 383)
        lines = ["---"]
        for key, value in base_meta.items():
            if isinstance(value, list):
                lines.append("%s: [%s]" % (key, ", ".join(value)))
            elif isinstance(value, bool):
                lines.append("%s: %s" % (key, "true" if value else "false"))
            else:
                lines.append('%s: "%s"' % (key, value))
        lines.append("---")
        text = "\n".join(lines) + "\n\n" + body
        path = article_dir / "article.md"
        path.write_text(text, encoding="utf-8")
        return str(path), str(article_dir)

    return _make


@pytest.fixture
def sample_body():
    return """# 公众号 HTML 渲染元素覆盖样例

这一段包含 **加粗**、*斜体*、~~删除线~~、`inline code`，以及一个 [外部链接](https://example.com/wechat-style) 和一个 [公众号内链](https://mp.weixin.qq.com/s/demo)。

## 列表

- 无序项一
- 无序项二
  - 嵌套项 A
- 无序项三

1. 有序项一
2. 有序项二

## 引用与代码

> 这是一段引用，说明一句话观点。

```python
def greet(name):
    # 打印问候
    print("Hello, " + name)
    return 42
```

## 图片与表格

![耗时对比示意图](images/chart.png)

| 方式 | 耗时 | 备注 |
|:---|---:|:---|
| 手动排版 | 32 分钟 | 每篇都要重来 |
| 脚本排版 | 3 分钟 | 一次配置 |

---

### 三级标题

最后一段，建议你先按文档准备一篇样例跑通流程。
"""
