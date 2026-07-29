@echo off
title OPTCG / Naruto  -  Review new products
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================================
echo   Step 1/2  -  Looking for new products on every shop
echo ===============================================================
echo.
python -m scraper.new_products generate
if errorlevel 1 goto :error
echo.
echo ===============================================================
echo   ACTION NEEDED
echo ---------------------------------------------------------------
echo   1. Open      data\new_products.xlsx
echo   2. In the 'decision' column put  KEEP  or  DROP  on each row
echo   3. For every KEEP, also fill the 'set' column (e.g. OP12, PRB02)
echo   4. Save and CLOSE the file
echo ===============================================================
echo.
echo   When you are done, press any key to apply your choices...
pause >nul
echo.
echo ===============================================================
echo   Step 2/2  -  Applying KEEP / DROP
echo ===============================================================
echo.
python -m scraper.new_products apply
if errorlevel 1 goto :error
echo.
echo ===============================================================
echo   Done.
echo ===============================================================
pause
goto :eof

:error
echo.
echo /!\ An error occurred. See the messages above.
pause
