#!/usr/bin/env python3
"""Background test for intruder cam"""
import subprocess, select, time, os, sys

LOG = os.path.expanduser('~/Library/Logs/test_bg.log')

def log(msg):
    with open(LOG, 'w') as f:
        f.write(f'{time.time():.0f}: {msg}\n')
    sys.stdout.write(f'{msg}\n')
    sys.stdout.flush()

log('=== starting ===')

proc = subprocess.Popen(
    ['log', 'stream', '--predicate',
     '(process == "powerd" AND eventMessage contains[c] "hidActive:1")',
     '--style', 'compact', '--info'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, bufsize=1,
)
log(f'log stream started PID={proc.pid}')

# Use select to wait for data
fd = proc.stdout.fileno()
for i in range(30):
    r, _, _ = select.select([fd], [], [], 1)
    if r:
        line = proc.stdout.readline()
        if not line:
            log(f'EOF at {i}s')
            break
        log(f'data: {line.strip()[:60]}')
    if proc.poll() is not None:
        log(f'log stream died at {i}s rc={proc.poll()}')
        break
    if i % 5 == 0:
        log(f'alive at {i}s')

log('=== exiting ===')
