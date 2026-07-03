#!/bin/bash
# =============================================================
# PaddleOCR API - 云服务器一键部署脚本
# 适用系统：Ubuntu 18.04+ / CentOS 7+ / Debian 10+
# 用法：bash deploy_ocr_server.sh
# =============================================================

set -e

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

# 检测系统
OS=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
fi

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║  PaddleOCR API 云服务器一键部署      ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# 步骤1：安装系统依赖
# ============================================================
echo -e "\n${YELLOW}===== 步骤1/5：安装系统依赖 =====${NC}"

if [ "$OS" == "ubuntu" ] || [ "$OS" == "debian" ]; then
    apt-get update -yqq && apt-get install -yqq python3 python3-pip nfs-common -y
elif [ "$OS" == "centos" ] || [ "$OS" == "rhel" ] || [ "$OS" == "alinux" ]; then
    yum install -y python3 python3-pip
else
    # 通用检测
    if command -v apt-get &>/dev/null; then
        apt-get update -yqq && apt-get install -yqq python3 python3-pip
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip
    else
        err "未能识别的系统，请手动安装 python3 和 pip3"
        exit 1
    fi
fi

log "系统依赖安装完成"

# ============================================================
# 步骤2：创建项目目录
# ============================================================
echo -e "\n${YELLOW}===== 步骤2/5：创建项目目录 =====${NC}"

INSTALL_DIR="/opt/paddle-ocr"
mkdir -p "$INSTALL_DIR"
log "项目目录: $INSTALL_DIR"

# 下载 API 文件（从本脚本同目录复制或直接内嵌）
if [ -f "$(dirname "$0")/ocr_api.py" ]; then
    cp "$(dirname "$0")/ocr_api.py" "$INSTALL_DIR/"
    log "已复制本地 ocr_api.py"
else
    # 从 GitHub 等源下载（占位，实际需要用户自己放置）
    warn "未找到 ocr_api.py，请手动将此文件放到 $INSTALL_DIR/"
    warn "可以从 WorkBuddy 沙箱中复制：/root/.codebuddy/skills/paddle-ocr/ocr_api.py"
fi

# ============================================================
# 步骤3：安装 Python 依赖
# ============================================================
echo -e "\n${YELLOW}===== 步骤3/5：安装 Python 依赖 =====${NC}"

pip3 install --upgrade pip -q
pip3 install paddlepaddle -q
pip3 install "paddleocr==2.10.0" -q
pip3 install uvicorn fastapi requests -q
pip3 install python-multipart -q

log "Python 依赖安装完成"
log "PaddlePaddle: $(python3 -c 'import paddle; print(paddle.__version__)' 2>/dev/null || echo '检查失败')"
log "PaddleOCR: 已安装"

# ============================================================
# 步骤4：配置 systemd 服务（开机自启）
# ============================================================
echo -e "\n${YELLOW}===== 步骤4/5：配置开机自启 =====${NC}"

cat > /etc/systemd/system/paddle-ocr.service << 'SERVICE'
[Unit]
Description=PaddleOCR API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/paddle-ocr
ExecStart=/usr/bin/python3 -m uvicorn ocr_api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable paddle-ocr.service

log "systemd 服务已配置，开机自启已启用"

# ============================================================
# 步骤5：启动服务
# ============================================================
echo -e "\n${YELLOW}===== 步骤5/5：启动服务 =====${NC}"

systemctl start paddle-ocr.service

# 等待服务就绪
echo "[*] 等待服务启动...（首次需加载模型，约 10-20 秒）"
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 获取服务器 IP
PUBLIC_IP=$(curl -s http://ifconfig.me 2>/dev/null || curl -s http://ip.sb 2>/dev/null || echo "请手动获取公网IP")

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${GREEN}PaddleOCR API 部署完成${NC}                                   ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${NC}本地地址: ${YELLOW}http://localhost:8000${NC}                         ${CYAN}║${NC}"
echo -e "${CYAN}  ║   ${NC}公网地址: ${YELLOW}http://${PUBLIC_IP}:8000${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}  ║   ${NC}Swagger  : ${YELLOW}http://${PUBLIC_IP}:8000/docs${NC}         ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${NC}服务状态: ${YELLOW}systemctl status paddle-ocr${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}  ║   ${NC}查看日志: ${YELLOW}journalctl -u paddle-ocr -f${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${YELLOW}⚠ 记得在云服务器安全组/防火墙中放行 8000 端口${NC}         ${CYAN}║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 验证服务
echo "[*] 验证服务..."
STATUS=$(curl -s http://localhost:8000/ 2>/dev/null)
if [ -n "$STATUS" ]; then
    log "服务运行正常：$STATUS"
else
    err "服务可能未正常启动，请查看日志：journalctl -u paddle-ocr -f"
fi

echo ""
echo -e "${YELLOW}Windows 调用示例：${NC}"
echo "  curl -X POST http://${PUBLIC_IP}:8000/ocr/upload -F \"file=@D:\图片.png\""
echo "  curl -X POST http://${PUBLIC_IP}:8000/ocr/search -F \"file=@D:\图片.png\" -F \"keyword=回归\" -F \"fuzzy=true\""
echo ""
