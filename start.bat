@echo off
setlocal
title LocalHost AI Launcher

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
set "UVICORN=%BACKEND%\.venv\Scripts\uvicorn.exe"

echo.
echo ================================================
echo LocalHost AI - starting local services
echo ================================================

if not exist "%VENV_PY%" (
  echo Backend environment is missing.
  echo Run this command once in PowerShell:
  echo py -3 -m venv "%BACKEND%\.venv"
  pause
  exit /b 1
)

if not exist "%UVICORN%" (
  echo Uvicorn is missing from the backend environment.
  echo Run this command once in PowerShell:
  echo "%VENV_PY%" -m pip install -r "%BACKEND%\requirements.txt"
  pause
  exit /b 1
)

if not exist "%FRONTEND%\node_modules\.bin\vite.cmd" (
  echo Frontend dependencies are missing.
  echo Run this command once in PowerShell:
  echo cd "%FRONTEND%"; npm install
  pause
  exit /b 1
)

echo Opening backend terminal...
start "LocalHost AI Backend" /D "%BACKEND%" cmd.exe /k %UVICORN% main:app --host 127.0.0.1 --port 8000

echo Opening frontend terminal...
start "LocalHost AI Frontend" /D "%FRONTEND%" cmd.exe /k "npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Workbench: http://localhost:5173
echo Wait until both new terminal windows show ready, then open the Workbench URL.
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"
exit /b 0
