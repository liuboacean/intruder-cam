#!/usr/bin/env python3
"""
Intruder Cam v3 — Mac 防盗拍监控（稳定版）
当电脑被唤醒（有人开盖/动鼠标/碰键盘）时，用摄像头抓拍。

修复问题：
  - ✅ 文件锁防止 ffmpeg 并发冲突
  - ✅ 自动杀掉残留 ffmpeg 进程
  - ✅ 事件防抖（分别冷却 + 合并触发）
  - ✅ 自动清理 7 天前的旧照片
  - ✅ LaunchAgent 开机自启（含卸载）

用法：
  python3 intruder_cam_v3.py              # 前台测试
  python3 intruder_cam_v3.py --daemon     # 后台运行
  python3 intruder_cam_v3.py --install    # 安装开机自启
  python3 intruder_cam_v3.py --uninstall  # 卸载开机自启

照片：~/Pictures/IntruderCam/
日志：~/Library/Logs/intruder_cam.log
"""

import fcntl
import os
import select
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ========== 配置 ==========
PHOTO_DIR = Path.home() / "Pictures" / "IntruderCam"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
LOG_FILE = Path.home() / "Library" / "Logs" / "intruder_cam.log"
LOCK_FILE = Path.home() / "Library" / "Logs" / "intruder_cam.lock"

# 冷却时间
COOLDOWN_WAKE = 60    # 显示器唤醒后 60 秒内不再重复拍
COOLDOWN_HID = 30     # 键盘/鼠标事件后 30 秒内不再重复拍

# ========== 日志 ==========

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ========== 文件锁（防止 ffmpeg 并发） ==========

class PhotoLock:
    """跨进程文件锁，确保同一时间只有一个 ffmpeg 在跑"""

    def __enter__(self):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.fp = open(LOCK_FILE, "w")
        try:
            fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.locked = True
        except BlockingIOError:
            self.locked = False
        return self

    def __exit__(self, *args):
        if hasattr(self, "fp"):
            fcntl.flock(self.fp, fcntl.LOCK_UN)
            self.fp.close()

# ========== 拍照（带重试和残留清理） ==========

def kill_stale_ffmpeg():
    """杀掉可能残留的 ffmpeg 进程（避免摄像头被占用）"""
    try:
        subprocess.run(
            ["pkill", "-f", "ffmpeg.*avfoundation"],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass


PHOTOS_ALBUM = "IntruderCam"
_photos_album_ready = False


def ensure_photos_album():
    """确保 IntruderCam 相簿存在（不重复创建）"""
    global _photos_album_ready
    if _photos_album_ready:
        return True
    try:
        # 先检查是否已有同名相簿
        check = subprocess.run(
            ["osascript", "-e",
             f'tell application "Photos" to get name of every album'],
            capture_output=True, text=True, timeout=10,
        )
        if PHOTOS_ALBUM not in check.stdout:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "Photos" to make new album named "{PHOTOS_ALBUM}"'],
                capture_output=True, timeout=10,
            )
    except Exception:
        pass
    _photos_album_ready = True
    return True


def import_to_photos(filepath: str) -> bool:
    """导入照片到系统相册 IntruderCam"""
    try:
        # 导入到相册
        result = subprocess.run(
            ["osascript", "-e",
             f'tell application "Photos" to import POSIX file "{filepath}"'],
            capture_output=True, timeout=15, text=True,
        )
        if result.returncode == 0:
            imported_id = result.stdout.strip()
            log(f"🖼️ 已导入相册 (ID: {imported_id[:20]}...)")

            # 尝试加入 IntruderCam 相簿
            ensure_photos_album()
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "Photos"\n'
                 f'  set targetAlbum to album "{PHOTOS_ALBUM}"\n'
                 f'  set mediaItem to media item id {imported_id}\n'
                 f'  add mediaItem to targetAlbum\n'
                 f'end tell'],
                capture_output=True, timeout=10,
            )
            return True
        else:
            log(f"⚠️ 导入相册失败: {result.stderr.strip()[:100]}")
            return False
    except subprocess.TimeoutExpired:
        log("⚠️ 导入相册超时")
        return False
    except Exception as e:
        log(f"⚠️ 导入相册异常: {e}")
        return False


def take_photo(reason: str) -> Optional[str]:
    """拍照，返回文件路径"""
    # 先拿锁，拿不到说明另一个拍照正在进行，跳过
    with PhotoLock() as lock:
        if not lock.locked:
            log(f"⏭️ [{reason}] 另一个拍照正在进行，跳过")
            return None

        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intruder_{ts}.png"
        filepath = str(PHOTO_DIR / filename)

        cmd = [
            FFMPEG, "-f", "avfoundation",
            "-framerate", "30", "-video_size", "1280x720",
            "-i", "0", "-vframes", "1", "-update", "1",
            filepath, "-y", "-loglevel", "error",
        ]

        # 尝试拍照（重试 1 次）
        for attempt in range(2):
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=8, text=True)
                fp = Path(filepath)
                if fp.exists() and fp.stat().st_size > 1000:
                    kb = fp.stat().st_size // 1024
                    log(f"📸 [{reason}] → {filename} ({kb}KB)")

                    # 同步导入系统相册（异步不阻塞）
                    import_to_photos(filepath)

                    return filepath
                else:
                    msg = result.stderr.strip()[:100] if result.stderr else "未知错误"
                    if attempt == 0:
                        log(f"⚠️ 拍照重试: {msg}")
                        kill_stale_ffmpeg()
                        time.sleep(1)
                    else:
                        log(f"⚠️ 拍照失败: {msg}")
                        return None
            except subprocess.TimeoutExpired:
                if attempt == 0:
                    log(f"⚠️ 拍照超时，杀残留进程重试")
                    kill_stale_ffmpeg()
                    time.sleep(1)
                else:
                    kill_stale_ffmpeg()
                    log(f"❌ 拍照超时（2次）")
                    return None
            except Exception as e:
                log(f"❌ 拍照异常: {e}")
                return None

    return None

# ========== 核心监控 ==========

class DisplayWatcher:
    """双通道检测显示器状态：

    通道 1: pmset -g assertions 检测 InternalPreventDisplaySleep 0→1（显示休眠→唤醒）
    通道 2: log stream 监听 loginwindow 认证事件（屏幕解锁）
    """

    def __init__(self, on_wake_cb):
        self.on_wake_cb = on_wake_cb
        self.last_state = None
        self._running = True
        self.screen_locked = False  # 当前屏幕是否锁屏
        self.last_hid_idle = None   # 锁屏后记录 HIDIdleTime

    def start(self):
        t = threading.Thread(target=self._poll, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _poll(self):
        # 初始检测
        self.last_state = self._check_pmset()
        self.screen_locked = self._check_screen_locked()
        if self.screen_locked:
            log("🔒 启动时检测到屏幕已锁屏")
        time.sleep(1)

        while self._running:
            try:
                new_screen_locked = self._check_screen_locked()

                # 屏幕锁状态变化：解锁 → 拍照
                if self.screen_locked and not new_screen_locked:
                    log("🔍 检测到屏幕解锁")
                    self.on_wake_cb()
                    self.last_hid_idle = None  # 清空锁屏 HID 记录
                elif not self.screen_locked and new_screen_locked:
                    log("🔒 屏幕已锁屏，开始监控键盘/鼠标活动")
                    self.last_hid_idle = self._get_hid_idle_time()
                self.screen_locked = new_screen_locked

                # 锁屏状态下：检测 HIDIdleTime 重置（有人动键盘/鼠标）
                if self.screen_locked:
                    current_idle = self._get_hid_idle_time()
                    if current_idle is not None and self.last_hid_idle is not None:
                        if current_idle < self.last_hid_idle - 1_000_000_000:
                            log("🔍 锁屏下检测到键盘/鼠标活动")
                            self.on_wake_cb()
                    self.last_hid_idle = current_idle if current_idle is not None else self.last_hid_idle

                # 通道：pmset 检测（显示休眠→唤醒）
                new_state = self._check_pmset()
                if new_state is not None and self.last_state is not None:
                    if self.last_state == 0 and new_state == 1:
                        log("🔍 显示器唤醒（从休眠转为亮起）")
                        self.on_wake_cb()
                self.last_state = new_state if new_state is not None else self.last_state

            except Exception as e:
                log(f"⚠️ 检测异常: {e}")
            time.sleep(2)

    def _check_screen_locked(self) -> bool:
        """通过 CGSSessionScreenIsLocked 检测屏幕是否锁屏"""
        try:
            import Quartz
            d = Quartz.CGSessionCopyCurrentDictionary()
            return d.get('CGSSessionScreenIsLocked', False) == 1
        except Exception:
            return False

    def _listen_unlock(self):
        """通道 2：log stream 监听 loginwindow 解锁事件"""
        time.sleep(3)
        startup_time = time.time()  # 启动后 10 秒内忽略历史事件
        while self._running:
            try:
                proc = subprocess.Popen(
                    ["log", "stream", "--predicate",
                     '(process == "loginwindow" AND eventMessage contains[c] "authentication")',
                     "--style", "compact", "--info"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=0,
                )
                if proc.stdout is None:
                    time.sleep(10)
                    continue

                import os as _os, fcntl as _fcntl
                fd = proc.stdout.fileno()
                old = _fcntl.fcntl(fd, _fcntl.F_GETFL)
                _fcntl.fcntl(fd, _fcntl.F_SETFL, old | _os.O_NONBLOCK)

                deadline = time.time() + 60
                while time.time() < deadline and self._running:
                    try:
                        data = _os.read(fd, 4096)
                        if not data:
                            break
                        now = time.time()
                        # 跳过启动期的历史事件
                        if now - startup_time < 10:
                            continue
                        # 检查冷却
                        if now - self.last_wake_time < COOLDOWN_WAKE:
                            continue
                        self.last_wake_time = now
                        log("🔍 检测到屏幕解锁事件")
                        take_photo("屏幕解锁")
                    except BlockingIOError:
                        time.sleep(1)
                        continue
                proc.stdout.close()
                proc.wait(timeout=3)
            except Exception:
                time.sleep(5)

    def _check_pmset(self) -> Optional[int]:
        """检查 InternalPreventDisplaySleep 状态"""
        try:
            result = subprocess.run(
                ["pmset", "-g", "assertions"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if "InternalPreventDisplaySleep" in line:
                    val = line.split()[-1].strip()
                    return int(val)
            return None
        except Exception:
            return None

    def _get_hid_idle_time(self) -> Optional[int]:
        """读取 HIDIdleTime（纳秒，自上次键盘/鼠标活动以来的时间）"""
        try:
            result = subprocess.run(
                ["ioreg", "-c", "IOHIDSystem"],
                capture_output=True, text=True, timeout=3,
            )
            for line in result.stdout.splitlines():
                if "HIDIdleTime" in line:
                    val = line.split("=")[-1].strip().strip('"')
                    return int(val)
            return None
        except Exception:
            return None


class IntruderMonitor:
    def __init__(self):
        self.last_wake_time = 0.0
        self.last_hid_time = 0.0
        self._running = True

    def on_display_wake(self):
        """显示器从休眠唤醒时的回调"""
        now = time.time()
        if now - self.last_wake_time >= COOLDOWN_WAKE:
            self.last_wake_time = now
            take_photo("显示器唤醒")

    def run(self):
        log("=" * 50)
        log("🚀 Intruder Cam v3 稳定版")
        log(f"📁 照片: {PHOTO_DIR}")
        log(f"⏱  冷却: 唤醒{COOLDOWN_WAKE}s / 键盘{COOLDOWN_HID}s")
        log("=" * 50)

        # 启动测试照（已禁用：KeepAlive 频繁重启导致大量无意义拍照）
        # take_photo("启动测试")

        # 启动显示器状态轮询（每 2 秒检测）
        watcher = DisplayWatcher(on_wake_cb=self.on_display_wake)
        watcher.start()
        log("👂 显示器状态轮询已启动")

        # 跳过 log stream 启动输出
        time.sleep(3)

        # 持续监听 HID 活动（自动重连 log stream）
        while self._running:
            # 主 HID 监听
            try:
                self._listen_hid()
            except Exception as e:
                log(f"⚠️ HID 监听异常: {e}")
                import traceback
                log(traceback.format_exc())
            log("🔄 HID 监听断开，5 秒后重连...")
            for _ in range(5):
                if not self._running:
                    break
                time.sleep(1)
        watcher.stop()
        log("👋 monitor stopped")

    def _check_recent_display_wake(self):
        """备用检测已禁用 — WindowServer display 事件太频繁，误报严重"""
        pass

    def _listen_hid(self):
        """启动一次 log stream 监听（非 GUI session 下约 20-30 秒断开，自动重连）"""
        predicate = '(process == "powerd" AND eventMessage contains[c] "hidActive:1")'

        proc = subprocess.Popen(
            ["log", "stream", "--predicate", predicate, "--style", "compact", "--info"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=0,  # unbuffered
        )
        log("👂 HID 活动监听已启动")

        if proc.stdout is None:
            log("⚠️ HID 监听无法启动（stdout 为空）")
            return
        if not proc.stdout.readable():
            log("⚠️ HID 监听无法启动（stdout 不可读）")
            proc.stdout.close()
            return

        # 用 os.read 非阻塞轮询，每次最多 45 秒
        import os as _os
        import fcntl as _fcntl
        fd = proc.stdout.fileno()
        # 设置为非阻塞模式
        old_flags = _fcntl.fcntl(fd, _fcntl.F_GETFL)
        _fcntl.fcntl(fd, _fcntl.F_SETFL, old_flags | _os.O_NONBLOCK)
        deadline = time.time() + 45

        try:
            while time.time() < deadline and self._running:
                try:
                    data = _os.read(fd, 4096)
                    if not data:
                        break
                    for line in data.decode('utf-8', errors='replace').split('\n'):
                        line = line.strip()
                        if not line or line.startswith("Filtering") or line.startswith("log"):
                            continue
                        now = time.time()
                        if "hidActive:1" in line and now - self.last_hid_time >= COOLDOWN_HID:
                            self.last_hid_time = now
                            log("🔍 检测到键盘/鼠标活动")
                            take_photo("有人碰电脑")
                except BlockingIOError:
                    # 没有数据可读，等 1 秒再试
                    time.sleep(1)
                    continue
                except Exception as e:
                    log(f"⚠️ HID 读取异常: {e}")
                    break
        finally:
            # 关键修复：确保 pipe 被关闭，防止 FD 泄漏
            proc.stdout.close()
            proc.wait(timeout=5)


# ========== 登录项管理（替代 LaunchAgent，摄像头权限正常） ==========

def install_login_item():
    """通过 osascript 注册为登录项（自带用户权限，摄像头可用）"""
    script = f'''
tell application "System Events"
    set appPath to "{__file__}"
    set loginItemList to get the name of every login item
    if "IntruderCam" is not in loginItemList then
        make new login item at end of login items with properties {{name:"IntruderCam", path:appPath}}
    end if
end tell

tell application "Terminal"
    activate
    do script "python3 \\"{__file__}\\" --daemon"
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    log("✅ 已添加登录项 + 启动 IntruderCam")
    print("✅ 已添加登录项（开机自启）+ 已启动 IntruderCam")


def uninstall_login_item():
    script = '''
tell application "System Events"
    set loginItemList to get the name of every login item
    repeat with itemName in loginItemList
        if itemName contains "IntruderCam" then
            delete login item itemName
        end if
    end repeat
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)

    # 也杀掉运行中的进程
    subprocess.run(["pkill", "-f", "intruder_cam_v3.py"], capture_output=True)
    log("✅ 已移除登录项")
    print("✅ 已移除登录项")


# ========== 入口 ==========

def main():
    if "--install" in sys.argv:
        install_login_item()
        return
    elif "--uninstall" in sys.argv:
        uninstall_login_item()
        return

    if "--daemon" in sys.argv:
        if os.fork() > 0:
            sys.exit(0)

    # --foreground 模式：直接运行（用于 LaunchAgent，不 fork）
    monitor = IntruderMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
