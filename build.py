#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess

def build_executable():
    """
    构建可执行文件
    """
    print("开始构建学习通视频完成工具...")
    
    # 检查是否安装了PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("正在安装PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])
    
    # 构建命令
    build_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",  # 打包成单个文件
        "--windowed",  # 不显示控制台窗口 (Windows)
        "--name", "学习通视频完成工具",
        "--icon", "icon.ico",
        "main.py"
    ]
    
    print("执行构建命令...")
    print(" ".join(build_cmd))
    
    try:
        subprocess.check_call(build_cmd)
        print("\n构建完成！可执行文件位于 dist/ 目录下")
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()