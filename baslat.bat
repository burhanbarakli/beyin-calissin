@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Beyin Calissin

rem Python'u bul (PATH, py launcher, varsayilan kurulum yeri)
set "PY="
where python >nul 2>nul && python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo Python bulunamadi. Kurmak icin:  winget install -e --id Python.Python.3.12
  pause
  exit /b 1
)

rem Paketler eksikse kur
"%PY%" -c "import pymupdf, fastapi, uvicorn, multipart" >nul 2>nul || "%PY%" -m pip install -r requirements.txt

rem Ayar dosyasi yoksa ornekten olustur
if not exist config.json copy config.example.json config.json >nul

"%PY%" -m app.server
pause
