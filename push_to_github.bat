@echo off
title Push Islamic-AI to GitHub
echo ========================================================
echo        Pushing Islamic-AI project to GitHub
echo ========================================================
echo.

echo [1/5] Syncing files for Cloudflare Pages (app -> root)...
python scripts\sync_for_deployment.py
echo.

echo [2/5] Checking git repository status...
git status
echo.

echo [3/5] Adding all changes to git...
git add -A
echo.

echo [4/5] Creating commit...
git commit -m "Update Islamic-AI: Ten Qiraat audio interactive explorer, word tafsir, Cloudflare sync, API fix"
echo.

echo [5/5] Pushing to remote repository (main branch)...
git push origin main
echo.

if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo      SUCCESS: Changes pushed to GitHub successfully!
    echo ========================================================
) else (
    echo ========================================================
    echo      ERROR: Failed to push to GitHub.
    echo      Please verify your credentials and network.
    echo ========================================================
)

echo.
pause
