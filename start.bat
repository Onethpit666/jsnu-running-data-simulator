@echo off
chcp 65001 >nul
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo 启动失败。请先运行 install.bat；若端口被占用，可运行 python app.py --port 5001
  pause
)
