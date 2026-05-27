#!/bin/bash
# IntruderCam 后台启动脚本（独立进程，不依赖终端会话）
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/Library/Logs/intruder_cam.log"
PIDFILE="$HOME/Library/Logs/intruder_cam.pid"
cd "$DIR" || exit 1

# 杀掉旧进程
if [ -f "$PIDFILE" ]; then
    OLPID=$(cat "$PIDFILE")
    kill "$OLPID" 2>/dev/null
    sleep 1
fi

# 后台启动，完全脱离终端
nohup python3 -u "$DIR/intruder_cam.py" >> "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
echo "IntruderCam started (PID: $PID)"
