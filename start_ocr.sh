#!/bin/bash
# =============================================================
# PaddleOCR API - 一键启动脚本（Linux 沙箱/服务器版）
# 用法：bash start_ocr.sh
# =============================================================

set -e

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }

API_DIR="/root/.codebuddy/skills/paddle-ocr"
API_FILE="$API_DIR/ocr_api.py"

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║     PaddleOCR API 一键启动           ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ——— 1. 检查 Python ———
log "检查 Python..."
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    err "未安装 Python，请先安装 Python 3.7+"
    exit 1
fi
log "Python: $($PYTHON --version)"

# ——— 2. 检查/安装 PaddlePaddle ———
log "检查 PaddlePaddle..."
if $PYTHON -c "import paddle; print(paddle.__version__)" 2>/dev/null; then
    log "PaddlePaddle 已安装"
else
    warn "PaddlePaddle 未安装，正在自动安装（CPU版）..."
    $PYTHON -m pip install paddlepaddle -q
    log "PaddlePaddle 安装完成"
fi

# ——— 3. 检查/安装 PaddleOCR ———
log "检查 PaddleOCR..."
if $PYTHON -c "import paddleocr" 2>/dev/null; then
    log "PaddleOCR 已安装"
else
    warn "PaddleOCR 未安装，正在自动安装..."
    $PYTHON -m pip install "paddleocr==2.10.0" -q
    log "PaddleOCR 安装完成"
fi

# ——— 4. 检查 uvicorn ———
log "检查 uvicorn..."
$PYTHON -c "import uvicorn" 2>/dev/null || { warn "安装 uvicorn..."; $PYTHON -m pip install uvicorn fastapi -q; }
log "uvicorn 就绪"

# ——— 5. 检查 API 文件 ———
if [ ! -f "$API_FILE" ]; then
    err "未找到 $API_FILE"
    err "请确认项目已正确部署"
    exit 1
fi
log "API 文件就绪"

# ——— 6. 检查 requests ———
$PYTHON -c "import requests" 2>/dev/null || { warn "安装 requests..."; $PYTHON -m pip install requests -q; }
log "依赖库检查完成"

# ——— 7. 启动 OCR 服务 ———
echo ""
log "正在启动 OCR 服务...（首次启动需加载模型，约 10-15 秒）"
pkill -f "uvicorn ocr_api" 2>/dev/null || true
sleep 1

cd "$API_DIR"
nohup $PYTHON -m uvicorn ocr_api:app --host 0.0.0.0 --port 8000 > /tmp/ocr_api.log 2>&1 &
OCR_PID=$!
sleep 2

# 等待服务就绪
for i in $(seq 1 20); do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    log "OCR 服务启动成功 (PID: $OCR_PID)"
    echo -e "  本地地址: ${CYAN}http://localhost:8000${NC}"
else
    err "OCR 服务启动失败，请查看日志：cat /tmp/ocr_api.log"
    exit 1
fi

# ——— 8. 启动公网隧道 ———
echo ""
log "正在启动公网隧道..."

# 检查/下载 cloudflared
CLOUDFLARED="/tmp/cloudflared"
if [ ! -f "$CLOUDFLARED" ]; then
    warn "正在下载 cloudflared..."
    curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
    log "cloudflared 下载完成"
fi

# 启动隧道
nohup "$CLOUDFLARED" tunnel --url http://localhost:8000 > /tmp/tunnel.log 2>&1 &
TUNNEL_PID=$!

# 等待隧道就绪，提取公网 URL
TUNNEL_URL=""
for i in $(seq 1 15); do
    TUNNEL_URL=$(grep -oP 'https://[a-z-]+\.trycloudflare\.com' /tmp/tunnel.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${GREEN}PaddleOCR API 已启动${NC}                                   ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
if [ -n "$TUNNEL_URL" ]; then
    echo -e "${CYAN}  ║   ${NC}公网地址: ${YELLOW}$TUNNEL_URL${NC}                   ${CYAN}║${NC}"
fi
echo -e "${CYAN}  ║   ${NC}本地地址: ${YELLOW}http://localhost:8000${NC}                         ${CYAN}║${NC}"
echo -e "${CYAN}  ║   ${NC}Swagger  : ${YELLOW}http://localhost:8000/docs${NC}                     ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ║   ${NC}${YELLOW}测试:${NC} curl -X POST $TUNNEL_URL/ocr/upload -F \"file=@图片.png\"  ${CYAN}║${NC}"
echo -e "${CYAN}  ║                                                             ║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
log "停止服务: pkill -f 'uvicorn ocr_api'; pkill -f cloudflared"
log "查看日志: cat /tmp/ocr_api.log"
echo ""
