@echo off
setlocal EnableExtensions EnableDelayedExpansion
set APP_HOME=%~dp0
set PROPS=%APP_HOME%gradle\wrapper\gradle-wrapper.properties
for /f "tokens=1,* delims==" %%A in (%PROPS%) do if "%%A"=="distributionUrl" set URL=%%B
set URL=%URL:\:=%
for /f "tokens=2 delims=-" %%A in ("%URL%") do set VER=%%A
if "%GRADLE_USER_HOME%"=="" set GRADLE_USER_HOME=%USERPROFILE%\.gradle
set BASE=%GRADLE_USER_HOME%\wrapper\dists\planner-gradle-%VER%
set ZIP=%BASE%\gradle-%VER%-bin.zip
set BIN=%BASE%\gradle-%VER%\bin\gradle.bat
if not exist "%BIN%" (
  if not exist "%BASE%" mkdir "%BASE%"
  if not exist "%ZIP%" powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing '%URL%' -OutFile '%ZIP%'"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%ZIP%' '%BASE%'"
)
call "%BIN%" %*
exit /b %ERRORLEVEL%
