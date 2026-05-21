@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
echo.
echo Зависимости установлены. Запуск: python launcher.py
pause
