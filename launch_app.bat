@echo off
title TCGWatch - Local App (API + Frontend)
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================================
echo   TCGWatch - version LOCALE (identique a la prod)
echo   API  (FastAPI) : http://localhost:8000/docs
echo   App  (Next.js) : http://localhost:3000
echo.
echo   Base de donnees : SQLite locale (data\tcg_stock.sqlite)
echo   -> tes essais locaux NE touchent PAS la prod Supabase.
echo.
echo   Ferme LES DEUX fenetres pour tout arreter.
echo ===============================================================
echo.

REM --- 1) Backend API dans sa propre fenetre (rechargement auto) ---------------
echo [1/2] Demarrage de l'API FastAPI sur le port 8000...
start "TCGWatch API (local)" cmd /k "cd /d "%~dp0" && set ENVIRONMENT=development && set DATABASE_URL=sqlite:///./data/tcg_stock.sqlite && python -m uvicorn main:app --reload --port 8000"

REM --- 2) Frontend Next.js dans CETTE fenetre ---------------------------------
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [2/2] Installation des dependances frontend ^(premier lancement^)...
    call npm install
    echo.
)
echo [2/2] Demarrage du frontend Next.js sur le port 3000...
echo.
echo   Le navigateur va s'ouvrir sur http://localhost:3000
echo   (si la page est vide au debut, rafraichis apres quelques secondes).
echo.
timeout /t 4 >nul
start "" "http://localhost:3000"
call npm run dev
