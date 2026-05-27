#!/usr/bin/env python3
"""MINIMAL background test — does time.time() + while loop work?"""
import time, os, sys, subprocess

LOG = os.path.expanduser('~/Library/Logs/test_final.log')
def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('=== START ===')

# Simulate what intruder_cam does before the HID loop
class MockMonitor:
    def __init__(self):
        self._running = True
        self.last_hid_time = 0.0

m = MockMonitor()
deadline = time.time() + 60
count = 0

while time.time() < deadline and m._running:
    count += 1
    time.sleep(1)
    if count % 10 == 0:
        log(f'loop iteration {count}')
    if count > 120:
        break

log(f'=== DONE after {count} iterations ===')
