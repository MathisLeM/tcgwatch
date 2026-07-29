@echo off
title OPTCG / Naruto Dashboard
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================================
echo   Starting Streamlit dashboard at http://localhost:8501
echo   Close this window to stop the dashboard.
echo ===============================================================
echo.
streamlit run app.py
