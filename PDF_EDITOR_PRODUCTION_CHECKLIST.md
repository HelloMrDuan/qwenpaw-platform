# PDF Editor V1.2 Production Checklist

Release 负责人必须为每个检查项附上可追溯证据。只有全部必选项完成且无未关闭 P0/P1 问题时，才可批准 Production Release。

## 上线前检查

- [ ] 自动测试：Core Contract、PDF Contract、17 项标准回归和 V1.1 兼容回归全部通过，并记录命令、环境与结果。
- [ ] 视觉测试：逐页检查生成式验收输出以及真实业务样本的目标/非目标区域，保存脱敏结果和评审结论。
- [ ] 中文字体测试：确认中文页码字形预检、保存后文本和真实渲染墨迹通过；缺字场景正确失败。
- [ ] 图片几何测试：确认替换前后 bbox、transform、旋转和图片数量符合容差，旧图无残留且非目标区域稳定。
- [ ] 真实业务测试：按照 `skills/pdf-editor/tests/REAL_DOCUMENT_TESTING.md` 覆盖六类样本，记录输入/输出哈希、操作、视觉结果和问题。
- [ ] Skill 上传测试：在 Cloud staging 上传最终 Skill ZIP，验证发现、加载、Contract 调用、StreamEvent、Artifact 下载及失败回滚。

## 制品与边界确认

- [ ] Skill ZIP 与 Delivery ZIP 均可解压，CRC 校验通过且不包含 `__pycache__`、`.pyc` 或敏感凭据。
- [ ] SHA-256 与 Release 记录一致。
- [ ] Release 文档明确记录 V1.2 限制及 V1.1 回滚方式。
- [ ] 变更范围不包含 QwenPaw Runtime、Agent 或 Channel。

## 审批记录

| 字段 | 记录 |
| --- | --- |
| Release 版本 | V1.2 |
| Skill ZIP SHA-256 |  |
| Delivery ZIP SHA-256 |  |
| 自动测试证据 |  |
| 真实业务验收记录 |  |
| Cloud staging 记录 |  |
| 未关闭问题 |  |
| 发布结论 | APPROVED / REJECTED / BLOCKED |
| 发布负责人 |  |
| 审批日期 |  |
