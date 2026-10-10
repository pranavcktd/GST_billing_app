@echo off
rem ---------------------------------------------------------------------------
rem  Get the latest code BEFORE you start working.
rem
rem  1. GST_billing_app (this repo, both folders)        -> git pull
rem  2. mybillsync_backend  (live on Railway)  -> into backend\
rem  3. mybillsync_frontend (live on Vercel)   -> into frontend\
rem
rem  Steps 2 and 3 bring in anything that was changed directly in the live
rem  repositories (for example a quick fix made on GitHub).
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

call "%~dp0sync-remotes.bat" || goto :fail

git diff --quiet && git diff --cached --quiet
if errorlevel 1 (
  echo.
  echo You have changes that are not committed yet.
  echo Commit or undo them first, then run this again.
  git status --short
  goto :fail
)

echo.
echo === 1/3  Main repository (GST_billing_app) ===
git pull origin main || goto :fail

echo.
echo === 2/3  Backend (mybillsync_backend) ===
git subtree pull --prefix=backend backend-repo main -m "Sync backend from mybillsync_backend" || goto :fail

echo.
echo === 3/3  Frontend (mybillsync_frontend) ===
git subtree pull --prefix=frontend frontend-repo main -m "Sync frontend from mybillsync_frontend" || goto :fail

echo.
echo All up to date. You can start working.
pause
exit /b 0

:fail
echo.
echo *** Stopped - read the message above. Nothing was pushed. ***
pause
exit /b 1
