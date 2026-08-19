#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  森空岛自动签到 — 一键更新 Token
#
#  用法:
#    bash set_token.sh            # 从剪贴板读取 Token (需 Termux:API)
#    bash set_token.sh <新Token>  # 直接传入 Token
#
#  说明:
#    - 自动保留 creds.txt 中的注释行 (# 开头)
#    - 只替换 Token 行，不会误删配置
#    - 更新后立即可选测试签到
# ============================================================

set -e

INSTALL_DIR="$HOME/skland-auto-sign"
CREDS="$INSTALL_DIR/creds.txt"

# ── 颜色 ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── 获取 Token ──
if [ -n "$1" ]; then
    # 方式一: 命令行参数传入
    TOK="$1"
else
    # 方式二: 从剪贴板读取 (需 Termux:API)
    if command -v termux-clipboard-get >/dev/null 2>&1; then
        TOK=$(termux-clipboard-get 2>/dev/null | tr -d '[:space:]')
    else
        echo -e "${RED}[ERROR]${NC} 未安装 Termux:API，无法读取剪贴板"
        echo "  安装: pkg install termux-api"
        echo "  或用法: bash set_token.sh <新Token>"
        exit 1
    fi
fi

# ── 校验 ──
if [ -z "$TOK" ]; then
    echo -e "${RED}[ERROR]${NC} 未获取到 Token（剪贴板为空？）"
    echo "  请先在浏览器复制新 Token，再运行本脚本"
    exit 1
fi

if [ ${#TOK} -lt 10 ]; then
    echo -e "${RED}[ERROR]${NC} Token 长度异常 (${#TOK} 字符)，请检查是否复制完整"
    exit 1
fi

# ── 确保 creds.txt 存在 ──
if [ ! -f "$CREDS" ]; then
    echo -e "${YELLOW}[WARN]${NC} creds.txt 不存在，创建新文件"
    mkdir -p "$INSTALL_DIR"
    cat > "$CREDS" << 'EOF'
# 森空岛自动签到 — Token 配置
# 每行一个鹰角通行证 Token，# 开头为注释
# 获取方式：森空岛 App → 我的 → 设置 → 复制 Token
# 或浏览器登录 skland.com 后访问 https://web-api.skland.com/account/info/hg
# ⚠️ 此文件包含敏感信息，已被 .gitignore 忽略
EOF
fi

# ── 保留注释行，写入新 Token ──
grep '^#' "$CREDS" > /tmp/creds_new.txt 2>/dev/null || true
echo "$TOK" >> /tmp/creds_new.txt
mv /tmp/creds_new.txt "$CREDS"

echo -e "${GREEN}[OK]${NC} Token 已更新: ${TOK:0:8}****${TOK: -4}"

# ── 可选: 立即测试 ──
if [ -t 0 ]; then
    echo -n "是否立即测试签到? (y/N) "
    read -r REPLY
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        cd "$INSTALL_DIR"
        python skland_sign.py
    fi
fi
