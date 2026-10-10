@echo off
rem ---------------------------------------------------------------------------
rem  Send your work live.
rem
rem  1. Commits your changes (asks for a short message) if there are any
rem  2. GST_billing_app      <- the whole project (both folders)
rem  3. mybillsync_backend   <- backend\  only  -> Railway redeploys
rem  4. mybillsync_frontend  <- frontend\ only  -> Vercel redeploys
rem
rem  If a push is refused, someone changed the live repository: run
rem  sync-pull.bat first, then run this again.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

call "%~dp0sync-remotes.bat" || goto :fail

git add -A
git diff --cached --quiet
if errorlevel 1 (
  echo.
  echo Changes to send:
  git status --short
  echo.
  set /p MSG=Describe your change in a few words:
)
git diff --cached --quiet
if errorlevel 1 (
  if not defined MSG set MSG=Update
  git commit -m "%MSG%" || goto :fail
)

echo.
echo === 1/3  Main repository (GST_billing_app) ===
git push origin main || goto :fail

echo.
echo === 2/3  Backend  -^> mybillsync_backend (Railway) ===
git subtree push --prefix=backend backend-repo main || goto :fail

echo.
echo === 3/3  Frontend -^> mybillsync_frontend (Vercel) ===
git subtree push --prefix=frontend frontend-repo main || goto :fail

echo.
echo Done. Railway and Vercel will now build and go live (usually 1-3 minutes).
pause
exit /b 0

:fail
echo.
echo *** Stopped - read the message above. ***
echo If a push was refused, run sync-pull.bat, then sync-push.bat again.
pause
exit /b 1
