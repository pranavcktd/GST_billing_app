@echo off
REM ============================================================================
REM  SmartHisab - stop the local servers
REM
REM    stop-dev.bat        stops the frontend (port 3000) and backend (port 8000)
REM    stop-dev.bat all    also stops the database container gst-billing-db
REM ============================================================================
setlocal
set ARG=%1

for %%P in (3000 8000) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:":%%P .*LISTENING"') do (
    if not "%%I"=="0" (
      if /i not "%ARG%"=="quiet" echo Stopping process %%I on port %%P ...
      taskkill /PID %%I /T /F >nul 2>nul
    )
  )
)

REM close the console windows opened by start-dev.bat
taskkill /FI "WINDOWTITLE eq SmartHisab backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq SmartHisab frontend*" /T /F >nul 2>nul

if /i "%ARG%"=="all" (
  echo Stopping database container gst-billing-db ...
  docker stop gst-billing-db >nul 2>nul
)

if /i not "%ARG%"=="quiet" echo SmartHisab servers stopped.
endlocal
