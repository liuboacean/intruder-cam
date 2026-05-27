#!/usr/bin/env python3
"""Test log stream with select in background"""
import subprocess, select, time, os

LOG = os.path.expanduser('~/Library/Logs/test_bg3.log')
def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('=== start ===')

proc = subprocess.Popen(
    ['log', 'stream', '--predicate',
     '(process == "powerd" AND eventMessage contains[c] "hidActive:1")',
     '--style', 'compact', '--info'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
)
log(f'Popen OK pid={proc.pid} stdout={proc.stdout is not None}')

if proc.stdout:
    fd = proc.stdout.fileno()
    log(f'fileno={fd}')
    for i in range(15):
        r, _, _ = select.select([fd], [], [], 1)
        if r:
            line = proc.stdout.readline()
            if not line:
                log(f'EOF at {i}s')
                break
            log(f'data[{i}s]: {line.strip()[:60]}')
        else:
            # No data but check if process alive
            if proc.poll() is not None:
                log(f'log stream died at {i}s rc={proc.poll()}')
                break
            elif i % 5 == 0:
                log(f'alive no data at {i}s')

log('=== exiting ===')
