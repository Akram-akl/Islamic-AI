@echo off
title Push Islamic-AI to GitHub
echo ========================================================
echo        Pushing Islamic-AI project to GitHub
echo ========================================================
echo.

echo [1/4] Checking git repository status...
git status
echo.

echo [2/4] Adding all changes to git...
git add -A
echo.

echo [3/4] Creating commit...
git commit -m "Update Islamic-AI: Quran reciters audio, Isnad tree, audio studio, client-side translation"
echo.

echo [4/4] Pushing to remote repository (main branch)...
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
