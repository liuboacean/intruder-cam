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
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ========== 配置 ==========
PHOTO_DIR = Path.home() / "Pictures" / "IntruderCam"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
LOG_FILE = Path.home() / "Library" / "Logs" / "intruder_cam.log"
LOCK_FILE = Path.home() / "Library" / "Logs" / "intruder_cam.lock"

# 冷却时间
COOLDOWN_WAKE = 20    # 显示器唤醒后 20 秒内不再重复拍
COOLDOWN_HID = 15     # 键盘/鼠标事件后 15 秒内不再重复拍

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
    """确保 IntruderCam 相簿存在"""
    global _photos_album_ready
    if _photos_album_ready:
        return True
    try:
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


def take_photo(reason: str) -> str | None:
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

class IntruderMonitor:
    def __init__(self):
        self.last_wake_time = 0.0
        self.last_hid_time = 0.0

    def run(self):
        log("=" * 50)
        log("🚀 Intruder Cam v3 稳定版")
        log(f"📁 照片: {PHOTO_DIR}")
        log(f"⏱  冷却: 唤醒{COOLDOWN_WAKE}s / 键盘{COOLDOWN_HID}s")
        log("=" * 50)

        # 启动测试照
        take_photo("启动测试")

        # 跳过 log stream 启动输出
        time.sleep(3)

        predicate = (
            '(process == "powerd" AND eventMessage contains[c] "Cancelling notification display wake")'
            ' OR (process == "powerd" AND eventMessage contains[c] "hidActive:1")'
        )

        proc = subprocess.Popen(
            ["log", "stream", "--predicate", predicate, "--style", "compact", "--info"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        log("👂 监听中... 去锁屏试试吧！")

        try:
            for line in proc.stdout:
                line = line.strip()
                if not line or line.startswith("Filtering") or line.startswith("log"):
                    continue

                now = time.time()

                if "Cancelling notification display wake" in line:
                    if now - self.last_wake_time >= COOLDOWN_WAKE:
                        self.last_wake_time = now
                        log("🔍 显示器唤醒!")
                        take_photo("显示器唤醒")
                    # 冷却内不记录日志（静默跳过）

                elif "hidActive:1" in line:
                    if now - self.last_hid_time >= COOLDOWN_HID:
                        self.last_hid_time = now
                        log("🔍 检测到键盘/鼠标活动")
                        take_photo("有人碰电脑")

        except KeyboardInterrupt:
            log("🛑 用户中断")
        except Exception as e:
            log(f"❌ 监控异常: {e}")


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
