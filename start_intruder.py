#!/usr/bin/env python3
"""IntruderCam startup script - checks PID file, starts if not running."""
import os, sys, subprocess, time

PID_FILE = os.path.expanduser("~/Library/Logs/intruder_cam.pid")
LOG_FILE = os.path.expanduser("~/Library/Logs/intruder_cam.log")
SCRIPT = os.path.expanduser("~/intruder-cam/intruder_cam.py")
VENV_PYTHON = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python3")

def is_running():
    """Check if process is running via PID file + kill -0."""
    if not os.path.exists(PID_FILE):
        return False
    with open(PID_FILE) as f:
        pid_str = f.read().strip()
    if not pid_str.isdigit():
        return False
    pid = int(pid_str)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def start():
    """Launch IntruderCam in background."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] IntruderCam not running. Starting...")
    # Raise file descriptor limit — IntruderCam uses many sockets/FDs
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft = min(2048, hard if hard > 0 else 2048)
        if soft < new_soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ulimit NOFILE raised: {soft} → {new_soft}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] WARNING: couldn't raise ulimit: {e}")
    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    proc = subprocess.Popen(
        [python, SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Started PID {proc.pid}")
    return proc.pid

if __name__ == "__main__":
    if is_running():
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] IntruderCam already running.")
        sys.exit(0)
    pid = start()
    time.sleep(2)
    if is_running():
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Confirmed running on PID {pid}")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: Process failed to start!")
        sys.exit(1)
