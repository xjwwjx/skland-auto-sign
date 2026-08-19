#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  森空岛自动签到 - Android (Termux) 一键安装脚本
#
#  使用方法:
#    1. 安装 Termux (F-Droid 版本推荐)
#    2. 打开 Termux，执行:
#       pkg install git -y
#       git clone https://github.com/xjwwjx/skland-auto-sign.git ~/skland-auto-sign
#       cd ~/skland-auto-sign
#       bash setup_android.sh
#
#  或直接下载脚本后运行:
#       curl -fsSL https://raw.githubusercontent.com/xjwwjx/skland-auto-sign/main/setup_android.sh | bash
# ============================================================

set -e

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 检测 Termux 环境 ──
if [ -z "$TERMUX_VERSION" ]; then
    error "此脚本需要在 Termux 环境中运行！"
    echo "请先安装 Termux (推荐从 F-Droid 安装: https://f-droid.org/packages/com.termux/)"
    exit 1
fi

info "检测到 Termux $TERMUX_VERSION"

# ── 安装目录 ──
INSTALL_DIR="$HOME/skland-auto-sign"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 如果当前目录已经是安装目录，就不需要再 clone
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ] && [ "$(basename "$SCRIPT_DIR")" = "skland-auto-sign" ]; then
    info "从克隆目录运行，使用当前目录: $SCRIPT_DIR"
    INSTALL_DIR="$SCRIPT_DIR"
elif [ ! -d "$INSTALL_DIR" ]; then
    info "克隆仓库到 $INSTALL_DIR ..."
    pkg install git -y
    git clone https://github.com/xjwwjx/skland-auto-sign.git "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
info "工作目录: $INSTALL_DIR"

# ── 安装依赖 ──
info "安装 Python 和依赖..."
pkg update -y
pkg install -y python python-pip cronie termux-api

# 安装 Python 依赖
pip install -r requirements.txt -q

info "依赖安装完成"

# ── 创建配置文件（如果不存在）──
if [ ! -f "creds.txt" ]; then
    if [ -f "creds.example.txt" ]; then
        cp creds.example.txt creds.txt
    else
        cat > creds.txt << 'EOF'
# 森空岛自动签到 — Token 配置
# 每行一个鹰角通行证 Token，# 开头为注释
# 获取方式：森空岛 App → 我的 → 设置 → 复制 Token
# ⚠️ 此文件包含敏感信息，已被 .gitignore 忽略
EOF
    fi
    warn "已创建 creds.txt，请编辑填入你的 Token！"
    warn "命令: nano $INSTALL_DIR/creds.txt"
fi

# ── 配置 cron 定时任务 ──
CRON_SCHEDULE="0 15 * * *"  # 每天 15:00 执行
PYTHON_BIN="$(command -v python3 || command -v python)"

info "配置定时任务 (每天 15:00 自动签到)..."

# 创建 cron 执行脚本
cat > "$INSTALL_DIR/run_sign.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash
# 森空岛自动签到 - cron 执行入口
cd "$INSTALL_DIR"
export HOME="$HOME"
export PATH="$PATH"
$PYTHON_BIN "$INSTALL_DIR/skland_sign.py" >> "$INSTALL_DIR/sign_log.txt" 2>&1
EOF
chmod +x "$INSTALL_DIR/run_sign.sh"

# 设置 crontab
CRON_ENTRY="$CRON_SCHEDULE $INSTALL_DIR/run_sign.sh"

# 检查是否已有 cron 任务
if crontab -l 2>/dev/null | grep -q "skland-auto-sign"; then
    info "已存在签到定时任务，跳过"
else
    # 保留现有 crontab，追加新任务
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    info "定时任务已添加: $CRON_SCHEDULE"
fi

# ── 启动 cron 服务 ──
info "启动 cron 服务..."
if pgrep -x crond > /dev/null 2>&1; then
    info "crond 已在运行"
else
    crond && info "crond 已启动" || warn "crond 启动失败，请手动执行: crond"
fi

# ── 设置 Termux 唤醒锁（防止手机休眠杀进程）──
if command -v termux-wake-lock > /dev/null 2>&1; then
    termux-wake-lock 2>/dev/null && info "已设置唤醒锁 (termux-wake-lock)" || warn "唤醒锁设置失败"
fi

# ── 设置 Termux 开机自启 ──
BOOT_RC="$HOME/.termux/boot/start_skland_cron.sh"
if [ ! -d "$HOME/.termux/boot" ]; then
    mkdir -p "$HOME/.termux/boot"
fi
cat > "$BOOT_RC" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Termux 开机自启: 启动 cron 服务并设置唤醒锁
termux-wake-lock 2>/dev/null
crond 2>/dev/null
EOF
chmod +x "$BOOT_RC"
info "已设置开机自启 (需要安装 Termux:Boot)"

# ── 安装完成，输出信息 ──
echo ""
echo "=============================================="
echo -e "${GREEN}  安装完成！${NC}"
echo "=============================================="
echo ""
echo "  安装目录: $INSTALL_DIR"
echo "  Python:  $PYTHON_BIN"
echo "  定时任务: 每天 15:00 自动签到"
echo "  日志文件: $INSTALL_DIR/sign_log.txt"
echo ""
echo -e "${YELLOW}  下一步:${NC}"
echo "  1. 编辑 Token 配置:"
echo "     nano $INSTALL_DIR/creds.txt"
echo ""
echo "  2. 手动测试签到:"
echo "     cd $INSTALL_DIR && python skland_sign.py"
echo ""
echo "  3. 查看签到日志:"
echo "     cat $INSTALL_DIR/sign_log.txt"
echo ""
echo -e "${YELLOW}  管理定时任务:${NC}"
echo "  查看任务:   crontab -l"
echo "  编辑时间:   crontab -e"
echo "  删除任务:   crontab -l | grep -v skland-auto-sign | crontab -"
echo "  重启 cron:  pkill crond && crond"
echo ""
echo -e "${YELLOW}  注意事项:${NC}"
echo "  - 需要保持 Termux 后台运行，不要被系统清理"
echo "  - 建议在电池设置中关闭 Termux 的电池优化"
echo "  - 安装 Termux:Boot 可实现开机自启 cron"
echo "  - Termux:API 需要从 F-Droid 安装对应 APP"
echo ""
echo "=============================================="
