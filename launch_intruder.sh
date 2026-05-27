#!/bin/bash
# 启动 IntruderCam（独立进程，完全脱离终端）
PIDFILE="$HOME/Library/Logs/intruder_cam.pid"
SCRIPT="$HOME/intruder-cam/intruder_cam.py"
LOG="$HOME/Library/Logs/intruder_cam.log"

# 检查是否已运行
if [ -f "$PIDFILE" ]; then
    OLDPID=$(cat "$PIDFILE")
    if kill -0 "$OLDPID" 2>/dev/null; then
        echo "IntruderCam already running (PID: $OLDPID)"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

# 杀掉残留进程
pkill -f "intruder_cam" 2>/dev/null
pkill -f "ffmpeg.*avfoundation" 2>/dev/null
rm -f ~/Library/Logs/intruder_cam.lock
sleep 1

# 后台启动 Python 脚本，不 fork
cd "$HOME/intruder-cam"
nohup python3 -u intruder_cam.py >> "$LOG" 2>&1 &
CHILD_PID=$!
echo $CHILD_PID > "$PIDFILE"

# 等待启动确认
sleep 4
if kill -0 $CHILD_PID 2>/dev/null; then
    echo "✅ IntruderCam started (PID: $CHILD_PID)"
else
    echo "❌ IntruderCam failed to start"
    tail -5 "$LOG"
fi
