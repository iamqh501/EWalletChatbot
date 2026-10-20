@echo off
chcp 65001 >nul
title EWallet Chatbot Control Panel

echo ==========================================
echo       EWALLET CHATBOT - STARTUP
echo ==========================================

REM Read ports from .env with fallback defaults
set BACKEND_PORT=8000
set FRONTEND_PORT=3000
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /I "%%a"=="BACKEND_PORT" set BACKEND_PORT=%%b
        if /I "%%a"=="FRONTEND_PORT" set FRONTEND_PORT=%%b
    )
)
set BACKEND_PORT=%BACKEND_PORT: =%
set FRONTEND_PORT=%FRONTEND_PORT: =%

echo VITE_BACKEND_PORT=%BACKEND_PORT%> frontend\.env


echo [INFO] Su dung Backend Port: %BACKEND_PORT%, Frontend Port: %FRONTEND_PORT%

echo [INFO] Dang kiem tra va don dep cac tien trinh cu tren port %BACKEND_PORT% va %FRONTEND_PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%BACKEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%FRONTEND_PORT%"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 >nul

echo [1/2] Dang khoi dong Backend (Uvicorn) chay ngam tren port %BACKEND_PORT%...
powershell -Command "$p = Start-Process cmd -ArgumentList '/c .\.venv\Scripts\uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%' -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText('backend.pid', $p.Id)"

echo [2/2] Dang khoi dong Frontend (Vite) chay ngam tren port %FRONTEND_PORT%...
powershell -Command "$p = Start-Process cmd -ArgumentList '/c cd frontend && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%' -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText('frontend.pid', $p.Id)"

echo.
echo ==========================================
echo He thong dang chay ngam!
echo - Backend API: http://127.0.0.1:%BACKEND_PORT%
echo - Frontend UI: http://127.0.0.1:%FRONTEND_PORT%
echo ==========================================
echo.
echo NHAN PHIM BAT KY TAI DAY DE TAT TOAN BO UNG DUNG...
pause >nul

echo.
echo Dang dong cac dich vu...
set /p BACKEND_PID=<backend.pid
set /p FRONTEND_PID=<frontend.pid
taskkill /PID %BACKEND_PID% /T /F >nul 2>&1
taskkill /PID %FRONTEND_PID% /T /F >nul 2>&1
del backend.pid frontend.pid >nul 2>&1

echo Hoan tat! Tat ca tien trinh da duoc tat.
timeout /t 3 >nul
