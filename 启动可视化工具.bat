@echo off
chcp 65001 >nul
title PaddleOCR 一键启动

rem ===== 找 Python =====
set PYTHON=
if exist "%~dp0venv311\Scripts\python.exe" set PYTHON=%~dp0venv311\Scripts\python.exe
if exist "%~dp0venv\Scripts\python.exe" set PYTHON=%~dp0venv\Scripts\python.exe
if "%PYTHON%"=="" set PYTHON=python

rem ===== 1. 启动 GUI（立即弹出窗口，不阻塞） =====
start "" "%PYTHON%" "%~dp0PaddleOCR可视化工具.pyw"

rem ===== 2. 后台启动 OCR 服务（静默，用 Python 脚本） =====
start /min "PaddleOCR-服务" "%PYTHON%" -c "
import os, subprocess, sys, requests, time

def log(msg):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '启动日志.txt'), 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime(\"%H:%M:%S\")}] {msg}\n')

log('后台服务启动中...')

# 检查服务是否已运行
try:
    r = requests.get('http://localhost:8000/', timeout=2)
    if r.status_code == 200:
        log('OCR 服务已在运行')
        sys.exit(0)
except:
    pass

# 检查依赖，缺啥装啥
try:
    import uvicorn
except ImportError:
    log('安装 OCR 依赖（首次约 3-5 分钟）...')
    subprocess.run([sys.executable, '-m', 'pip', 'install',
        'paddlepaddle', 'paddleocr==2.10.0', 'uvicorn', 'fastapi', 'requests', 'python-multipart', '-q'])
    log('依赖安装完成')

# 启动 OCR 服务
log('启动 OCR 服务...')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, '-m', 'uvicorn', 'ocr_api:app', '--host', '0.0.0.0', '--port', '8000'])
" 2>nul

exit
