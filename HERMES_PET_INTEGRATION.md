# IntruderCam 集成 Hermes Pet 指南

## 两种使用模式

IntruderCam 可以独立运行，也可以集成到 Hermes Pet 桌面宠物中使用。

---

## 模式 A：无 Hermes Pet（独立运行）

使用 `start_intruder.py` 作为守护进程启动，cron 看门狗自动保活。

```bash
# 启动
python3 ~/intruder-cam/start_intruder.py

# 停止
pkill -9 -f "intruder_cam\\.py"

# 查看状态
PID=$(cat ~/Library/Logs/intruder_cam.pid 2>/dev/null)
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "IntruderCam 运行中 (PID $PID)"
else
    echo "IntruderCam 未运行"
fi

# 查看照片
open ~/Pictures/IntruderCam/
```

无需额外配置，cron 每 2 分钟自动保活。

---

## 模式 B：与 Hermes Pet 集成

如果 Hermes Pet 桌面宠物正在运行（`127.0.0.1:8768`），IntruderCam 的控制面板会自动出现在 Pet 的右键菜单中。

### 安装集成补丁

```bash
# 进入 Hermes Pet 项目目录
cd ~/.hermes/pet/taiei-hermes-pet

# 应用 IntruderCam 补丁
git apply ~/intruder-cam/hermes-pet-intrudercam.patch

# 重启 Pet
hermes-pet --restart --port 8768
```

### 使用

右键点击桌面 Pet → **IntruderCam** 子菜单：

```
IntruderCam
  🟢 运行中          ← 实时状态
  ─────────
  ■ Stop             ← 停止监控
  ─────────
  📂 Open Photos     ← 打开照片文件夹
```

- 状态自动刷新（每 2 秒）
- 运行中显示 Stop，未运行显示 Start
- 点击 Open Photos 打开 Finder 照片目录

### 卸载集成补丁

```bash
cd ~/.hermes/pet/taiei-hermes-pet
git checkout hermes-pet-macos/hermes_cli/assets/hermes_pet_macos.swift
git checkout hermes-pet-macos/hermes_cli/pet_overlay.py
hermes-pet --restart --port 8768
```

---

## 对照表

| 功能 | 无 Pet（终端） | 有 Pet（右键菜单） |
|------|---------------|-------------------|
| 启动 | `python3 start_intruder.py` | 右键 → Start |
| 停止 | `pkill -f intruder_cam` | 右键 → Stop |
| 状态 | 查 PID 文件 | 菜单直接显示 🟢/⚪ |
| 开照片 | `open ~/Pictures/IntruderCam/` | 右键 → Open Photos |
| 保活 | cron 2 分钟 | cron 2 分钟（不变） |
