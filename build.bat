@echo off
setlocal
echo ===================================================
echo   Expense Tracker APKG builder - Asustor AS-202TE
echo ===================================================
python build_package.py %*
pause
