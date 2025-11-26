@echo off
setlocal
set SCRIPT_DIR=%~dp0
python -m pip install --upgrade pip
python -m pip install -r "%SCRIPT_DIR%requirements.txt"
endlocal
