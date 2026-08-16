@echo off
title TCGWatch - Sync donnees locales vers la prod
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================================
echo   TCGWatch  -  Push des donnees locales vers Supabase (prod)
echo ===============================================================
echo.
echo   DATABASE_URL doit pointer sur Supabase (fichier .env).
echo   Rejouable autant de fois que necessaire (upsert).
echo.
echo ---------------------------------------------------------------
echo   1/2  Apercu (dry-run) : rien n'est ecrit
echo ---------------------------------------------------------------
python -m scripts.sync_to_prod --dry-run
if errorlevel 1 goto :error
echo.
echo ---------------------------------------------------------------
choice /c ON /n /m "   Pousser ces donnees en prod ? [O]ui / [N]on : "
if errorlevel 2 goto :cancel
echo.
echo ---------------------------------------------------------------
echo   2/2  Push
echo ---------------------------------------------------------------
python -m scripts.sync_to_prod
if errorlevel 1 goto :error
echo.
echo ===============================================================
echo   Termine. La prod est a jour.
echo ===============================================================
pause
goto :eof

:cancel
echo.
echo   Annule - rien n'a ete ecrit.
pause
goto :eof

:error
echo.
echo /!\ Une erreur est survenue. Voir les messages ci-dessus.
pause
