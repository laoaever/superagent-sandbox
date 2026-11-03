"""公众号写作流程脚本包（零三方依赖，Python 3.8+）。

模块划分：
- frontmatter: 解析/序列化 Markdown YAML frontmatter（用仓库自带的极简 parser，不依赖 PyYAML）
- markdown:    Markdown → 结构块（标题/段落/列表/引用/代码/表格/图片/分割线）
- theme:       主题加载、CSS 声明生成、主题规范校验
- render:      结构块 → 公众号可粘贴 HTML（section + 内联 style + span leaf）
- doc:         文章目录、frontmatter 字段读取
- topics:      选题库 / 素材库
- templates:   写作模板
- check:       发布前检查
- textfmt:     中文标点/中英文空格等格式修复
- cli:         命令行入口
"""

__version__ = "1.0.0"
