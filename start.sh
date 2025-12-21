#!/bin/bash

echo "========================================"
echo "  OpenAI Balance 启动脚本"
echo "========================================"
echo

# 设置虚拟环境目录名
VENV_DIR=".venv"

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 显示 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1)
echo "[信息] 检测到 $PYTHON_VERSION"

# 检查虚拟环境是否存在
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo
    echo "[信息] 虚拟环境不存在，正在创建..."
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo "[错误] 创建虚拟环境失败"
        exit 1
    fi
    echo "[成功] 虚拟环境已创建"
else
    echo "[信息] 虚拟环境已存在"
fi

# 激活虚拟环境
echo
echo "[信息] 激活虚拟环境..."
source $VENV_DIR/bin/activate

# 检查是否需要安装依赖
if [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo
    echo "[信息] 正在安装依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 安装依赖失败"
        exit 1
    fi
    touch $VENV_DIR/.deps_installed
    echo "[成功] 依赖安装完成"
else
    echo "[信息] 依赖已安装，跳过安装步骤"
    echo "[提示] 如需重新安装依赖，请删除 $VENV_DIR/.deps_installed 文件"
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo
    echo "[警告] 未找到 .env 配置文件"
    if [ -f ".env.example" ]; then
        echo "[信息] 正在从 .env.example 复制..."
        cp .env.example .env
        echo "[成功] 已创建 .env 文件，请根据需要修改配置"
    else
        echo "[警告] 未找到 .env.example，请手动创建 .env 文件"
    fi
fi

# 启动应用
echo
echo "========================================"
echo "  正在启动 OpenAI Balance..."
echo "========================================"
echo
echo "[信息] 访问地址: http://localhost:8000"
echo "[信息] 按 Ctrl+C 停止服务"
echo

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 退出虚拟环境
deactivate
