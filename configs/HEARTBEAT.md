实际使用 Shell 依次执行以下三个脚本：

/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/tailscale/healthcheck.sh

/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/wecom-kf/healthcheck_v345.sh

/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes/start_bridge.sh

要求：
1. 只执行以上三个脚本，不做其他操作。
2. 不重新下载、不重新配置、不重新登录。
3. 不执行 kill、pkill。
4. 三个脚本均成功时只回复 HEARTBEAT_OK。
5. 任一失败时只返回对应原始错误。
