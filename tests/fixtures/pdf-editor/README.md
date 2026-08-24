# PDF Editor 脱敏真实文档 Fixture 目录

该目录只定义 Production Release 真实文档验收的分类和存放规范，不包含真实业务文件。

```text
pdf-editor/
├── simple/    # 普通文本 PDF
├── font/      # 复杂字体、嵌入字体和中文字体 PDF
├── image/     # 含图片或用于图片替换的 PDF
├── scanned/   # 扫描型 PDF
└── complex/   # 脱敏企业盖章、多页表格等复杂 PDF
```

使用要求：

- 只允许放入已授权且完成不可逆脱敏的测试副本。
- 企业盖章样本只能使用合成章、测试章或无效脱敏章。
- 不得提交真实 PDF、图片、渲染结果、客户标识或业务日志。
- 本地验收记录遵循 `skills/pdf-editor/tests/REAL_DOCUMENT_TESTING.md`。
- 如需共享测试样本，应使用经批准的受控制品存储，并在记录中仅引用 Artifact ID 和 SHA-256。

各子目录中的 `.gitkeep` 仅用于保留目录结构。
