@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PORT=8503"
set "APP_FILE=app.py"
title 航运数据异常检测系统

echo ======================================================
echo 正在启动：航运数据异常检测系统
echo 入口文件：%APP_FILE%
echo 本地地址：http://localhost:%PORT%
echo ======================================================
echo.

rem 1) 优先用 Windows py 启动器，其次用 python
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if "%PYTHON_CMD%"=="" (
    echo [错误] 没找到 Python。
    echo 请安装 Python 3.10/3.11/3.12，并勾选 Add Python to PATH。
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检测 Python 版本...
%PYTHON_CMD% --version
if errorlevel 1 (
    echo [错误] Python 可以被找到，但无法正常运行。
    pause
    exit /b 1
)

echo.
echo [2/4] 创建/检查虚拟环境 .venv...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv ".venv"
    if errorlevel 1 (
        echo [警告] python -m venv 创建失败，尝试使用 virtualenv 备用方案...
        %PYTHON_CMD% -m pip install --user virtualenv
        %PYTHON_CMD% -m virtualenv ".venv"
        if errorlevel 1 (
            echo [错误] 虚拟环境仍然创建失败。
            echo 常见原因：Python 安装不完整、路径权限问题、Windows 商店版 Python 异常、文件夹在受限目录。
            echo 建议：安装 python.org 的 Python 3.11/3.12，然后把本项目放到 C:\AI_Portfolio 或桌面英文路径再运行。
            pause
            exit /b 1
        )
    )
) else (
    echo 已存在 .venv，跳过创建。
)

echo.
echo [3/4] 安装/检查依赖包...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    echo 可能原因：网络访问 PyPI 不稳定、某个包版本不兼容、代理/VPN 问题。
    echo 可以稍后重试，或把报错截图发给我继续修。
    pause
    exit /b 1
)

echo.
echo [4/4] 启动 Streamlit...
echo 如果浏览器没有自动打开，请复制：http://localhost:%PORT%
echo.
".venv\Scripts\python.exe" -m streamlit run "%APP_FILE%" --server.port %PORT% --server.address localhost

pause
