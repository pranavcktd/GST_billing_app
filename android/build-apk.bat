@echo off
rem ---------------------------------------------------------------------------
rem  Builds the MyBillSync Android app (APK) without Android Studio.
rem
rem    build-apk.bat                         opens http://<this PC's Wi-Fi IP>:3000
rem    build-apk.bat https://your-site.com   opens that address
rem
rem  Needs: Java 17 (JAVA_HOME) and the Android SDK in D:\android-sdk
rem  (platforms;android-35, build-tools;35.0.0). Output: android\MyBillSync.apk
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

set SDK=D:\android-sdk
set BT=%SDK%\build-tools\35.0.0
set JAR=%SDK%\platforms\android-35\android.jar
if not defined JAVA_HOME set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot
set JAVA=%JAVA_HOME%\bin

set URL=%~1
if "%URL%"=="" (
  for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    if "!IP:~0,3!"=="10." set LAN=!IP!
    if "!IP:~0,8!"=="192.168." set LAN=!IP!
  )
  if not defined LAN (echo Could not find this PC's Wi-Fi address - pass it: build-apk.bat http://192.168.x.x:3000 & goto :fail)
  set URL=http://!LAN!:3000
)
echo Building for: %URL%

if exist build rmdir /s /q build
mkdir build\gen\com\corenexgen\mybillsync build\classes build\dex

rem the address the app opens first (it can be changed in the app if unreachable)
(
  echo package com.corenexgen.mybillsync;
  echo public final class BuildConfig { public static final String DEFAULT_URL = "%URL%"; }
) > build\gen\com\corenexgen\mybillsync\BuildConfig.java

echo [1/6] Resources
"%BT%\aapt2.exe" compile --dir res -o build\res.zip || goto :fail
"%BT%\aapt2.exe" link -o build\app-unsigned.apk -I "%JAR%" --manifest AndroidManifest.xml --java build\gen ^
  --min-sdk-version 26 --target-sdk-version 35 --version-code 1 --version-name 1.0 build\res.zip || goto :fail

echo [2/6] Compile
dir /s /b src\*.java build\gen\*.java > build\sources.txt
"%JAVA%\javac.exe" -nowarn -source 11 -target 11 -encoding UTF-8 -classpath "%JAR%" -d build\classes @build\sources.txt || goto :fail

echo [3/6] Dex
dir /s /b build\classes\*.class > build\classes.txt
call "%BT%\d8.bat" --release --min-api 26 --lib "%JAR%" --output build\dex @build\classes.txt || goto :fail

echo [4/6] Package
pushd build\dex
"%BT%\aapt.exe" add ..\app-unsigned.apk classes.dex >nul || (popd & goto :fail)
popd
"%BT%\zipalign.exe" -p -f 4 build\app-unsigned.apk build\app-aligned.apk || goto :fail

echo [5/6] Signing key
if not exist keystore\mybillsync-test.jks (
  mkdir keystore 2>nul
  "%JAVA%\keytool.exe" -genkeypair -keystore keystore\mybillsync-test.jks -alias mybillsync -keyalg RSA -keysize 2048 ^
    -validity 10000 -storepass mybillsync-test -keypass mybillsync-test ^
    -dname "CN=MyBillSync Test, O=Corenexgen AI Technologies Pvt Ltd, C=IN" || goto :fail
)

echo [6/6] Sign
call "%BT%\apksigner.bat" sign --ks keystore\mybillsync-test.jks --ks-pass pass:mybillsync-test --key-pass pass:mybillsync-test ^
  --out MyBillSync.apk build\app-aligned.apk || goto :fail
call "%BT%\apksigner.bat" verify MyBillSync.apk || goto :fail

echo.
echo Done: %~dp0MyBillSync.apk  (opens %URL%)
exit /b 0

:fail
echo.
echo *** Build failed - see the message above. ***
exit /b 1
