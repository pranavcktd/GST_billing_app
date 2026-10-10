@echo off
rem Used by sync-pull.bat and sync-push.bat: makes sure the two live repositories are known to git.
cd /d "%~dp0"
git remote get-url backend-repo >nul 2>&1 || git remote add backend-repo https://github.com/pranavcktd/mybillsync_backend.git
git remote get-url frontend-repo >nul 2>&1 || git remote add frontend-repo https://github.com/pranavcktd/mybillsync_frontend.git
git fetch -q backend-repo 2>nul
git fetch -q frontend-repo 2>nul
exit /b 0
