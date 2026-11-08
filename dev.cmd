@echo off
setlocal
cd /d "%~dp0"

if /i "%~1"=="setup" goto setup
if /i "%~1"=="dev" goto dev
echo Usage: dev.cmd setup ^| dev
exit /b 1

:setup
uv sync
if errorlevel 1 exit /b 1
call npm --prefix apps\web ci
if errorlevel 1 exit /b 1
if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  if errorlevel 1 exit /b 1
)
exit /b 0

:dev
node scripts\dev.mjs
exit /b %errorlevel%
