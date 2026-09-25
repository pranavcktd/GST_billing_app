@echo off
REM ============================================================================
REM  SmartHisab - start the local servers
REM
REM    start-dev.bat          development mode (auto-reload on code changes)
REM    start-dev.bat prod     production build (faster pages; rebuilds the frontend first)
REM
REM  Opens:  http://localhost:3000   (also http://<this-PC-IP>:3000 from other devices)
REM  API:    http://127.0.0.1:8000/docs
REM  Stop with stop-dev.bat
REM ============================================================================
setlocal
cd /d "%~dp0"
set MODE=%1

REM ---- stop anything already on the ports, so a restart always works
call "%~dp0stop-dev.bat" quiet

REM ---- 1. database (Docker container gst-billing-db on port 5433)
where docker >nul 2>nul
if errorlevel 1 (
  echo [!] Docker is not installed or not on PATH - start PostgreSQL yourself.
) else (
  docker info >nul 2>nul
  if errorlevel 1 (
    echo [!] Docker Desktop is not running - start it, wait until it is ready, then run this again.
    pause
    exit /b 1
  )
  echo [1/4] Starting database container gst-billing-db ...
  docker start gst-billing-db >nul 2>nul || echo [!] Could not start container gst-billing-db
  REM give PostgreSQL a few seconds to accept connections
  ping -n 5 127.0.0.1 >nul
)

REM ---- 2. database migrations
if not exist "backend\.venv\Scripts\python.exe" (
  echo [!] backend\.venv not found - create it first:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
echo [2/4] Applying database migrations ...
pushd backend
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
  popd
  echo [!] Migration failed - see the message above.
  pause
  exit /b 1
)
popd

REM ---- 3. backend (FastAPI on 127.0.0.1:8000, reached by the frontend through /api)
echo [3/4] Starting backend on http://127.0.0.1:8000 ...
if /i "%MODE%"=="prod" (
  start "SmartHisab backend" /d "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
) else (
  start "SmartHisab backend" /d "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
)

REM ---- 4. frontend (Next.js on 0.0.0.0:3000 so other devices on the LAN can open it)
if not exist "frontend\node_modules" (
  echo [4/4] Installing frontend packages first ...
  pushd frontend
  call npm install
  popd
)
if /i "%MODE%"=="prod" (
  echo [4/4] Building and starting frontend - production - on http://localhost:3000 ...
  start "SmartHisab frontend" /d "%~dp0frontend" cmd /k "npx next build && npx next start -p 3000 -H 0.0.0.0"
) else (
  echo [4/4] Starting frontend - development - on http://localhost:3000 ...
  start "SmartHisab frontend" /d "%~dp0frontend" cmd /k "npx next dev -p 3000 -H 0.0.0.0"
)

echo.
echo  SmartHisab is starting in two new windows (backend, frontend).
echo  Open http://localhost:3000 in a few seconds.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do for /f "tokens=*" %%b in ("%%a") do echo  From other devices on your network: http://%%b:3000
echo  Stop everything with stop-dev.bat
echo.
endlocal
