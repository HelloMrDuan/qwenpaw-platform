#!/bin/sh
set -eu

BASE=/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes
DIR="$BASE/wecom-node"
MAIN="$DIR/wecom_bridge.mjs"
LOG="$BASE/wecom_bridge.log"
PIDFILE="$BASE/wecom_bridge.pid"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && [ -r "/proc/$PID/cmdline" ]; then
    CMD="$(tr '\0' ' ' < "/proc/$PID/cmdline")"
    case "$CMD" in
      *wecom_bridge.mjs*)
        echo "wecom bridge OK (PID $PID)"
        exit 0
        ;;
    esac
  fi
fi

nohup node "$MAIN" >>"$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
sleep 3

if [ -r "/proc/$PID/cmdline" ]; then
  CMD="$(tr '\0' ' ' < "/proc/$PID/cmdline")"
  case "$CMD" in
    *wecom_bridge.mjs*)
      echo "wecom bridge started (PID $PID)"
      exit 0
      ;;
  esac
fi

echo "wecom bridge failed to start"
tail -n 50 "$LOG" 2>/dev/null || true
exit 1
