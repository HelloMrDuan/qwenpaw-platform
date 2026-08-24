#!/bin/sh
set -e

BASE="/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/wecom-kf"

echo "===== STOP OLD GATEWAYS (341-344) ====="
for v in 341 342 343 344; do
    pids=$(pgrep -f "wecom_kf_gateway_v${v}\.py" || true)
    if [ -n "$pids" ]; then
        echo "Stopping V$v PIDs: $pids"
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
    else
        echo "V$v already stopped"
    fi
done

echo
echo "===== WAIT FOR EXIT ====="
sleep 3

echo
echo "===== VERIFY ONLY V345 RUNNING ====="
ps -ef | grep '[w]ecom_kf_gateway_v[0-9][0-9][0-9]\.py' || true

echo
echo "===== V345 HEALTH ====="
curl -sS -o /dev/null -w 'V345_LOCAL_HEALTHZ=%{http_code}\n' --max-time 5 http://127.0.0.1:8798/healthz || true

echo
echo "===== PUBLIC HEALTH ====="
curl -sS -o /dev/null -w 'V345_PUBLIC_HEALTHZ=%{http_code}\n' --max-time 10 https://qwenpaw-sbs-prod-dj2gm.tail7c303e.ts.net/healthz || true

echo
echo "===== FINAL HEALTHCHECK ====="
"$BASE/healthcheck_v345.sh" || true
