@echo off
chcp 65001 >nul
echo ============================================
echo   PoENavi - Run directly (no build needed)
echo ============================================
echo.

REM Install dependencies if needed
pip install PySide6 pynput keyboard opencv-python-headless numpy 2>nul

python main.py
pause
