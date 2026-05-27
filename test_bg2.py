#!/usr/bin/env python3
"""Minimal background test - check what works"""
import subprocess, time, os, sys

LOG = os.path.expanduser('~/Library/Logs/test_bg2.log')

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.0f}: {msg}\n')

log('=== start ===')

# Test 1: simple subprocess
try:
    r = subprocess.run(['echo', 'hello'], capture_output=True, text=True, timeout=5)
    log(f'test1 OK: {r.stdout.strip()}')
except Exception as e:
    log(f'test1 FAIL: {e}')

# Test 2: Popen with log
try:
    p = subprocess.Popen(
        ['log', 'stream', '--predicate', 'process == "powerd"', '--style', 'compact'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
    )
    log(f'test2 OK: pid={p.pid}')
    p.kill()
except Exception as e:
    log(f'test2 FAIL: {e}')

# Test 3: just osascript
try:
    r = subprocess.run(['osascript', '-e', 'return "ok"'], capture_output=True, text=True, timeout=5)
    log(f'test3 OK: {r.stdout.strip()}')
except Exception as e:
    log(f'test3 FAIL: {e}')

log('=== done ===')
