#!/bin/bash
# IntruderCam 终极启动脚本 — 完全独立进程
PIDFILE="$HOME/Library/Logs/intruder_cam.pid"
SCRIPT="$HOME/intruder-cam/intruder_cam.py"
LOG="$HOME/Library/Logs/intruder_cam.log"

# 清除旧状态
rm -f "$PIDFILE"
pkill -f "intruder_cam" 2>/dev/null
pkill -f "ffmpeg.*avfoundation" 2>/dev/null
sleep 1

# 启动 — 所有 I/O 全丢到 /dev/null
# 子进程自己写日志文件
nohup python3 -u "$SCRIPT" >/dev/null 2>/dev/null &
CPID=$!
echo $CPID > "$PIDFILE"

# 等一会确认存活
sleep 8
if kill -0 $CPID 2>/dev/null; then
    echo "✅ IntruderCam started (PID: $CPID)"
    disown $CPID 2>/dev/null
else
    echo "❌ IntruderCam died immediately"
    tail -10 "$LOG"
    rm -f "$PIDFILE"
fi
