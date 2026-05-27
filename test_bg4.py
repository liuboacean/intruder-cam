#!/usr/bin/env python3
"""Full intruder cam test in background (write log via file)"""
import subprocess, select, time, os, threading

LOG = os.path.expanduser('~/Library/Logs/test_bg4.log')
def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('=== FULL TEST START ===')

# Display watcher thread
_watch_running = True
def poll_display():
    while _watch_running:
        try:
            r = subprocess.run(['pmset', '-g', 'assertions'], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if 'InternalPreventDisplaySleep' in line:
                    val = line.split()[-1].strip()
                    log(f'display: InternalPreventDisplaySleep={val}')
                    break
        except Exception as e:
            log(f'display error: {e}')
        time.sleep(2)

t = threading.Thread(target=poll_display, daemon=True)
t.start()
log('display watcher started')

time.sleep(3)
log('starting HID listener')

proc = subprocess.Popen(
    ['log', 'stream', '--predicate',
     '(process == "powerd" AND eventMessage contains[c] "hidActive:1")',
     '--style', 'compact', '--info'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
)
log(f'HID started PID={proc.pid} stdout={proc.stdout is not None}')

if proc.stdout:
    fd = proc.stdout.fileno()
    log(f'fd={fd} calling select...')
    deadline = time.time() + 45
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 60)
        if r:
            line = proc.stdout.readline()
            if not line:
                log('HID EOF')
                break
        else:
            log('HID select timeout')
            break

_watch_running = False
log('=== EXITING ===')
