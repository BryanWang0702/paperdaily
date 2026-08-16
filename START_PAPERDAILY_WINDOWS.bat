@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo Python 3 was not found.
    echo Install Python 3.11 or newer from python.org, then run this file again.
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  %PYTHON_CMD% -m venv .venv
  if %errorlevel% neq 0 goto :error
)

if not exist "api_token.txt" (
  copy /Y "api_token.example.txt" "api_token.txt" >nul
  echo.
  echo A new api_token.txt file was created.
  echo Paste your DeepSeek/OpenAI-compatible API token into the first line, save it, then run this file again.
  start "" notepad "api_token.txt"
  pause
  exit /b 0
)

echo Checking Python dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if %errorlevel% neq 0 goto :error

echo Starting PaperDaily...
".venv\Scripts\python.exe" local_app.py
if %errorlevel% neq 0 goto :error
exit /b 0

:error
echo.
echo PaperDaily could not start. See the message above for details.
pause
exit /b 1
