#!/usr/bin/env python3
"""Test: thread + log stream + 60s select in background"""
import subprocess, select, time, os, threading

LOG = os.path.expanduser('~/Library/Logs/test_bg6.log')
def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('=== START ===')

# Thread that polls pmset
def display_thread():
    for i in range(30):
        r = subprocess.run(['pmset', '-g', 'assertions'], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if 'InternalPreventDisplaySleep' in line:
                log(f'display[{i}]: {line.strip()}')
                break
        time.sleep(5)

t = threading.Thread(target=display_thread, daemon=True)
t.start()
log('thread started')

time.sleep(2)
log('starting log stream')

proc = subprocess.Popen(
    ['log', 'stream', '--predicate',
     '(process == "powerd" AND eventMessage contains[c] "hidActive:1")',
     '--style', 'compact', '--info'],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
)

if proc.stdout:
    fd = proc.stdout.fileno()
    log(f'selecting with 60s timeout...')
    r, _, _ = select.select([fd], [], [], 60)
    log(f'select returned (r={bool(r)})')

log('=== DONE ===')
