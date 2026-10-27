@echo off
chcp 65001 >nul
title EWallet Assistant Control Panel

echo ==========================================
echo       EWALLET ASSISTANT - STARTUP
echo ==========================================

REM Read ports from .env with fallback defaults
set BACKEND_PORT=8000
set FRONTEND_PORT=3000
set ADMIN_PORT=3001
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if /I "%%a"=="BACKEND_PORT" set BACKEND_PORT=%%b
        if /I "%%a"=="FRONTEND_PORT" set FRONTEND_PORT=%%b
        if /I "%%a"=="ADMIN_PORT" set ADMIN_PORT=%%b
    )
)
set BACKEND_PORT=%BACKEND_PORT: =%
set FRONTEND_PORT=%FRONTEND_PORT: =%
set ADMIN_PORT=%ADMIN_PORT: =%

(
echo VITE_BACKEND_PORT=%BACKEND_PORT%
echo VITE_USER_PORT=%FRONTEND_PORT%
echo VITE_ADMIN_PORT=%ADMIN_PORT%
) > frontend\.env

echo [INFO] Ports: Backend: %BACKEND_PORT%, User Chatbot: %FRONTEND_PORT%, Admin Docs: %ADMIN_PORT%

echo [INFO] Dang kiem tra va don dep cac tien trinh cu tren port %BACKEND_PORT%, %FRONTEND_PORT%, %ADMIN_PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%BACKEND_PORT% "') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%FRONTEND_PORT% "') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%ADMIN_PORT% "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 >nul

echo [1/3] Dang khoi dong Backend (Uvicorn) chay ngam tren port %BACKEND_PORT%...
powershell -Command "$p = Start-Process cmd -ArgumentList '/c .\.venv\Scripts\uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%' -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText('backend.pid', $p.Id)"

echo [2/3] Dang khoi dong Frontend User (Chatbot) chay ngam tren port %FRONTEND_PORT%...
powershell -Command "$p = Start-Process cmd -ArgumentList '/c cd frontend && npm run dev:user -- --host 127.0.0.1 --port %FRONTEND_PORT%' -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText('frontend_user.pid', $p.Id)"

echo [3/3] Dang khoi dong Frontend Admin (Quan ly tai lieu) chay ngam tren port %ADMIN_PORT%...
powershell -Command "$p = Start-Process cmd -ArgumentList '/c cd frontend && npm run dev:admin -- --host 127.0.0.1 --port %ADMIN_PORT%' -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText('frontend_admin.pid', $p.Id)"

echo.
echo ==========================================
echo He thong dang chay ngam!
echo - Backend API:        http://127.0.0.1:%BACKEND_PORT%
echo - User Chatbot UI:    http://127.0.0.1:%FRONTEND_PORT%
echo - Admin Docs Manager: http://127.0.0.1:%ADMIN_PORT%
echo ==========================================
echo.
echo NHAN PHIM BAT KY TAI DAY DE TAT TOAN BO UNG DUNG...
pause >nul

echo.
echo Dang dong cac dich vu...
if exist backend.pid (
    set /p BACKEND_PID=<backend.pid
    taskkill /PID %BACKEND_PID% /T /F >nul 2>&1
)
if exist frontend_user.pid (
    set /p USER_PID=<frontend_user.pid
    taskkill /PID %USER_PID% /T /F >nul 2>&1
)
if exist frontend_admin.pid (
    set /p ADMIN_PID=<frontend_admin.pid
    taskkill /PID %ADMIN_PID% /T /F >nul 2>&1
)
del backend.pid frontend_user.pid frontend_admin.pid >nul 2>&1

echo Hoan tat! Tat ca tien trinh da duoc tat.
timeout /t 3 >nul
