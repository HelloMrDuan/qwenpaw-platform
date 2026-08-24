# PDF Editor V1.2 Production Release

## 版本信息

- Release：V1.2
- Skill version：1.2.0
- 类型：QwenPaw Extension Skill
- Runtime 边界：本 Release 不包含、不替换也不修改 QwenPaw Runtime、Agent 或 Channel。

## 支持能力与验收场景

V1.2 已覆盖以下 17 项标准回归场景：

1. PDF 类型识别；
2. 全文文本替换；
3. 指定第 N 次文本替换；
4. 文本删除；
5. 页面删除；
6. 页面插入；
7. 页面重排；
8. 页面旋转；
9. PDF 拆分；
10. PDF 合并；
11. 页面提取；
12. 添加文本；
13. 添加图片；
14. 替换图片；
15. 添加水印；
16. 添加中文页码；
17. 保存后综合视觉验收。

同时提供 Skill Contract 接入、标准 StreamEvent、Artifact 输出，以及执行、重开、语义、视觉、几何/布局五层验证结果。

## 已知限制

- V1.2 不包含 OCR 识别、OCR 文本层生成或扫描件内容重绘。
- 扫描型 PDF 只能执行不依赖文本识别的适用操作；不得将扫描件分类成功解释为 OCR 编辑能力。
- 自动生成 fixture、P0 视觉测试和兼容回归已经通过，但不能替代真实业务文档验收。
- 复杂字体、企业盖章、多页表格等场景必须按照 `tests/REAL_DOCUMENT_TESTING.md` 完成受控验收后，才能声明 Production Real-Document PASS。
- 字体不可用或目标字符缺字时，页码操作会明确失败，不生成伪成功文件。

## Production 发布门禁

发布前必须完成仓库根目录 `PDF_EDITOR_PRODUCTION_CHECKLIST.md`。其中“真实业务测试”和“Skill 上传测试”是 Production Release 必需证据，不得以本地自动测试代替。

## 发布内容

- Skill 包：`dist/pdf-editor-v1.2/pdf-editor-production-v1.2-final-skill.zip`
- 完整交付包：`dist/pdf-editor-v1.2/qwenpaw-pdf-editor-production-v1.2-final-delivery.zip`
- 校验文件：`dist/pdf-editor-v1.2/SHA256SUMS.txt`

上传前必须重新计算 SHA-256，并与对应 Release 记录保持一致。

## 回滚到 V1.1

1. 停止继续分发或上传 V1.2 Skill 包。
2. 保留失败请求、Artifact ID、事件日志和输出哈希；不得保留未脱敏业务原件。
3. 在 QwenPaw Cloud/目标环境中停用 V1.2，并恢复此前已验证的 V1.1 Skill 包或对应工作区备份。
4. 确认 Skill 配置、发现路径和调用入口均指向 V1.1，不修改 Runtime、Agent 或 Channel 实现。
5. 使用 V1.1 基线用例执行冒烟测试，确认文本替换、页面操作和输出 Artifact 可用。
6. 记录回滚原因、执行人、时间、V1.1 包哈希和验证结果。

回滚不应通过重写 Git 历史或强制推送实现。代码级回退应基于已发布标签/提交创建显式 revert 或修复提交，具体方式由发布负责人审批。
