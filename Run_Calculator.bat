@echo off
title Threadworks Embroidery Calculator
cd /d "%~dp0"
echo ======================================================
echo    Starting Threadworks Embroidery Calculator...
echo ======================================================
echo.
python -m streamlit run app.py
pause

