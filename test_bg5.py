#!/usr/bin/env python3
"""Test 60-second select in background"""
import select, time, os

LOG = os.path.expanduser('~/Library/Logs/test_bg5.log')
def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('starting 60s select')
try:
    r, w, x = select.select([], [], [], 60)
    log(f'select returned: r={r} w={w} x={x}')
except Exception as e:
    log(f'select error: {e}')
log('done')
