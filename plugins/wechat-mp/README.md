# WeChat MP Historical Gateway

状态：`RECOVERED_SOURCE_ONLY`。该目录保存微信公众号 Gateway 历史源码，尚未接入 Runtime。

## 来源与目录纠正

逻辑来源名称为 `channel-runtime-recovery-export/wechat-mp/`，ZIP 中实际路径为 `channel-runtime-recovery-export/wechat/`。

迁移文件：

- `recovered/wechat_mp_gateway.py`：历史运行版本，默认端口 8799；
- `recovered/wechat_mp_gateway_v2.py`：V2 候选，默认端口 8800。

两个版本均原样保留，不在本阶段判断生产版本或合并实现。

## 原运行方式

恢复报告记录：

```text
python3 wechat_mp_gateway.py
```

恢复包没有独立守护/启动脚本。

## 依赖

- Python 标准库 HTTP Server、XML、hashlib、subprocess、urllib、JSON；
- 外部 QwenPaw CLI；
- V2 的外部 QwenPaw API。

## 配置键与缺失项

识别出的键包括 `TOKEN`、`HOST`、`PORT`、`QWENPAW`、`QWENPAW_API` 和 timeout。

缺失：

- `mp-secret.env` 的脱敏模板；
- 历史启动/守护脚本；
- 外部 QwenPaw 调用环境说明；
- 生产版本确认记录。

真实 secret 和运行状态没有迁移。
