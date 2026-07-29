@echo off
title OPTCG / Naruto Scraper
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================================
echo   OPTCG / Naruto Mythos  -  Taking a fresh snapshot
echo ===============================================================
echo.
python -m scraper.run --game optcg
if errorlevel 1 goto :error
echo.
echo ===============================================================
echo   Regenerating products_view.xlsx
echo ===============================================================
python -m scraper.export_excel
if errorlevel 1 goto :error
echo.
echo ===============================================================
echo   Done.  data\products_view.xlsx is up to date.
echo ===============================================================
pause
goto :eof

:error
echo.
echo /!\ An error occurred. See the messages above.
pause
