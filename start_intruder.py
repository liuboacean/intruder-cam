#!/usr/bin/env python3
"""启动 IntruderCam — 先彻底杀光旧进程，再启动新实例"""
import subprocess, os, sys, time, signal

PIDFILE = os.path.expanduser('~/Library/Logs/intruder_cam.pid')
SCRIPT = os.path.expanduser('~/intruder-cam/intruder_cam.py')

# Step 1: 杀光所有 intruder_cam.py 进程
subprocess.run(
    ['pkill', '-9', '-f', 'intruder_cam\\.py'],
    capture_output=True, timeout=5,
)
subprocess.run(
    ['pkill', '-9', '-f', 'ffmpeg.*avfoundation'],
    capture_output=True, timeout=5,
)
time.sleep(2)  # 等进程彻底退出

# Step 2: 清除旧锁/PID
for f in ['intruder_cam.pid', 'intruder_cam.lock']:
    p = os.path.expanduser(f'~/Library/Logs/{f}')
    if os.path.exists(p):
        os.remove(p)

# Step 3: 启动（完全独立进程组）
proc = subprocess.Popen(
    [sys.executable, '-u', SCRIPT],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
    close_fds=True,
)

child_pid = proc.pid
with open(PIDFILE, 'w') as f:
    f.write(str(child_pid))

# 确认存活
time.sleep(6)
try:
    os.kill(child_pid, 0)
    print(f"✅ IntruderCam 启动成功 (PID: {child_pid})")
    print(f"📁 照片: ~/Pictures/IntruderCam/")
except OSError:
    print(f"❌ 启动失败 (PID {child_pid} died)")
    if os.path.exists(os.path.expanduser('~/Library/Logs/intruder_cam.log')):
        with open(os.path.expanduser('~/Library/Logs/intruder_cam.log')) as f:
            print(f.read()[-500:])
