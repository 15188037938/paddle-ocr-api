@echo off
chcp 65001 >nul
title PaddleOCR API - Windows 一键启动

echo ╔══════════════════════════════════════╗
echo ║     PaddleOCR API Windows 一键启动   ║
║      v2.1.0 - GPU + 批量 + 认证        ║
echo ╚══════════════════════════════════════╝
echo.

rem ===== 可选：设置 API Key =====
if "%API_KEY%"=="" (
    echo [!] 提示：可通过 set API_KEY=your_secret_key 开启认证
) else (
    echo [✓] API Key 认证已开启
)

rem ===== 可选：启用 GPU =====
if /i "%USE_GPU%"=="true" (
    echo [✓] GPU 加速模式已启用
) else if /i "%USE_GPU%"=="1" (
    set USE_GPU=true
    echo [✓] GPU 加速模式已启用
)

rem ===== 1. 检查 Python =====
echo [*] 检查 Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [!!] 未找到 Python，请先安装 Python 3.7+
    echo      下载: https://www.python.org/downloads/
    echo      安装时记得勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo [✓] Python: %%i

rem ===== 2. 检查/安装 PaddlePaddle（优先 GPU） =====
echo [*] 检查 PaddlePaddle...
python -c "import paddle; print('版本:', paddle.__version__)" 2>nul
if %errorlevel% neq 0 (
    if /i "%USE_GPU%"=="true" (
        echo [!] 未安装，正在安装 GPU 版（约3-8分钟）...
        python -m pip install paddlepaddle-gpu -q
        echo [✓] PaddlePaddle-GPU 安装完成
    ) else (
        echo [!] 未安装，正在自动安装（CPU版，约2-5分钟）...
        python -m pip install paddlepaddle -q
        echo [✓] PaddlePaddle 安装完成
    )
) else (
    echo [✓] PaddlePaddle 已安装
)

rem ===== 3. 检查/安装 PaddleOCR =====
echo [*] 检查 PaddleOCR...
python -c "import paddleocr" 2>nul
if %errorlevel% neq 0 (
    echo [!] 未安装，正在自动安装...
    python -m pip install paddleocr==2.10.0 -q
    echo [✓] PaddleOCR 安装完成
) else (
    echo [✓] PaddleOCR 已安装
)

rem ===== 4. 检查/安装 uvicorn =====
echo [*] 检查 uvicorn...
python -c "import uvicorn" 2>nul
if %errorlevel% neq 0 (
    echo [!] 正在安装 uvicorn...
    python -m pip install uvicorn fastapi requests -q
)
echo [✓] 依赖库就绪

rem ===== 5. 获取脚本所在目录 =====
set "API_DIR=%~dp0"

rem ===== 6. 检查 API 文件 =====
if not exist "%API_DIR%ocr_api.py" (
    echo [!!] 未找到 ocr_api.py
    echo      请确保 start_ocr.bat 和 ocr_api.py 在同一目录
    pause
    exit /b 1
)
echo [✓] API 文件就绪

rem ===== 7. 启动服务 =====
echo.
echo [*] 正在启动 OCR 服务...
taskkill /f /im "uvicorn*" >nul 2>&1
timeout /t 2 /nobreak >nul

cd /d "%API_DIR%"
start /b "" python -m uvicorn ocr_api:app --host 0.0.0.0 --port 8000

timeout /t 8 /nobreak >nul

rem ===== 8. 验证服务 =====
python -c "import requests; r=requests.get('http://localhost:8000/'); assert r.status_code==200" 2>nul
if %errorlevel% equ 0 (
    echo [✓] OCR 服务启动成功
) else (
    echo [!!] 启动失败，请检查是否有端口冲突或报错
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════╗
echo ║                                          ║
echo ║   PaddleOCR API 已启动                   ║
echo ║                                          ║
echo ║   本地地址: http://localhost:8000        ║
echo ║   Swagger  : http://localhost:8000/docs  ║
echo ║                                          ║
echo ║   测试:                                    ║
echo ║                                          ║
echo ║   curl -X POST http://localhost:8000/ocr/upload -F "file=@图片.png"  ║
echo ║                                          ║
echo ╚══════════════════════════════════════════╝
echo.
echo 按任意键停止服务...
pause >nul

taskkill /f /im "uvicorn*" >nul 2>&1
echo 服务已停止
pause
