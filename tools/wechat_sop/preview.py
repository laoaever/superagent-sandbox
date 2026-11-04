"""预览页：把渲染好的正文包进一个带「复制到公众号」按钮的外壳。

按钮只存在于外壳，不在被复制的 section 内，所以粘进公众号的是干净正文。
复制使用 `ClipboardItem` + `text/html`，不支持时回退到 Range → execCommand('copy')。
"""

from __future__ import annotations

import html
from typing import Dict, Any

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s · 公众号预览</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #f2f3f5;
    font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    color: #222;
  }
  .toolbar {
    position: sticky; top: 0; z-index: 10;
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px;
    background: rgba(255,255,255,0.96);
    border-bottom: 1px solid #e5e5e5;
  }
  .toolbar .meta { flex: 1 1 auto; min-width: 0; font-size: 13px; color: #666; }
  .toolbar .meta strong { color: #222; display: block; font-size: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .toolbar button {
    flex: 0 0 auto;
    border: none; border-radius: 6px; cursor: pointer;
    padding: 9px 16px; font-size: 14px; font-weight: 600;
    background: %(primary)s; color: #fff;
  }
  .toolbar button:active { opacity: 0.85; }
  .toolbar .status { font-size: 13px; color: #999; min-width: 88px; text-align: right; }
  .phone {
    max-width: 420px; margin: 20px auto 60px; padding: 20px 16px 40px;
    background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }
  .article { font-size: 16px; }
  .hint { max-width: 420px; margin: 0 auto; font-size: 12px; color: #999; padding: 0 16px 16px; text-align: center; }
  @media print { .toolbar, .hint { display: none; } .phone { box-shadow: none; margin: 0; } body { background: #fff; } }
</style>
</head>
<body>
<div class="toolbar">
  <div class="meta"><strong>%(title)s</strong><span>%(subtitle)s</span></div>
  <span class="status" id="status"></span>
  <button id="copy" type="button">复制到公众号</button>
</div>
<div class="hint">点「复制到公众号」后，到公众号后台新建图文，在正文区粘贴即可。发布仍由人工在后台确认。</div>
<div class="phone">
<div class="article" id="article">%(body)s</div>
</div>
<script>
(function () {
  var status = document.getElementById('status');
  var article = document.getElementById('article');
  function flash(text, color) {
    status.textContent = text;
    status.style.color = color || '#999';
    setTimeout(function () { status.textContent = ''; status.style.color = '#999'; }, 2400);
  }
  function legacyCopy() {
    var range = document.createRange();
    range.selectNodeContents(article);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    selection.removeAllRanges();
    return ok;
  }
  document.getElementById('copy').addEventListener('click', function () {
    var html = article.innerHTML;
    if (navigator.clipboard && window.ClipboardItem) {
      var item = new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([article.innerText], { type: 'text/plain' })
      });
      navigator.clipboard.write([item]).then(function () {
        flash('已复制 ✓', '#07c160');
      }).catch(function () {
        flash(legacyCopy() ? '已复制 ✓' : '复制失败，请手动全选', '#ff4d4f');
      });
      return;
    }
    flash(legacyCopy() ? '已复制 ✓' : '复制失败，请手动全选', '#ff4d4f');
  });
})();
</script>
</body>
</html>
"""


def wrap_preview(body: str, meta: Dict[str, Any], theme: Dict[str, Any], *,
                 footnotes: int = 0, word_count: int = 0) -> str:
    title = html.escape(str(meta.get("title") or "未命名文章"))
    subtitle_parts = []
    if meta.get("author"):
        subtitle_parts.append(html.escape(str(meta["author"])))
    subtitle_parts.append("主题 %s" % html.escape(str(theme.get("name", "default"))))
    if word_count:
        subtitle_parts.append("%d 字" % word_count)
    subtitle_parts.append("外链脚注 %d 条" % footnotes)
    return _TEMPLATE % {
        "title": title,
        "subtitle": html.escape(" · ".join(subtitle_parts)),
        "body": body,
        "primary": theme.get("primary_color", "#07c160"),
    }
