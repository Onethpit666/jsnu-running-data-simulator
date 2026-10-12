@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements-build.txt
if errorlevel 1 (
  echo 依赖安装失败，已停止打包。
  pause
  exit /b 1
)
python build_exe.py
if errorlevel 1 (
  echo 打包失败，请查看上方错误。
  pause
  exit /b 1
)
echo 打包完成：dist\KeepRunStudio.exe
pause
