@echo off
chcp 65001 >nul
title PaddleOCR 一键启动（服务 + 可视化工具）
mode con cols=70 lines=22

echo ╔══════════════════════════════════════╗
echo ║     PaddleOCR 一键启动               ║
echo ║     自动检测服务 + 启动可视化工具    ║
echo ╚══════════════════════════════════════╝
echo.

rem ===== 1. 找 Python 环境 =====
set PYTHON=
if exist "%~dp0venv311\Scripts\python.exe" (
    set PYTHON=%~dp0venv311\Scripts\python.exe
    echo [✓] 虚拟环境: venv311
) else if exist "%~dp0venv\Scripts\python.exe" (
    set PYTHON=%~dp0venv\Scripts\python.exe
    echo [✓] 虚拟环境: venv
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python
        echo [✓] 系统 Python
    ) else (
        echo [!!] 未找到 Python！请安装 https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

for /f "tokens=2" %%i in ('%PYTHON% --version 2^>^&1') do echo [✓] Python: %%i

rem ===== 2. 检查 GUI 依赖 =====
echo [*] 检查 GUI 依赖...
%PYTHON% -c "import PIL, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 安装 GUI 依赖...
    %PYTHON% -m pip install Pillow requests -q
    if %errorlevel% neq 0 (
        echo [!!] 依赖安装失败
        pause
        exit /b 1
    )
)
echo [✓] GUI 依赖就绪

rem ===== 3. 检查 OCR 服务 =====
echo.
echo [*] 检测 OCR 服务状态...
%PYTHON% -c "import requests; r=requests.get('http://localhost:8000/', timeout=2); print('ok' if r.status_code==200 else 'no')" >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] OCR 服务已在运行
    set NEED_START_SERVER=0
) else (
    echo [!] OCR 服务未启动，正在后台启动...
    set NEED_START_SERVER=1
)

rem ===== 4. 启动 OCR 服务（如果需要） =====
if "%NEED_START_SERVER%"=="1" (
    rem 检查 OCR 服务依赖
    echo [*] 检查 OCR 依赖...
    %PYTHON% -c "import uvicorn" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [!] 正在安装 OCR 依赖（首次约 3-5 分钟）...
        echo     请耐心等待...
        %PYTHON% -m pip install paddlepaddle "paddleocr==2.10.0" uvicorn fastapi requests python-multipart -q
        if %errorlevel% neq 0 (
            echo [!!] OCR 依赖安装失败
            pause
            exit /b 1
        )
        echo [✓] OCR 依赖安装完成
    ) else (
        echo [✓] OCR 依赖就绪
    )

    rem 后台启动 OCR 服务
    start "PaddleOCR API 服务" /min "%PYTHON%" -m uvicorn ocr_api:app --host 0.0.0.0 --port 8000
    echo.
    echo [→] OCR 服务正在启动（首次需下载模型，约 10-30 秒）...
    
    rem 等待服务就绪（最多等 120 秒）
    set WAIT_COUNT=0
    :WAIT_LOOP
    %PYTHON% -c "import requests; r=requests.get('http://localhost:8000/', timeout=2); print('ok' if r.status_code==200 else 'no')" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [✓] OCR 服务启动完成！
        goto SERVER_READY
    )
    set /a WAIT_COUNT+=1
    if %WAIT_COUNT% geq 60 (
        echo [!!] OCR 服务启动超时
        echo     请手动检查：http://localhost:8000
        pause
        exit /b 1
    )
    echo     等待中...（%WAIT_COUNT% 秒）
    timeout /t 2 /nobreak >nul
    goto WAIT_LOOP
    :SERVER_READY
)

echo.

rem ===== 5. 启动可视化工具 =====
echo [→] 正在启动可视化工具...
start "" "%PYTHON%" "%~dp0PaddleOCR可视化工具.pyw"
echo [✓] 可视化工具已启动！
echo.
echo     如果窗口没弹出来，请检查：
echo     1. PaddleOCR可视化工具.pyw 是否存在
echo     2. 浏览器打开 http://localhost:8000 看服务是否正常
echo.
timeout /t 3 /nobreak >nul
exit
