#!/bin/sh
set -eu

BASE=/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/hermes
HERMES_HOME="$BASE/data"
LOG="$BASE/telegram_bridge.log"
PIDFILE="$BASE/telegram_bridge.pid"
MAIN="$BASE/telegram_bridge_main.py"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "${PID:-}" ] && ps -p "$PID" >/dev/null 2>&1; then
    echo "telegram bridge OK (PID $PID)"
    exit 0
  fi
fi

env HERMES_HOME="$HERMES_HOME" python3 "$MAIN" >>"$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"

sleep 2

if ps -p "$PID" >/dev/null 2>&1; then
  echo "telegram bridge started (PID $PID)"
else
  echo "telegram bridge failed to start"
  exit 1
fi
