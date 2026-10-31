@echo off
cd /d "%~dp0"
py pronunciar.py
if errorlevel 9009 python pronunciar.py
pause
