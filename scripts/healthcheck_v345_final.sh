#!/bin/sh

BASE="/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/wecom-kf"
V345="$BASE/wecom_kf_gateway_v345.py"
LOG="$BASE/gateway-v345-runtime.log"
HEALTH_URL="http://127.0.0.1:8798/healthz"

# 1. 服务健康：正常结束
if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
    exit 0
fi

# 2. 进程仍存在但健康检查失败：
#    不 kill、不重启，只向 Heartbeat 报错
if pgrep -f '[w]ecom_kf_gateway_v345.py' >/dev/null 2>&1; then
    echo "V345 unhealthy: process exists but /healthz is not responding" >&2
    exit 1
fi

# 3. 进程不存在：只拉起 V345
echo "V345 process missing: starting V345" >&2
nohup python3 "$V345" >> "$LOG" 2>&1 &

# 4. 给 V345 一点启动时间，并验证是否真正恢复
i=0
while [ "$i" -lt 15 ]; do
    if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
        exit 0
    fi

    sleep 1
    i=$((i + 1))
done

echo "V345 start attempted but /healthz did not become healthy within 15s" >&2
exit 1
