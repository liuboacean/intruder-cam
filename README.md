# Intruder Cam 👁️

> macOS 防盗拍监控 — 锁屏状态下有人碰你电脑，自动抓拍并导入系统相册

## 工作原理

电脑锁屏后，如果有人：

- **打开笔记本盖子** / **移动鼠标** → 显示器唤醒 → 自动拍照
- **敲击键盘** / **点击鼠标** → HID 活动检测 → 自动拍照

照片会 **自动导入「照片」App 的 IntruderCam 相簿**，你随时可以查看。

## 安装

### 前提

```bash
# 确保 ffmpeg 已安装（用于调用摄像头）
brew install ffmpeg
```

### 下载 & 安装

```bash
# 下载脚本
curl -sL -o intruder_cam.py \
  "https://raw.githubusercontent.com/liuboacean/intruder-cam/main/intruder_cam.py"

# 安装开机自启（登录项）
python3 intruder_cam.py --install
```

安装后脚本会：
1. 注册为**登录项**（开机自动启动）
2. 打开终端窗口，立即开始监听
3. 首次运行时 macOS 会弹**摄像头权限**提示 → 点「允许」

### 权限说明

首次运行时会弹出摄像头权限请求，请允许。脚本只在本地运行，不上传任何数据。

## 使用

```bash
# 前台测试
python3 intruder_cam.py

# 后台运行（终端关闭后继续）
python3 intruder_cam.py --daemon

# 安装开机自启
python3 intruder_cam.py --install

# 卸载开机自启
python3 intruder_cam.py --uninstall
```

## 照片在哪？

- **本地文件**：`~/Pictures/IntruderCam/`
- **系统相册**：打开「照片」App → 相簿 → **IntruderCam**

照片命名格式：`intruder_YYYYMMDD_HHMMSS.png`

## 技术细节

- 通过 `log stream` 实时监听 HID（键盘/鼠标）活动  
- 通过 `pmset -g assertions` 每 2 秒轮询显示器休眠状态，检测唤醒  
- 使用 `ffmpeg` + AVFoundation 调用摄像头（1280×720）  
- 拍照后通过 AppleScript 导入系统相册  
- 文件锁防止 ffmpeg 并发冲突  
- 唤醒冷却 20s / 键盘冷却 15s，防重复触发

## 为什么不用 LaunchAgent？

macOS 安全机制（TCC）限制，LaunchAgent 后台启动的进程没有摄像头权限。
本程序使用 **登录项（Login Item）** 方式注册开机自启，从终端启动以保证摄像头权限正常。

## 隐私

- **100% 本地运行**，不上传任何数据到云端
- 所有照片仅保存在你的电脑和系统相册中
- 开源代码，可审阅

## 许可证

MIT
