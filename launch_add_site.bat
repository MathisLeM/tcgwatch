@echo off
title Add a website to the tracker
chcp 65001 >nul
cd /d "%~dp0"
python -m scraper.add_site
echo.
pause
