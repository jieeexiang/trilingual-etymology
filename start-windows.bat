@echo off
cd /d "%~dp0"
where py 1>NUL 2>NUL
if %errorlevel%==0 (
  py server.py
) else (
  python server.py
)
pause
