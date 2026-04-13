@echo off
chcp 65001 >nul
title OCR-GUI-Tool Git 上传脚本

echo ========================================
echo   OCR-GUI-Tool Git 备份脚本
echo ========================================
echo.

:: 检查 Git 是否安装
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Git 未安装！
    echo 请先下载安装 Git: https://git-scm.com/download/win
    echo 安装完成后重新运行此脚本。
    pause
    exit /b 1
)

echo [OK] Git 已安装

:: 检查是否已有 GitHub 认证
gh auth status >nul 2>&1
if errorlevel 1 (
    echo.
    echo [提示] GitHub 未登录，开始授权...
    gh auth login
)

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查是否是 Git 仓库
if not exist ".git" (
    echo.
    echo [步骤1] 初始化 Git 仓库...
    git init
    git add .
    git commit -m "Initial commit - OCR GUI Tool backup"
) else (
    echo.
    echo [步骤1] Git 仓库已存在，添加所有更改...
    git add .
    git status
    set /p commit_msg=请输入提交说明（直接回车使用默认）:
    if "!commit_msg!"=="" set commit_msg=Update backup
    git commit -m "!commit_msg!"
)

:: 创建 GitHub 仓库并推送
echo.
echo [步骤2] 创建 GitHub 仓库并推送...
echo 请输入仓库名称（直接回车使用默认: OCR-GUI-Tool）:
set /p repo_name=
if "%repo_name%"=="" set repo_name=OCR-GUI-Tool

gh repo create "%repo_name%" --public --source=. --push

echo.
echo ========================================
echo   完成！请访问: https://github.com/YOUR_USERNAME/%repo_name%
echo ========================================
pause
