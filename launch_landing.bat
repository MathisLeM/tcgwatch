@echo off
title TCGWatch Landing Page
chcp 65001 >nul
cd /d "%~dp0frontend"
echo ===============================================================
echo   Starting Next.js landing page at http://localhost:3000
echo   Close this window to stop the dev server.
echo ===============================================================
echo.
if not exist "node_modules" (
    echo Installing dependencies ^(first run^)...
    call npm install
    echo.
)
echo Opening http://localhost:3000 in your browser...
start "" "http://localhost:3000"
call npm run dev
