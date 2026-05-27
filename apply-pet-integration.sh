#!/bin/bash
# 应用 Hermes Pet IntruderCam 集成补丁
set -e

PET_ROOT="$HOME/.hermes/pet/taiei-hermes-pet/hermes-pet-macos"
SWIFT="$PET_ROOT/hermes_cli/assets/hermes_pet_macos.swift"
PYTHON="$PET_ROOT/hermes_cli/pet_overlay.py"

echo "=== 验证文件存在 ==="
for f in "$SWIFT" "$PYTHON"; do
    if [ ! -f "$f" ]; then
        echo "❌ 文件不存在: $f"
        exit 1
    fi
done
echo "✅ 文件检查通过"

echo ""
echo "=== 应用 Swift 修改 ==="

# 1. PetSnapshot 加 intrudercam_running
if grep -q "intrudercam_running" "$SWIFT"; then
    echo "⏭️  已存在，跳过 PetSnapshot 修改"
else
    sed -i '' 's/let ui_language: String?$/let ui_language: String?\n    let intrudercam_running: Bool?/' "$SWIFT"
    echo "✅ 1/6 PetSnapshot 新增 intrudercam_running"
fi

# 2. PetOverlayView 加 intrudercamRunning 属性
if grep -q "intrudercamRunning" "$SWIFT"; then
    echo "⏭️  已存在，跳过属性添加"
else
    sed -i '' 's/private let supportedLanguages/private var intrudercamRunning = false\n    private let supportedLanguages/' "$SWIFT"
    echo "✅ 2/6 添加 intrudercamRunning 属性"
fi

# 3. setSnapshot 中赋值
if grep -q "intrudercam_running" "$SWIFT" | grep -q "setSnapshot"; then
    echo "⏭️  已存在，跳过 setSnapshot 修改"
else
    sed -i '' '/if let language = snapshot.ui_language/a\
        self.intrudercamRunning = snapshot.intrudercam_running ?? false' "$SWIFT"
    echo "✅ 3/6 setSnapshot 赋值 intrudercamRunning"
fi

# 4. rightMouseDown 插入菜单
if grep -q "addIntruderCamMenu" "$SWIFT"; then
    echo "⏭️  已存在，跳过菜单插入"
else
    sed -i '' '/addMenuItem(menu, title: tr("settings"), action: #selector(promptSettings))/a\
        menu.addItem(NSMenuItem.separator())\
        addIntruderCamMenu(to: menu)' "$SWIFT"
    echo "✅ 4/6 插入 IntruderCam 菜单"
fi

# 5. 添加 addIntruderCamMenu 函数 + @objc actions
if grep -q "func addIntruderCamMenu" "$SWIFT"; then
    echo "⏭️  已存在，跳过函数添加"
else
    # 在 totalNotificationCount 前插入
    sed -i '' '/private func totalNotificationCount/i\
\
    private func addIntruderCamMenu(to menu: NSMenu) {\
        let root = NSMenuItem(title: "IntruderCam", action: nil, keyEquivalent: "")\
        let submenu = NSMenu()\
        let statusText = intrudercamRunning ? "🟢 运行中" : "⚪ 未运行"\
        let statusItem = NSMenuItem(title: statusText, action: nil, keyEquivalent: "")\
        statusItem.isEnabled = false\
        submenu.addItem(statusItem)\
        submenu.addItem(NSMenuItem.separator())\
        if intrudercamRunning {\
            addMenuItem(submenu, title: "■ Stop", action: #selector(intruderCamStop))\
        } else {\
            addMenuItem(submenu, title: "▶ Start", action: #selector(intruderCamStart))\
        }\
        submenu.addItem(NSMenuItem.separator())\
        addMenuItem(submenu, title: "📂 Open Photos", action: #selector(intruderCamOpenPhotos))\
        menu.setSubmenu(submenu, for: root)\
        menu.addItem(root)\
    }\
\
    // MARK: - IntruderCam\
\
    @objc private func intruderCamStart() {\
        emitAction("intrudercam_start")\
    }\
\
    @objc private func intruderCamStop() {\
        emitAction("intrudercam_stop")\
    }\
\
    @objc private func intruderCamStatus() {\
        emitAction("intrudercam_status")\
    }\
\
    @objc private func intruderCamOpenPhotos() {\
        emitAction("intrudercam_photos")\
    }\
' "$SWIFT"
    echo "✅ 5/6 添加 addIntruderCamMenu + 4个action"
fi

echo ""
echo "=== 应用 Python 修改 ==="

# 6. 添加 _intrudercam_is_running 函数
if grep -q "_intrudercam_is_running" "$PYTHON"; then
    echo "⏭️  已存在，跳过函数添加"
else
    sed -i '' '/def _pet_preferences_payload/i\
def _intrudercam_is_running() -> bool:\
    pid_file = Path.home() / "Library/Logs/intruder_cam.pid"\
    if not pid_file.exists():\
        return False\
    try:\
        pid = int(pid_file.read_text().strip())\
        os.kill(pid, 0)\
        return True\
    except (OSError, ValueError):\
        return False\
\
' "$PYTHON"
    echo "✅ 7/8 添加 _intrudercam_is_running()"
fi

# 7. 在 snapshot 中加入 intrudecam_running
if grep -q "intrudercam_running" "$PYTHON"; then
    echo "⏭️  已存在，跳过 snapshot 修改"
else
    sed -i '' '/"ui_language": _pet_language(),/a\
            "intrudercam_running": _intrudercam_is_running(),' "$PYTHON"
    echo "✅ 8/8 snapshot 加入 intrudercam_running"
fi

echo ""
echo "=== 修改完成！重启 Pet ==="
hermes-pet --restart --port 8768 2>&1 || echo "请手动重启: hermes-pet --restart --port 8768"
