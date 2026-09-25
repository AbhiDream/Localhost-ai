@echo off
setlocal
title LocalHost AI Launcher

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
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

echo Stopping previously started LocalHost AI services...
rem Use a script instead of a long inline command: cmd.exe otherwise escapes
rem PowerShell pipes differently and can leave an old server on the port.
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\stop-localhost-ai.ps1" -ProjectRoot "%ROOT%" >nul 2>&1

echo Opening backend terminal...
start "LocalHost AI Backend" /D "%BACKEND%" "%ComSpec%" /d /k ""%VENV_PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo Opening frontend terminal...
start "LocalHost AI Frontend" /D "%FRONTEND%" "%ComSpec%" /d /k "npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Workbench: http://127.0.0.1:5173
echo Wait until both new terminal windows show ready, then open the Workbench URL.
echo The browser will open automatically in a few seconds.
powershell -NoProfile -Command "Start-Sleep -Seconds 4" >nul
start "" "http://127.0.0.1:5173"
exit /b 0
