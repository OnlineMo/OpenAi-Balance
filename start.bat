@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   OpenAI Balance 启动脚本
echo ========================================
echo.

:: 设置虚拟环境目录名
set VENV_DIR=.venv

:: 检查 Python 是否安装
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 显示 Python 版本
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [信息] 检测到 %PYTHON_VERSION%

:: 检查虚拟环境是否存在
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo [信息] 虚拟环境不存在，正在创建...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境已创建
) else (
    echo [信息] 虚拟环境已存在
)

:: 激活虚拟环境
echo.
echo [信息] 激活虚拟环境...
call %VENV_DIR%\Scripts\activate.bat

:: 检查是否需要安装依赖
if not exist "%VENV_DIR%\.deps_installed" (
    echo.
    echo [信息] 正在安装依赖...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 安装依赖失败
        pause
        exit /b 1
    )
    echo. > %VENV_DIR%\.deps_installed
    echo [成功] 依赖安装完成
) else (
    echo [信息] 依赖已安装，跳过安装步骤
    echo [提示] 如需重新安装依赖，请删除 %VENV_DIR%\.deps_installed 文件
)

:: 检查 .env 文件
if not exist ".env" (
    echo.
    echo [警告] 未找到 .env 配置文件
    if exist ".env.example" (
        echo [信息] 正在从 .env.example 复制...
        copy .env.example .env >nul
        echo [成功] 已创建 .env 文件，请根据需要修改配置
    ) else (
        echo [警告] 未找到 .env.example，请手动创建 .env 文件
    )
)

:: 启动应用
echo.
echo ========================================
echo   正在启动 OpenAI Balance...
echo ========================================
echo.
echo [信息] 访问地址: http://localhost:8000
echo [信息] 按 Ctrl+C 停止服务
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

:: 退出虚拟环境
deactivate

pause
